"""
DevX Batch Operations API
=========================

Provides multi-user maintenance operations with an initial focus on
user deletion via quarantine. The architecture is designed so future
batch actions (holistic reviews, recomputations, etc.) can plug into
the same job manifest workflow with minimal changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from .config import PROJECT_ROOT
from ReDNACoreDemo.core.agent_capabilities import generate_token

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Paths & environment overrides
# ---------------------------------------------------------------------------

REPO_DATA_ROOT = PROJECT_ROOT.parent / "data"
DEFAULT_DATA_ROOT = REPO_DATA_ROOT if (REPO_DATA_ROOT / "users").exists() else PROJECT_ROOT / "data"
DATA_ROOT = Path(os.environ.get("DEVX_DATA_ROOT", DEFAULT_DATA_ROOT))
USERS_ROOT = DATA_ROOT / "users"
QUARANTINE_ROOT = DATA_ROOT / "quarantine"
PURGE_REQUESTS_ROOT = DATA_ROOT / "purge_requests"
DEVX_JOBS_ROOT = DATA_ROOT / "devx_jobs"
HOLISTIC_JOBS_ROOT = DEVX_JOBS_ROOT / "holistic"
REVOKE_CAPS_JOBS_ROOT = DEVX_JOBS_ROOT / "revoke_caps"
HOLISTIC_RESULTS_ROOT = DATA_ROOT / "holistic"
HOLISTIC_HISTORY_ROOT = HOLISTIC_RESULTS_ROOT / "history"
AUDIT_LOG = DEVX_JOBS_ROOT / "user_ops_audit.jsonl"
PERMISSIONS_ROOT = DATA_ROOT / "permissions"
CAPABILITY_STORE_ROOT = DATA_ROOT / "capability_tokens"

for directory in (
    USERS_ROOT,
    QUARANTINE_ROOT,
    PURGE_REQUESTS_ROOT,
    DEVX_JOBS_ROOT,
    HOLISTIC_JOBS_ROOT,
    REVOKE_CAPS_JOBS_ROOT,
    HOLISTIC_RESULTS_ROOT,
    HOLISTIC_HISTORY_ROOT,
    AUDIT_LOG.parent,
    PERMISSIONS_ROOT,
    CAPABILITY_STORE_ROOT,
):
    directory.mkdir(parents=True, exist_ok=True)

# Consent service configuration
CONSENT_SERVICE_URL = os.environ.get("CONSENT_SERVICE_URL", "http://127.0.0.1:8200")
CONSENT_PORT_LOG = PROJECT_ROOT / "data" / "consent" / "consent_port.log"

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def timestamp_for_id(moment: Optional[datetime] = None) -> str:
    """Render a timestamp suitable for filenames (e.g. 20251008T123456Z)."""
    moment = moment or utcnow()
    return moment.strftime("%Y%m%dT%H%M%SZ")


def validate_user_id(user_id: str) -> str:
    """Normalize and validate user ids to prevent path traversal."""
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id must be provided.")
    user_id = user_id.strip()
    if "/" in user_id or "\\" in user_id or ".." in user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user id: {user_id}")
    return user_id


def safe_json_dump(path: Path, payload: Dict) -> None:
    """Write JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def append_audit(event: str, payload: Dict[str, Any]) -> None:
    """Append audit entry to JSONL log."""
    entry = {
        "event": event,
        "timestamp": utcnow().isoformat().replace("+00:00", "Z"),
        **payload,
    }
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def load_json(path: Path) -> Dict:
    """Load JSON if present, returning an empty dict on failure."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid JSON encountered at %s", path)
        return {}


def directory_size_bytes(path: Path) -> int:
    """Recursively compute total size; resilient to racing files."""
    total = 0
    if not path.exists():
        return total
    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            try:
                total += file_path.stat().st_size
            except FileNotFoundError:
                continue
    return total


def directory_last_updated(path: Path) -> Optional[str]:
    """Return ISO timestamp of latest modification under a directory."""
    latest: Optional[float] = None
    if not path.exists():
        return None
    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            try:
                mtime = file_path.stat().st_mtime
                if latest is None or mtime > latest:
                    latest = mtime
            except FileNotFoundError:
                continue
    if latest is None:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


SYNTHETIC_NAME_PREFIXES = ("persona_", "hc_", "mrscoach", "mrscoachtest")
SYNTHETIC_NAME_SUFFIXES = ("_exp", "_demo")


def is_synthetic(name: str, user_dir: Path) -> bool:
    """Identify synthetic directories using naming heuristics and metadata markers."""
    lowered = name.lower()
    if lowered.startswith(SYNTHETIC_NAME_PREFIXES) or lowered.endswith(SYNTHETIC_NAME_SUFFIXES):
        return True

    if (user_dir / ".synthetic").exists():
        return True

    user_json = user_dir / "user.json"
    if user_json.exists():
        payload = load_json(user_json)
        kind = payload.get("kind")
        if isinstance(kind, str):
            if kind.lower() != "human":
                return True
        elif kind is not None:
            return True

    return False


def list_top_level(path: Path) -> List[str]:
    """List top-level entries in a directory."""
    if not path.exists():
        return []
    entries = []
    for entry in sorted(path.iterdir()):
        entries.append(entry.name)
    return entries


def count_files(path: Path) -> int:
    """Count files under a directory."""
    if not path.exists():
        return 0
    total = 0
    for _, _, files in os.walk(path):
        total += len(files)
    return total


def read_resolved(user_id: str) -> Dict[str, Any]:
    """Read resolved.json for a user if available."""
    resolved_path = user_directory(user_id) / "resolved.json"
    if not resolved_path.exists():
        return {}
    try:
        return json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read resolved.json for %s: %s", user_id, exc)
        return {}


def compute_rr_metrics(containers: List[Dict[str, Any]]) -> Tuple[float, Dict[str, float], List[Dict[str, Any]]]:
    """Compute overall RR, domain-level averages, and lowest RR paths."""
    rr_values: List[float] = []
    domain_map: Dict[str, List[float]] = {}
    path_rr_pairs: List[Tuple[str, float]] = []

    for entry in containers:
        if not isinstance(entry, dict):
            continue
        rr_value = entry.get("rr")
        path = entry.get("path")
        if isinstance(rr_value, (int, float)):
            rr_float = float(rr_value)
            rr_values.append(rr_float)
            if isinstance(path, str):
                domain = path.split(".")[0] if "." in path else path
                domain_map.setdefault(domain, []).append(rr_float)
                path_rr_pairs.append((path, rr_float))

    if rr_values:
        sorted_rr = sorted(rr_values)
        mid = len(sorted_rr) // 2
        if len(sorted_rr) % 2 == 0:
            overall_rr = (sorted_rr[mid - 1] + sorted_rr[mid]) / 2.0
        else:
            overall_rr = sorted_rr[mid]
    else:
        overall_rr = 0.0

    by_domain = {
        domain: (sum(values) / len(values) if values else 0.0)
        for domain, values in domain_map.items()
    }

    path_rr_pairs.sort(key=lambda item: item[1])
    top_low_rr = [{"path": path, "rr": rr} for path, rr in path_rr_pairs[:5]]

    return (overall_rr, by_domain, top_low_rr)


def write_holistic_result(user_id: str, payload: Dict[str, Any]) -> None:
    """Persist holistic result and history snapshot."""
    HOLISTIC_RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    HOLISTIC_HISTORY_ROOT.mkdir(parents=True, exist_ok=True)

    result_path = HOLISTIC_RESULTS_ROOT / f"{user_id}.json"
    history_stamp = payload["generated_at"].replace(":", "").replace("-", "")
    history_path = HOLISTIC_HISTORY_ROOT / f"{user_id}_{history_stamp}.json"

    safe_json_dump(result_path, payload)
    safe_json_dump(history_path, payload)


def load_latest_holistic(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the latest holistic result for a user if available."""
    result_path = HOLISTIC_RESULTS_ROOT / f"{user_id}.json"
    if not result_path.exists():
        return None
    payload = load_json(result_path)
    if not payload:
        return None
    return payload


def list_holistic_history(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Collect recent holistic history entries."""
    pattern = f"{user_id}_*.json"
    entries = sorted(HOLISTIC_HISTORY_ROOT.glob(pattern), reverse=True)
    history: List[Dict[str, Any]] = []
    for path in entries[:limit]:
        payload = load_json(path)
        generated_at = payload.get("generated_at") if isinstance(payload, dict) else None
        try:
            size_bytes = path.stat().st_size
        except FileNotFoundError:
            size_bytes = None
        history.append(
            {
                "path": str(path),
                "generated_at": generated_at,
                "size_bytes": size_bytes,
            }
        )
    return history


def load_user_audit_entries(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Read recent audit log entries involving the user."""
    if not AUDIT_LOG.exists():
        return []

    try:
        lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()
    except Exception:  # noqa: BLE001
        return []

    filtered: List[Dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        users = entry.get("user_ids")
        match = False
        if isinstance(users, list):
            match = any(str(u) == user_id for u in users)
        elif isinstance(users, str):
            match = users == user_id

        if not match:
            if entry.get("user_id") == user_id or entry.get("from") == user_id or entry.get("to") == user_id:
                match = True

        if match:
            filtered.append(entry)
        if len(filtered) >= limit:
            break

    return filtered


def permissions_path(user_id: str) -> Path:
    return PERMISSIONS_ROOT / f"{user_id}.json"


def load_permissions(user_id: str) -> Dict[str, Any]:
    path = permissions_path(user_id)
    if not path.exists():
        return {"namespaces": {}}
    data = load_json(path)
    if not isinstance(data, dict):
        return {"namespaces": {}}
    data.setdefault("namespaces", {})
    return data


def save_permissions(user_id: str, payload: Dict[str, Any]) -> None:
    safe_json_dump(permissions_path(user_id), payload)


def capability_store_path(user_id: str) -> Path:
    return CAPABILITY_STORE_ROOT / f"{user_id}.json"


def load_capability_tokens(user_id: str) -> List[Dict[str, Any]]:
    path = capability_store_path(user_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return []


def save_capability_tokens(user_id: str, tokens: List[Dict[str, Any]]) -> None:
    path = capability_store_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    tmp.replace(path)


def mark_capability_status(user_id: str, capability_id: str, status: str) -> Optional[Dict[str, Any]]:
    tokens = load_capability_tokens(user_id)
    updated: Optional[Dict[str, Any]] = None
    for token in tokens:
        if token.get("capability_id") == capability_id:
            if token.get("status") != status:
                token["status"] = status
            timestamp = utcnow().isoformat().replace("+00:00", "Z")
            if status == "revoked":
                token["revoked_at"] = timestamp
            updated = token
            break
    if updated is not None:
        save_capability_tokens(user_id, tokens)
    return updated


def latest_ticket(user_id: str) -> Tuple[Optional[Path], Optional[Dict]]:
    """Return the most recent purge ticket for a user."""
    ticket_dir = PURGE_REQUESTS_ROOT / user_id
    if not ticket_dir.exists():
        return (None, None)
    tickets = sorted(ticket_dir.glob("ticket_*.json"))
    if not tickets:
        return (None, None)
    latest_path = tickets[-1]
    return (latest_path, load_json(latest_path))


def build_job_path(job_id: str) -> Path:
    return DEVX_JOBS_ROOT / f"{job_id}.json"


def load_job(job_id: str) -> Dict:
    job_path = build_job_path(job_id)
    if not job_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    return load_json(job_path)


def update_job_manifest(job_id: str, data: Dict) -> None:
    job_path = build_job_path(job_id)
    safe_json_dump(job_path, data)


def find_job_entry(user_id: str, action: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Find the most recent job containing the user entry.

    Returns (job_id, user_entry) or (None, None).
    """
    job_files = sorted(DEVX_JOBS_ROOT.glob("job_*.json"))
    if not job_files:
        return (None, None)
    for path in reversed(job_files):
        data = load_json(path)
        if action and data.get("action") != action:
            continue
        users = data.get("users", {})
        if user_id in users:
            return (path.stem.replace(".json", ""), users[user_id])
    return (None, None)


def confirm_string(expected_prefix: str, count: int, provided: str) -> None:
    expected = f"{expected_prefix} {count} USERS"
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Confirmation string mismatch. Expected '{expected}'.",
        )


# ---------------------------------------------------------------------------
# Consent service client
# ---------------------------------------------------------------------------


class ConsentServiceClient:
    """Thin HTTP client around the Consent Service."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def list_capabilities(self, user_id: str) -> Tuple[Optional[List[Dict]], Optional[str]]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/consent/capabilities", params={"user_id": user_id})
                response.raise_for_status()
                payload = response.json()
                caps = payload.get("capabilities")
                if caps is None:
                    return ([], None)
                if isinstance(caps, list):
                    return (caps, None)
                return ([], "Unexpected capabilities response format.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Consent service capabilities fetch failed for %s: %s", user_id, exc)
            return (None, str(exc))

    def revoke_capability(self, capability: Dict) -> Optional[str]:
        cap_id = capability.get("id") or capability.get("capability_id")
        if not cap_id:
            return "Capability record missing identifier."
        payload = {"capability_id": cap_id}
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(f"{self.base_url}/consent/revoke", json=payload)
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Consent service revoke failed for %s: %s", cap_id, exc)
            return str(exc)
        return None


def get_consent_client() -> ConsentServiceClient:
    return ConsentServiceClient(get_consent_service_url())


def get_consent_service_url() -> str:
    """Derive consent service URL from port log or fall back to default."""
    try:
        if CONSENT_PORT_LOG.exists():
            port = CONSENT_PORT_LOG.read_text(encoding="utf-8").strip()
            if port:
                return f"http://127.0.0.1:{port}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read consent port log: %s", exc)
    return CONSENT_SERVICE_URL


def revoke_user_capabilities(user_id: str) -> Tuple[Optional[int], List[str]]:
    """
    Revoke all capabilities for a user via the consent service.

    Returns (count, warnings). If the service is offline, count is None
    and warnings contains the failure reason.
    """
    client = get_consent_client()
    capabilities, error = client.list_capabilities(user_id)
    if capabilities is None:
        return (None, [error or "Consent service unavailable."])

    warnings: List[str] = []
    revoked = 0
    for capability in capabilities:
        issue = client.revoke_capability(capability)
        if issue:
            warnings.append(f"Failed to revoke capability {capability}: {issue}")
        else:
            revoked += 1

    return (revoked, warnings)


# ---------------------------------------------------------------------------
# Data computations
# ---------------------------------------------------------------------------


def user_directory(user_id: str) -> Path:
    return USERS_ROOT / user_id


def quarantine_directory(batch_timestamp: str, user_id: str) -> Path:
    return QUARANTINE_ROOT / batch_timestamp / user_id


def summarize_user(user_id: str) -> Dict:
    path = user_directory(user_id)
    size_bytes = directory_size_bytes(path)
    last_updated = directory_last_updated(path)
    has_vault = path.exists()

    ticket_path, ticket = latest_ticket(user_id)
    quarantine_status = None
    review_until = None
    if ticket:
        quarantine_status = ticket.get("status")
        review_until = ticket.get("review_until")

    return {
        "user_id": user_id,
        "has_vault": has_vault,
        "last_updated": last_updated,
        "size_bytes": size_bytes,
        "quarantine_status": quarantine_status,
        "review_until": review_until,
    }


def compute_summary_counts(user_id: str) -> Dict:
    base = user_directory(user_id)
    evidence = count_files(base / "evidence")
    derived = count_files(base / "derived")
    containers = count_files(base / "containers")
    return {
        "counts": {
            "evidence": evidence,
            "derived": derived,
            "containers": containers,
        },
        "last_updated": directory_last_updated(base),
        "size_bytes": directory_size_bytes(base),
    }


def dry_run_plan(user_id: str) -> Dict:
    base = user_directory(user_id)
    size_bytes = directory_size_bytes(base)
    vault_paths = list_top_level(base)

    ticket_path, ticket = latest_ticket(user_id)
    has_open = bool(ticket and ticket.get("status") in {"quarantine"})

    caps, warning = get_consent_client().list_capabilities(user_id)
    capability_count = None if caps is None else len(caps)
    warnings = []
    if warning:
        warnings.append(warning)

    return {
        "user_id": user_id,
        "bytes_to_quarantine": size_bytes,
        "vault_paths": vault_paths,
        "capability_count": capability_count,
        "warnings": warnings,
        "has_open_tickets": has_open,
    }


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@router.get("/users/list")
def list_users(
    query: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_synthetic: bool = Query(False),
) -> Dict:
    """
    List known users from the vault directory with lightweight metadata.
    """
    if not USERS_ROOT.exists():
        return {"users": [], "total": 0}

    entries: List[Path] = [entry for entry in sorted(USERS_ROOT.iterdir()) if entry.is_dir()]

    if not include_synthetic:
        entries = [entry for entry in entries if not is_synthetic(entry.name, entry)]

    if query:
        q = query.lower()
        entries = [entry for entry in entries if q in entry.name.lower()]

    total = len(entries)
    page = entries[offset : offset + limit]
    summaries = [summarize_user(path.name) for path in page]

    return {"users": summaries, "total": total}


@router.get("/users/summary")
def user_summary(user_id: str) -> Dict:
    """
    Provide counts and metadata for a single user.
    """
    user_id = validate_user_id(user_id)
    base = user_directory(user_id)
    if not base.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found.")

    result = compute_summary_counts(user_id)
    result.update({"user_id": user_id})
    return result


@router.post("/users/batch/dry-run")
def dry_run_delete(payload: Dict) -> Dict:
    user_ids = payload.get("user_ids") or []
    if not isinstance(user_ids, list) or not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids must be a non-empty list.")

    plan: Dict[str, Dict] = {}
    totals = {"bytes_to_quarantine": 0, "users": 0}
    for raw_user_id in user_ids:
        user_id = validate_user_id(str(raw_user_id))
        base = user_directory(user_id)
        if not base.exists():
            plan[user_id] = {
                "user_id": user_id,
                "error": "User vault not found.",
            }
            continue
        user_plan = dry_run_plan(user_id)
        plan[user_id] = user_plan
        totals["bytes_to_quarantine"] += user_plan["bytes_to_quarantine"]
        totals["users"] += 1

    return {"users": plan, "totals": totals}


@router.post("/users/batch/delete")
def batch_delete(payload: Dict) -> Dict:
    user_ids = payload.get("user_ids") or []
    if not isinstance(user_ids, list) or not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids must be a non-empty list.")

    reason = payload.get("reason") or ""
    grace_days = payload.get("grace_days", 7)
    confirm = payload.get("confirm") or ""

    confirm_string("DELETE", len(user_ids), confirm)
    if grace_days <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="grace_days must be positive.")

    moment = utcnow()
    batch_timestamp = timestamp_for_id(moment)
    job_id = f"job_{batch_timestamp}_{uuid4().hex[:6]}"
    job_manifest = {
        "job_id": job_id,
        "action": "delete",
        "created_at": moment.isoformat(),
        "reason": reason,
        "grace_days": grace_days,
        "users": {},
    }

    accepted: List[str] = []
    errors: List[Dict[str, str]] = []

    for raw_user_id in user_ids:
        user_id = validate_user_id(str(raw_user_id))
        base = user_directory(user_id)
        entry = {
            "status": "error",
            "errors": [],
            "warnings": [],
        }

        if not base.exists():
            message = "User vault not found."
            entry["errors"].append(message)
            errors.append({"user_id": user_id, "message": message})
            job_manifest["users"][user_id] = entry
            continue

        if any(base.iterdir()) is False:
            logger.debug("User %s vault exists but appears empty.", user_id)

        revoked_count, warnings = revoke_user_capabilities(user_id)
        entry["capabilities_revoked"] = revoked_count
        if warnings:
            entry["warnings"].extend(warnings)

        review_until_dt = moment + timedelta(days=grace_days)
        review_until_iso = review_until_dt.isoformat()

        ticket_payload = {
            "user_id": user_id,
            "requested_at": moment.isoformat(),
            "status": "quarantine",
            "review_until": review_until_iso,
            "reason": reason,
            "capabilities_revoked": revoked_count,
            "warnings": warnings,
            "job_id": job_id,
        }

        ticket_name = f"ticket_{batch_timestamp}.json"
        ticket_path = PURGE_REQUESTS_ROOT / user_id / ticket_name

        quarantine_path = quarantine_directory(batch_timestamp, user_id)
        if quarantine_path.exists():
            entry["errors"].append("Quarantine path already exists.")
            errors.append({"user_id": user_id, "message": "Quarantine path already exists."})
            job_manifest["users"][user_id] = entry
            continue

        try:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            base.rename(quarantine_path)
        except OSError as exc:
            message = f"Failed to move vault to quarantine: {exc}"
            logger.exception("Quarantine move failed for %s", user_id)
            entry["errors"].append(message)
            errors.append({"user_id": user_id, "message": message})
            job_manifest["users"][user_id] = entry
            continue

        ticket_payload["quarantine_path"] = str(quarantine_path)
        safe_json_dump(ticket_path, ticket_payload)

        entry.update(
            {
                "status": "quarantine",
                "ticket_path": str(ticket_path),
                "quarantine_path": str(quarantine_path),
                "requested_at": moment.isoformat(),
                "review_until": review_until_iso,
            }
        )

        job_manifest["users"][user_id] = entry
        accepted.append(user_id)

    update_job_manifest(job_id, job_manifest)
    return {"job_id": job_id, "accepted": accepted, "errors": errors}


@router.get("/users/batch/status")
def batch_status(job_id: str) -> Dict:
    data = load_job(job_id)

    # Refresh runtime status from ticket files if available
    users = data.get("users", {})
    for user_id, info in users.items():
        ticket_path = info.get("ticket_path")
        if ticket_path:
            path = Path(ticket_path)
            if path.exists():
                ticket = load_json(path)
                info["status"] = ticket.get("status", info.get("status"))
                info["review_until"] = ticket.get("review_until", info.get("review_until"))
                if info["status"] == "restored":
                    info["restored_at"] = ticket.get("restored_at")
                if info["status"] == "purged":
                    info["purged_at"] = ticket.get("purged_at")
    return data


@router.post("/users/batch/undo")
def batch_undo(payload: Dict) -> Dict:
    job_id = payload.get("job_id")
    user_ids = payload.get("user_ids") or []
    confirm = payload.get("confirm") or ""

    if not job_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="job_id is required.")

    if not isinstance(user_ids, list) or not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids must be a non-empty list.")

    confirm_string("UNDO", len(user_ids), confirm)

    job_manifest = load_job(job_id)
    users = job_manifest.get("users", {})
    results = {"restored": [], "errors": []}

    for raw_user_id in user_ids:
        user_id = validate_user_id(str(raw_user_id))
        entry = users.get(user_id)
        if not entry:
            results["errors"].append({"user_id": user_id, "message": "User not part of job."})
            continue

        if entry.get("status") != "quarantine":
            results["errors"].append({"user_id": user_id, "message": "User is not in quarantine."})
            continue

        review_until = entry.get("review_until")
        if review_until:
            review_dt = datetime.fromisoformat(review_until)
            if utcnow() >= review_dt:
                results["errors"].append({"user_id": user_id, "message": f"Grace period expired on {review_until}."})
                continue

        quarantine_path = Path(entry.get("quarantine_path", ""))
        if not quarantine_path.exists():
            results["errors"].append({"user_id": user_id, "message": "Quarantine data missing."})
            continue

        dest = user_directory(user_id)
        if dest.exists():
            results["errors"].append({"user_id": user_id, "message": "User vault already exists; cannot restore."})
            continue

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            quarantine_path.rename(dest)
        except OSError as exc:
            message = f"Failed to restore vault: {exc}"
            logger.exception("Restore failed for %s", user_id)
            results["errors"].append({"user_id": user_id, "message": message})
            continue

        ticket_path = Path(entry.get("ticket_path", ""))
        ticket = load_json(ticket_path) if ticket_path else {}
        ticket.update({"status": "restored", "restored_at": utcnow().isoformat()})
        safe_json_dump(ticket_path, ticket)

        entry["status"] = "restored"
        entry["restored_at"] = ticket["restored_at"]
        results["restored"].append(user_id)

    update_job_manifest(job_id, job_manifest)
    return {"job_id": job_id, **results}


@router.post("/users/batch/purge")
def batch_purge(payload: Dict) -> Dict:
    user_ids = payload.get("user_ids") or []
    confirm = payload.get("confirm") or ""

    if not isinstance(user_ids, list) or not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids must be a non-empty list.")

    confirm_string("PURGE", len(user_ids), confirm)

    results = {"purged": [], "errors": []}

    for raw_user_id in user_ids:
        user_id = validate_user_id(str(raw_user_id))
        ticket_path, ticket = latest_ticket(user_id)
        if not ticket:
            results["errors"].append({"user_id": user_id, "message": "No purge ticket found."})
            continue

        if ticket.get("status") != "quarantine":
            results["errors"].append({"user_id": user_id, "message": "User is not in quarantine state."})
            continue

        review_until = ticket.get("review_until")
        if review_until:
            review_dt = datetime.fromisoformat(review_until)
            if utcnow() < review_dt:
                results["errors"].append(
                    {"user_id": user_id, "message": f"Cannot purge: still within grace period until {review_until}."}
                )
                continue

        quarantine_path = ticket.get("quarantine_path")
        if not quarantine_path:
            results["errors"].append({"user_id": user_id, "message": "Quarantine path not recorded in ticket."})
            continue

        path = Path(quarantine_path)
        if not path.exists():
            logger.warning("Expected quarantine path %s missing during purge.", path)

        try:
            if path.exists():
                shutil.rmtree(path)
            ticket.update({"status": "purged", "purged_at": utcnow().isoformat()})
            safe_json_dump(ticket_path, ticket)
        except OSError as exc:
            message = f"Failed to purge data: {exc}"
            logger.exception("Purge failed for %s", user_id)
            results["errors"].append({"user_id": user_id, "message": message})
            continue

        # Update job manifest entry if one exists
        job_id, job_entry = find_job_entry(user_id, action="delete")
        if job_id and job_entry:
            job_data = load_job(job_id)
            job_user_entry = job_data.get("users", {}).get(user_id, {})
            job_user_entry["status"] = "purged"
            job_user_entry["purged_at"] = ticket["purged_at"]
            update_job_manifest(job_id, job_data)

        results["purged"].append(user_id)

    return results


@router.post("/users/batch/revoke-caps")
async def revoke_caps_batch(request: BatchRequest) -> Dict:
    """
    Revoke all capabilities for the provided users via the Consent Service.

    The operation is idempotent: failures are recorded per-user but do not abort the job.
    """

    unique_ids = sorted({validate_user_id(str(uid)) for uid in request.user_ids})
    if not unique_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_ids must be provided.")

    moment = utcnow()
    timestamp = moment.strftime("%Y%m%d_%H%M%S")
    job_id = f"revoke_caps_{timestamp}"
    job_path = REVOKE_CAPS_JOBS_ROOT / f"{job_id}.json"

    results = []
    total_revoked = 0

    for user_id in unique_ids:
        count, warnings = await asyncio.to_thread(revoke_user_capabilities, user_id)
        revoked = count or 0
        total_revoked += revoked
        results.append(
            {
                "user_id": user_id,
                "revoked": revoked,
                "warnings": warnings,
            }
        )

    manifest = {
        "job_id": job_id,
        "action": "revoke_caps",
        "queued_at": moment.isoformat().replace("+00:00", "Z"),
        "reason": request.reason,
        "results": results,
        "total_revoked": total_revoked,
    }

    await asyncio.to_thread(safe_json_dump, job_path, manifest)

    return {
        "job_id": job_id,
        "status": "completed",
        "total_revoked": total_revoked,
        "results": results,
    }


def _next_holistic_job_id(moment: datetime) -> Tuple[str, Path]:
    """Generate a unique holistic job identifier."""
    timestamp = moment.strftime("%Y%m%d_%H%M%S")
    base_id = f"holistic_{timestamp}"
    job_path = HOLISTIC_JOBS_ROOT / f"{base_id}.json"
    counter = 1
    while job_path.exists():
        counter += 1
        job_path = HOLISTIC_JOBS_ROOT / f"{base_id}_{counter:02d}.json"
    job_id = job_path.stem
    return job_id, job_path


async def _queue_holistic_job(user_ids: List[str], reason: Optional[str]) -> Dict[str, Any]:
    """Create a holistic job manifest for the provided users."""
    sanitized_ids = [validate_user_id(str(uid)) for uid in user_ids]
    moment = utcnow()
    job_id, job_path = _next_holistic_job_id(moment)

    manifest = {
        "job_id": job_id,
        "user_ids": sanitized_ids,
        "queued_at": moment.isoformat().replace("+00:00", "Z"),
        "status": "queued",
        "action": "run_holistic",
    }
    if reason:
        manifest["reason"] = reason

    await asyncio.to_thread(safe_json_dump, job_path, manifest)
    logger.info("Queued holistic review job %s for %d users", job_id, len(sanitized_ids))
    return {"job_id": job_id, "status": "queued", "count": len(sanitized_ids)}


@router.post("/users/batch/run-holistic")
async def run_holistic_batch(request: BatchRequest) -> Dict:
    """
    Queue holistic-review jobs for selected users.

    No vault writes; just record a job manifest.
    """

    return await _queue_holistic_job(request.user_ids, request.reason)


@router.post("/users/batch/run-holistic/process")
async def process_holistic_job(job_id: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Execute a queued holistic job and persist results for each user."""

    manifest_path = HOLISTIC_JOBS_ROOT / f"{job_id}.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holistic job not found.")

    manifest = load_json(manifest_path)
    if manifest.get("action") != "run_holistic":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not a holistic job.")

    user_ids = manifest.get("user_ids", [])
    if not user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Holistic job has no users.")

    processed_at = utcnow()
    results: List[Dict[str, Any]] = []

    for user_id in user_ids:
        user_id = validate_user_id(str(user_id))
        base = user_directory(user_id)
        try:
            resolved = read_resolved(user_id)
            containers = resolved.get("containers", []) if isinstance(resolved.get("containers"), list) else []
            evidence_count = count_files(base / "evidence")
            derived_count = count_files(base / "derived")
            container_count = len(containers)

            overall_rr, by_domain, low_rr = compute_rr_metrics(containers)

            payload = {
                "user_id": user_id,
                "generated_at": processed_at.isoformat().replace("+00:00", "Z"),
                "counts": {
                    "containers": container_count,
                    "evidence": evidence_count,
                    "derived": derived_count,
                },
                "rr": {
                    "overall_rr": round(overall_rr, 2),
                    "by_domain": {domain: round(value, 2) for domain, value in by_domain.items()},
                },
                "top_low_rr_paths": [
                    {"path": item["path"], "rr": round(item["rr"], 2)} for item in low_rr
                ],
                "notes": manifest.get("reason", "Phase2 baseline"),
            }

            await asyncio.to_thread(write_holistic_result, user_id, payload)
            results.append({"user_id": user_id, "status": "ok", "generated_at": payload["generated_at"]})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Holistic processing failed for %s", user_id)
            results.append({"user_id": user_id, "status": "error", "reason": str(exc)})

    manifest.update(
        {
            "status": "completed",
            "completed_at": processed_at.isoformat().replace("+00:00", "Z"),
            "results": results,
        }
    )
    await asyncio.to_thread(safe_json_dump, manifest_path, manifest)

    return {
        "job_id": job_id,
        "status": "completed",
        "results": results,
    }


def _rename_user_assets(old_id: str, new_id: str) -> Dict[str, Any]:
    """Perform filesystem renames for a user."""

    summary = {
        "users_dir": False,
        "quarantine_dirs": 0,
        "purge_requests": False,
        "holistic_results": False,
        "holistic_history": 0,
    }

    old_dir = user_directory(old_id)
    new_dir = user_directory(new_id)
    if not old_dir.exists():
        raise FileNotFoundError(f"User directory missing: {old_dir}")
    if new_dir.exists():
        raise FileExistsError(f"Target user id already exists: {new_id}")

    new_dir.parent.mkdir(parents=True, exist_ok=True)
    old_dir.rename(new_dir)
    summary["users_dir"] = True

    for batch_dir in QUARANTINE_ROOT.glob("*"):
        if not batch_dir.is_dir():
            continue
        candidate = batch_dir / old_id
        if candidate.exists():
            candidate.rename(batch_dir / new_id)
            summary["quarantine_dirs"] += 1

    old_purge = PURGE_REQUESTS_ROOT / old_id
    if old_purge.exists():
        dest = PURGE_REQUESTS_ROOT / new_id
        if dest.exists():
            raise FileExistsError(f"Purge request directory already exists for {new_id}")
        old_purge.rename(dest)
        summary["purge_requests"] = True

    old_result = HOLISTIC_RESULTS_ROOT / f"{old_id}.json"
    if old_result.exists():
        dest = HOLISTIC_RESULTS_ROOT / f"{new_id}.json"
        if dest.exists():
            dest.unlink()
        old_result.rename(dest)
        summary["holistic_results"] = True

    renamed_history = 0
    for history_path in HOLISTIC_HISTORY_ROOT.glob(f"{old_id}_*.json"):
        new_name = history_path.name.replace(f"{old_id}_", f"{new_id}_", 1)
        history_path.rename(HOLISTIC_HISTORY_ROOT / new_name)
        renamed_history += 1
    summary["holistic_history"] = renamed_history

    return summary


class BatchRequest(BaseModel):
    """Payload for holistic batch actions."""

    user_ids: List[str]
    reason: Optional[str] = None

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("user_ids must be a non-empty list.")
        return value


class HolisticRunRequest(BaseModel):
    """Single-user holistic run payload."""

    reason: Optional[str] = None


class RenameRequest(BaseModel):
    """Payload for user rename operations."""

    new_user_id: str
    reason: Optional[str] = None
    confirm: Optional[str] = None


class DeleteUserRequest(BaseModel):
    """Payload for per-user delete/retire operations."""

    mode: Literal["retire", "purge"] = "retire"
    confirm: str
    reason: Optional[str] = None
    grace_days: int = 7


class GrantPermissionRequest(BaseModel):
    namespace: str
    scope: str
    expiry: Optional[str] = None

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("namespace is required")
        return value

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("scope is required")
        return value


class RevokePermissionRequest(BaseModel):
    namespace: Optional[str] = None
    scope: Optional[str] = None
    capability_id: Optional[str] = None


class IssueCapabilityRequest(BaseModel):
    scope: str
    ttl_minutes: int = 30

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("scope is required")
        return value

    @field_validator("ttl_minutes")
    @classmethod
    def validate_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ttl_minutes must be positive")
        return value


class RevokeCapabilityRequest(BaseModel):
    capability_id: str


@router.post("/users/{user_id}/holistic/run")
async def run_holistic_single(user_id: str, request: HolisticRunRequest | None = None) -> Dict[str, Any]:
    """Queue a holistic review for an individual user."""

    payload = request or HolisticRunRequest()
    job = await _queue_holistic_job([user_id], payload.reason)
    job["user_id"] = validate_user_id(user_id)
    return job


@router.get("/users/{user_id}/holistic/latest")
async def latest_holistic(user_id: str, history_limit: int = Query(5, ge=0, le=50)) -> Dict[str, Any]:
    """Return the most recent holistic summary and optional history."""

    sanitized = validate_user_id(user_id)
    latest = await asyncio.to_thread(load_latest_holistic, sanitized)
    history = await asyncio.to_thread(list_holistic_history, sanitized, history_limit)

    return {
        "user_id": sanitized,
        "latest": latest,
        "history": history,
        "history_limit": history_limit,
    }


@router.get("/users/{user_id}/audit")
async def audit_tail(user_id: str, limit: int = Query(10, ge=1, le=100)) -> Dict[str, Any]:
    """Return recent audit entries for a user."""

    sanitized = validate_user_id(user_id)
    entries = await asyncio.to_thread(load_user_audit_entries, sanitized, limit)
    return {"user_id": sanitized, "entries": entries, "limit": limit}


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(user_id: str) -> Dict[str, Any]:
    sanitized = validate_user_id(user_id)
    permissions = await asyncio.to_thread(load_permissions, sanitized)
    capability_tokens = await asyncio.to_thread(load_capability_tokens, sanitized)

    client = get_consent_client()
    consent_caps, consent_error = await asyncio.to_thread(client.list_capabilities, sanitized)

    return {
        "user_id": sanitized,
        "namespaces": permissions.get("namespaces", {}),
        "capabilities": {
            "local": capability_tokens,
            "consent": consent_caps or [],
            "consent_error": consent_error,
        },
    }


@router.post("/users/{user_id}/permissions/grant")
async def grant_permission(user_id: str, request: GrantPermissionRequest) -> Dict[str, Any]:
    sanitized = validate_user_id(user_id)
    permissions = await asyncio.to_thread(load_permissions, sanitized)
    namespaces = permissions.setdefault("namespaces", {})
    scope_map = namespaces.setdefault(request.namespace, {})

    moment = utcnow().isoformat().replace("+00:00", "Z")
    entry = {"granted_at": moment}
    if request.expiry:
        entry["expiry"] = request.expiry

    scope_map[request.scope] = entry
    await asyncio.to_thread(save_permissions, sanitized, permissions)

    append_audit(
        "permission_granted",
        {
            "user_ids": [sanitized],
            "namespace": request.namespace,
            "scope": request.scope,
            "expiry": request.expiry,
        },
    )

    return {
        "status": "granted",
        "user_id": sanitized,
        "namespace": request.namespace,
        "scope": request.scope,
        "permissions": namespaces,
    }


@router.post("/users/{user_id}/permissions/revoke")
async def revoke_permission(user_id: str, request: RevokePermissionRequest) -> Dict[str, Any]:
    sanitized = validate_user_id(user_id)

    if request.capability_id:
        record = await asyncio.to_thread(mark_capability_status, sanitized, request.capability_id, "revoked")
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability not found.")

        client = get_consent_client()
        await asyncio.to_thread(client.revoke_capability, {"capability_id": request.capability_id})

        append_audit(
            "capability_revoked",
            {
                "user_ids": [sanitized],
                "capability_id": request.capability_id,
            },
        )

        return {
            "status": "revoked",
            "user_id": sanitized,
            "capability": record,
        }

    if not request.namespace or not request.scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="namespace and scope are required to revoke a permission.",
        )

    permissions = await asyncio.to_thread(load_permissions, sanitized)
    namespaces = permissions.setdefault("namespaces", {})
    scope_map = namespaces.get(request.namespace)
    if not scope_map or request.scope not in scope_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")

    removed = scope_map.pop(request.scope)
    if not scope_map:
        namespaces.pop(request.namespace, None)

    await asyncio.to_thread(save_permissions, sanitized, permissions)

    append_audit(
        "permission_revoked",
        {
            "user_ids": [sanitized],
            "namespace": request.namespace,
            "scope": request.scope,
        },
    )

    return {
        "status": "revoked",
        "user_id": sanitized,
        "namespace": request.namespace,
        "scope": request.scope,
        "removed": removed,
        "permissions": namespaces,
    }


@router.post("/users/{user_id}/capability/issue")
async def issue_capability(user_id: str, request: IssueCapabilityRequest) -> Dict[str, Any]:
    sanitized = validate_user_id(user_id)
    ttl_seconds = int(request.ttl_minutes * 60)
    capability_id = uuid4().hex
    metadata = {"issued_by": "devx", "capability_id": capability_id}
    token = generate_token(
        agent_id=f"hc_{sanitized}",
        scope=request.scope,
        user_id=sanitized,
        ttl_seconds=ttl_seconds,
        metadata=metadata,
    )

    record = {
        "capability_id": capability_id,
        "scope": request.scope,
        "token": token.token,
        "payload": token.payload,
        "issued_at": token.payload.get("issued_at"),
        "expires_at": token.payload.get("exp"),
        "status": "active",
        "ttl_minutes": request.ttl_minutes,
    }

    tokens = await asyncio.to_thread(load_capability_tokens, sanitized)
    tokens.append(record)
    await asyncio.to_thread(save_capability_tokens, sanitized, tokens)

    append_audit(
        "capability_issued",
        {
            "user_ids": [sanitized],
            "scope": request.scope,
            "capability_id": capability_id,
            "expires_at": record["expires_at"],
        },
    )

    return record


@router.post("/users/{user_id}/capability/revoke")
async def revoke_capability(user_id: str, request: RevokeCapabilityRequest) -> Dict[str, Any]:
    sanitized = validate_user_id(user_id)
    capability_id = request.capability_id

    record = await asyncio.to_thread(mark_capability_status, sanitized, capability_id, "revoked")
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability not found.")

    client = get_consent_client()
    await asyncio.to_thread(client.revoke_capability, {"capability_id": capability_id})

    append_audit(
        "capability_revoked",
        {
            "user_ids": [sanitized],
            "capability_id": capability_id,
        },
    )

    return {
        "status": "revoked",
        "user_id": sanitized,
        "capability": record,
    }


@router.post("/users/{user_id}/rename")
async def rename_user(user_id: str, request: RenameRequest) -> Dict[str, Any]:
    """Rename a user safely, moving associated files."""

    old_id = validate_user_id(user_id)
    new_id = validate_user_id(request.new_user_id)

    if old_id == new_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New user id matches current id.",
        )

    expected = f"RENAME {old_id} TO {new_id}"
    if request.confirm is not None and request.confirm != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Confirmation must match "{expected}".',
        )

    old_dir = user_directory(old_id)
    if not old_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {old_id} not found.")
    if user_directory(new_id).exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {new_id} already exists.",
        )

    try:
        summary = await asyncio.to_thread(_rename_user_assets, old_id, new_id)
    except FileExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to rename user %s -> %s", old_id, new_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Rename failed.",
        ) from exc

    append_audit(
        "user_rename",
        {
            "from": old_id,
            "to": new_id,
            "user_ids": [old_id, new_id],
            "reason": request.reason,
            "summary": summary,
        },
    )

    return {
        "status": "renamed",
        "from": old_id,
        "to": new_id,
        "summary": summary,
    }


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: DeleteUserRequest) -> Dict[str, Any]:
    """Retire or purge a user vault."""

    sanitized = validate_user_id(user_id)
    mode = request.mode or "retire"

    if mode not in {"retire", "purge"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode must be 'retire' or 'purge'.",
        )

    if mode == "retire":
        expected = f"DELETE {sanitized}"
        if request.confirm != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Confirmation must match "{expected}".',
            )
        if request.grace_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="grace_days must be positive.",
            )

        base = user_directory(sanitized)
        if not base.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {sanitized} not found.")

        batch_timestamp = timestamp_for_id()
        quarantine_path = quarantine_directory(batch_timestamp, sanitized)
        if quarantine_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Quarantine path already exists for this user.",
            )

        revoked_count, warnings = await asyncio.to_thread(revoke_user_capabilities, sanitized)
        review_until_dt = utcnow() + timedelta(days=request.grace_days)
        review_until_iso = review_until_dt.isoformat()

        ticket_payload = {
            "user_id": sanitized,
            "requested_at": utcnow().isoformat(),
            "status": "quarantine",
            "review_until": review_until_iso,
            "reason": request.reason,
            "capabilities_revoked": revoked_count,
            "warnings": warnings,
            "job_id": None,
        }
        ticket_name = f"ticket_{batch_timestamp}.json"
        ticket_path = PURGE_REQUESTS_ROOT / sanitized / ticket_name

        try:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            base.rename(quarantine_path)
        except OSError as exc:
            logger.exception("Failed to move %s to quarantine", sanitized)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to move vault to quarantine: {exc}",
            ) from exc

        ticket_payload["quarantine_path"] = str(quarantine_path)
        safe_json_dump(ticket_path, ticket_payload)

        append_audit(
            "user_retire",
            {
                "user_ids": [sanitized],
                "reason": request.reason,
                "review_until": review_until_iso,
                "quarantine_path": str(quarantine_path),
                "ticket_path": str(ticket_path),
                "capabilities_revoked": revoked_count,
                "warnings": warnings,
            },
        )

        return {
            "status": "quarantine",
            "user_id": sanitized,
            "review_until": review_until_iso,
            "quarantine_path": str(quarantine_path),
            "ticket_path": str(ticket_path),
            "capabilities_revoked": revoked_count,
            "warnings": warnings,
        }

    # Purge mode
    expected = f"PURGE {sanitized}"
    if request.confirm != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Confirmation must match "{expected}".',
        )

    ticket_path, ticket = latest_ticket(sanitized)
    if not ticket or ticket.get("status") != "quarantine":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not currently in quarantine.",
        )

    review_until = ticket.get("review_until")
    if review_until:
        review_dt = datetime.fromisoformat(review_until)
        if utcnow() < review_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot purge until after {review_until}.",
            )

    quarantine_path = ticket.get("quarantine_path")
    path = Path(quarantine_path) if quarantine_path else None
    size_before = directory_size_bytes(path) if path and path.exists() else 0

    try:
        if path and path.exists():
            shutil.rmtree(path)
        if ticket_path:
            ticket.update({"status": "purged", "purged_at": utcnow().isoformat()})
            safe_json_dump(ticket_path, ticket)
    except OSError as exc:
        logger.exception("Failed to purge data for %s", sanitized)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purge data: {exc}",
        ) from exc

    append_audit(
        "user_purge",
        {
            "user_ids": [sanitized],
            "bytes_removed": size_before,
            "ticket_path": str(ticket_path) if ticket_path else None,
        },
    )

    return {
        "status": "purged",
        "user_id": sanitized,
        "bytes_removed": size_before,
        "ticket_path": str(ticket_path) if ticket_path else None,
    }
