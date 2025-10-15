"""Governance utilities for dormancy detection, sensitive gating, and rollback."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROLLBACK_FILENAME = "rollback_manifest.json"
_DORMANCY_DAYS = int(os.getenv("GOVERNANCE_DORMANCY_DAYS", "30"))
_SENSITIVE_FLAG = "sensitive"
_CONSENT_FLAG = "consent_granted"


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    token = ts
    if token.endswith("Z"):
        token = token[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enforce_sensitive_writes(resolved: Dict[str, Any]) -> None:
    for trait, payload in resolved.items():
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata") or {}
        sensitive = payload.get(_SENSITIVE_FLAG) or metadata.get(_SENSITIVE_FLAG)
        if sensitive and not metadata.get(_CONSENT_FLAG) and not payload.get(_CONSENT_FLAG):
            raise PermissionError(f"Consent required for sensitive trait '{trait}'")


def update_dormancy_flags(resolved: Dict[str, Any], *, now: Optional[datetime] = None) -> None:
    if not resolved:
        return
    now_dt = now or datetime.now(timezone.utc)
    threshold = timedelta(days=max(_DORMANCY_DAYS, 1))
    for payload in resolved.values():
        if not isinstance(payload, dict):
            continue
        metadata = payload.setdefault("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        last_observed = payload.get("last_observed")
        observed_ts = _parse_iso(last_observed)
        if observed_ts and now_dt - observed_ts > threshold:
            metadata["dormant"] = True
            metadata["dormant_since"] = observed_ts.isoformat()
        else:
            metadata.pop("dormant", None)
            metadata.pop("dormant_since", None)


def has_material_state(resolved: Dict[str, Any], evidence: Dict[str, Any], observations: Dict[str, Any]) -> bool:
    if resolved:
        return True
    if evidence and evidence.get("items"):
        return True
    if observations and observations.get("items"):
        return True
    return False


def build_rollback_manifest(
    resolved: Dict[str, Any],
    evidence: Dict[str, Any],
    observations: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "captured_at": iso_now(),
        "resolved": resolved,
        "evidence": evidence,
        "observations": observations,
    }


def write_rollback_manifest(path: Path, manifest: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))


def read_rollback_manifest(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


__all__ = [
    "ROLLBACK_FILENAME",
    "enforce_sensitive_writes",
    "update_dormancy_flags",
    "has_material_state",
    "build_rollback_manifest",
    "write_rollback_manifest",
    "read_rollback_manifest",
]
