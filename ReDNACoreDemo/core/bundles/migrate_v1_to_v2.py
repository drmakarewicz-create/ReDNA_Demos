"""Migration helpers from bundle v1 -> v2."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from . import CURRENT_SCHEMA, CURRENT_VERSION, iso_now


def migrate(bundle: Dict[str, Any]) -> Dict[str, Any]:
    migrated = deepcopy(bundle)
    meta = dict(migrated.get("meta") or {})
    previous_version = str(meta.get("version") or "1.0")

    meta["migrated_from"] = previous_version
    meta["version"] = CURRENT_VERSION
    meta.setdefault("schema", CURRENT_SCHEMA)
    meta.setdefault("migrated_at", iso_now())
    migrated["meta"] = meta

    resolved = migrated.get("resolved")
    if isinstance(resolved, dict):
        for trait, payload in resolved.items():
            if isinstance(payload, dict):
                payload.setdefault("reasons", [])
                payload.setdefault("ucn", payload.get("ucn", 0))
    migrated.setdefault("evidence", {"items": []})
    obs = migrated.get("observations")
    if not isinstance(obs, dict):
        migrated["observations"] = {"items": [], "by_trait": {}}
    else:
        obs.setdefault("items", [])
        obs.setdefault("by_trait", {})

    return migrated


__all__ = ["migrate"]
