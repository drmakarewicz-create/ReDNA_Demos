from __future__ import annotations

"""
Capability tokens for Agentic Head Coach operations.

Tokens are compact HMAC-signed envelopes that encode the agent identifier,
authorized scope, and expiration timestamp. They are validated by middleware
before executing sensitive actions.
"""

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Mapping
from uuid import uuid4

from .storage import CORE_DATA_ROOT


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(ts: datetime) -> str:
    return ts.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _decode_base64url(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


AGENT_CAPABILITY_SECRET = os.getenv("AGENT_CAPABILITY_SECRET", "dev-agent-capability-secret")
AUDIT_DIR = CORE_DATA_ROOT / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG = AUDIT_DIR / "agent_capability_failures.jsonl"
CAPABILITY_STORE_ROOT = CORE_DATA_ROOT / "capability_tokens"
CAPABILITY_STORE_ROOT.mkdir(parents=True, exist_ok=True)
CONSENT_STORE_ROOT = CORE_DATA_ROOT / "consent"
CONSENT_STORE_ROOT.mkdir(parents=True, exist_ok=True)
TELEMETRY_DIR = CORE_DATA_ROOT / "telemetry" / "agents"
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
TELEMETRY_LOG = TELEMETRY_DIR / "agent_activity.jsonl"


class CapabilityError(Exception):
    """Raised when a capability token is invalid or unauthorized."""


class ConsentDeniedError(Exception):
    """Raised when consent validation fails."""


@dataclass
class CapabilityToken:
    token: str
    payload: Dict[str, Any]


def _sign(body: str) -> str:
    digest = hmac.new(AGENT_CAPABILITY_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return _base64url(digest)


def generate_token(
    *,
    agent_id: str,
    scope: str,
    user_id: Optional[str] = None,
    ttl_seconds: int = 3600,
    metadata: Optional[Dict[str, Any]] = None,
) -> CapabilityToken:
    """
    Generate a signed capability token for an agent action.
    """
    now = _utc_now()
    expires = now + timedelta(seconds=int(ttl_seconds))

    payload: Dict[str, Any] = {
        "agent": agent_id,
        "scope": scope,
        "exp": _utc_iso(expires),
        "issued_at": _utc_iso(now),
    }
    if user_id:
        payload["user_id"] = user_id
    if metadata:
        payload["metadata"] = metadata

    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    token = f"{_base64url(serialized.encode('utf-8'))}.{_sign(serialized)}"
    return CapabilityToken(token=token, payload=payload)


def _log_audit(event: Dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("ts", _utc_iso(_utc_now()))
    with AUDIT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def audit_event(event: str, payload: Dict[str, Any]) -> None:
    """
    Append an event to the unified agent activity log.
    """
    entry = dict(payload)
    entry["event"] = event
    entry.setdefault("timestamp", _utc_iso(_utc_now()))
    line = json.dumps(entry, ensure_ascii=False)
    with TELEMETRY_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def verify_token(token: str, *, required_scope: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate a capability token.
    """
    if not token or "." not in token:
        _log_audit({"event": "capability_invalid_format", "user_id": user_id})
        raise CapabilityError("Malformed capability token")

    payload_part, signature_part = token.split(".", 1)
    try:
        body = _decode_base64url(payload_part).decode("utf-8")
    except Exception as exc:  # pragma: no cover - corrupted input
        _log_audit({"event": "capability_decode_error", "detail": str(exc), "user_id": user_id})
        raise CapabilityError("Invalid capability encoding") from exc

    expected_signature = _sign(body)
    if not hmac.compare_digest(signature_part, expected_signature):
        _log_audit({"event": "capability_bad_signature", "user_id": user_id})
        raise CapabilityError("Capability signature mismatch")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        _log_audit({"event": "capability_bad_json", "detail": str(exc), "user_id": user_id})
        raise CapabilityError("Capability payload invalid") from exc

    exp_text = payload.get("exp")
    try:
        exp_dt = datetime.fromisoformat(exp_text.replace("Z", "+00:00"))
    except Exception as exc:
        _log_audit({"event": "capability_bad_exp", "detail": str(exc), "payload": payload, "user_id": user_id})
        raise CapabilityError("Capability missing expiration") from exc

    if exp_dt <= _utc_now():
        _log_audit({"event": "capability_expired", "payload": payload, "user_id": user_id})
        raise CapabilityError("Capability token expired")

    if required_scope and payload.get("scope") != required_scope:
        _log_audit({"event": "capability_scope_mismatch", "payload": payload, "required_scope": required_scope, "user_id": user_id})
        raise CapabilityError("Capability scope denied")

    if user_id and payload.get("user_id") not in (None, user_id):
        _log_audit(
            {
                "event": "capability_user_mismatch",
                "payload": payload,
                "presented_user": user_id,
            }
        )
        raise CapabilityError("Capability user mismatch")

    return payload


def _capability_store_path(user_id: str) -> Path:
    sanitized = str(user_id or "").strip()
    if not sanitized:
        raise ValueError("user_id is required")
    return CAPABILITY_STORE_ROOT / f"{sanitized}.json"


def load_capability_records(user_id: str) -> List[Dict[str, Any]]:
    path = _capability_store_path(user_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [dict(record) for record in payload if isinstance(record, dict)]
    return []


def save_capability_records(user_id: str, records: Sequence[Dict[str, Any]]) -> None:
    path = _capability_store_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = [dict(record) for record in records]
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def issue_capability_record(
    user_id: str,
    scope: str,
    *,
    ttl_minutes: int = 15,
    issued_by: str = "devx",
    metadata: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Issue and persist a capability token record for a Head Coach agent preset.
    """
    if ttl_minutes <= 0:
        raise ValueError("ttl_minutes must be positive")

    capability_id = uuid4().hex
    record_metadata = dict(metadata or {})
    record_metadata.setdefault("issued_by", issued_by)
    record_metadata.setdefault("capability_id", capability_id)

    token = generate_token(
        agent_id=agent_id or f"hc_{user_id}",
        scope=scope,
        user_id=user_id,
        ttl_seconds=int(ttl_minutes * 60),
        metadata=record_metadata,
    )

    record = {
        "capability_id": capability_id,
        "scope": scope,
        "token": token.token,
        "payload": token.payload,
        "issued_at": token.payload.get("issued_at"),
        "expires_at": token.payload.get("exp"),
        "status": "active",
        "ttl_minutes": ttl_minutes,
        "metadata": record_metadata,
    }

    existing = load_capability_records(user_id)
    existing.append(record)
    save_capability_records(user_id, existing)
    return record


def revoke_capabilities(
    user_id: str,
    *,
    capability_ids: Optional[Sequence[str]] = None,
    reason: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Mark capability records as revoked. Returns the updated records.
    """
    records = load_capability_records(user_id)
    if not records:
        return []

    target_ids = {cap_id for cap_id in capability_ids} if capability_ids else None
    now_iso = _utc_iso(_utc_now())
    revoked: List[Dict[str, Any]] = []

    for record in records:
        cap_id = record.get("capability_id")
        if target_ids is not None and cap_id not in target_ids:
            continue
        if record.get("status") == "revoked":
            continue
        record["status"] = "revoked"
        record["revoked_at"] = now_iso
        if reason:
            record.setdefault("revoke_reason", reason)
        revoked.append(dict(record))

    if revoked:
        save_capability_records(user_id, records)
    return revoked


def _consent_path(user_id: str) -> Path:
    sanitized = str(user_id or "").strip()
    if not sanitized:
        raise ValueError("user_id is required")
    return CONSENT_STORE_ROOT / f"{sanitized}.json"


def _load_consent_namespaces(user_id: str) -> Dict[str, List[str]]:
    """
    Load static consent namespace grants for a user.
    """
    path = _consent_path(user_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {key: list(value) for key, value in data.items() if isinstance(value, list)}
    except json.JSONDecodeError:
        pass
    return {}


def ensure_consent(user_id: str, namespaces: Sequence[str], *, action: str = "read") -> None:
    """
    Validate that the user has granted consent for the requested namespaces.

    Consent data is loaded from CORE_DATA_ROOT/consent/<id>.json and may be
    monkeypatched in tests. If namespaces are missing, raises ConsentDeniedError.
    """
    if not namespaces:
        return

    grants = _load_consent_namespaces(user_id)
    allowed = set(grants.get(f"{action}", []) + grants.get("any", []))
    missing = [ns for ns in namespaces if ns not in allowed]
    if missing:
        audit_event(
            "consent_denied",
            {
                "user_id": user_id,
                "requested_namespaces": list(namespaces),
                "action": action,
                "missing": missing,
            },
        )
        raise ConsentDeniedError(f"Missing consent for {missing}")


def require_capability_header(headers: Mapping[str, str], *, user_id: str, scope: str) -> Dict[str, Any]:
    """
    Validate capability token from request headers and return payload.
    """
    token = headers.get("x-agent-capability")
    payload = verify_token(token or "", required_scope=scope, user_id=user_id)
    return payload


def _active_capability(records: Sequence[Dict[str, Any]], scope: str) -> Optional[Dict[str, Any]]:
    now = _utc_now()
    for record in records:
        if record.get("scope") != scope:
            continue
        if record.get("status") != "active":
            continue
        exp = record.get("expires_at")
        if not exp:
            continue
        try:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        except Exception:
            continue
        if exp_dt > now:
            return record
    return None


def ensure_capability_available(user_id: str, scope: str) -> None:
    records = load_capability_records(user_id)
    if _active_capability(records, scope) is not None:
        return
    raise CapabilityError(f"Capability {scope} missing or expired")
