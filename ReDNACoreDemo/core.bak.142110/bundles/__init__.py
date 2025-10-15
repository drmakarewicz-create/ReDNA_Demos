"""Bundle schema helpers and migration entry points."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

CURRENT_VERSION = "2.0.0"
CURRENT_SCHEMA = "redna.bundle/2.0"
LEGACY_V1 = {"1.0", "1.0.0"}


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(payload: Dict[str, Any]) -> Dict[str, Any]:
    meta = payload.get("meta") or {}
    version = str(meta.get("version") or "1.0")
    if version in LEGACY_V1:
        from . import migrate_v1_to_v2

        return migrate_v1_to_v2.migrate(payload)
    if version == CURRENT_VERSION:
        return payload
    raise ValueError(f"Unsupported bundle version: {version}")


__all__ = ["CURRENT_VERSION", "CURRENT_SCHEMA", "migrate", "iso_now"]
