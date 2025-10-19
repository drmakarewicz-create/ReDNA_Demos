"""Curiosity engine helpers for the demo Core service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

import json
import math
import os

try:
    import yaml
except ImportError:  # pragma: no cover - fallback guard
    yaml = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "core_config" / "trait_schema.yaml"

_CURIOUS_TRUE = {"1", "true", "yes", "on"}
_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_WEIGHT_CACHE: Optional[Dict[str, float]] = None

DEFAULT_WEIGHT = 1.0


def is_enabled() -> bool:
    """Return True when CORE_CURIOSITY_ENABLED env flag is truthy."""

    flag = os.getenv("CORE_CURIOSITY_ENABLED", "").strip().lower()
    return flag in _CURIOUS_TRUE


def _load_schema_payload() -> Dict[str, Any]:
    if yaml is None or not SCHEMA_PATH.exists():
        return {}
    try:
        return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_weights(payload: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    global _WEIGHT_CACHE
    if _WEIGHT_CACHE is not None:
        return _WEIGHT_CACHE

    if payload is None:
        payload = _load_schema_payload()

    weights: Dict[str, float] = {}
    raw_weights = payload.get("curiosity_weights") if isinstance(payload, Mapping) else None
    if isinstance(raw_weights, Mapping):
        for key, value in raw_weights.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(numeric) or numeric <= 0.0:
                continue
            weights[str(key)] = numeric

    _WEIGHT_CACHE = weights
    return weights


def _ensure_catalog() -> Dict[str, Dict[str, Any]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE

    catalog: Dict[str, Dict[str, Any]] = {}
    payload = _load_schema_payload()
    weights = _load_weights(payload)
    containers = payload.get("containers", [])
    for container in containers or []:
        if not isinstance(container, Mapping):
            continue
        container_id = str(container.get("id") or "").strip()
        label = str(container.get("label") or container_id)
        traits = container.get("traits") if isinstance(container.get("traits"), Iterable) else []
        curiosity_weight = float(weights.get(container_id, DEFAULT_WEIGHT) or DEFAULT_WEIGHT)
        if not math.isfinite(curiosity_weight) or curiosity_weight <= 0.0:
            curiosity_weight = DEFAULT_WEIGHT
        for trait in traits:
            if not isinstance(trait, Mapping):
                continue
            trait_id = str(trait.get("id") or "").strip()
            if not trait_id:
                continue
            default_curiosity = trait.get("default_curiosity")
            try:
                default_curiosity_value = float(default_curiosity)
            except (TypeError, ValueError):
                default_curiosity_value = DEFAULT_WEIGHT
            if not math.isfinite(default_curiosity_value) or default_curiosity_value <= 0.0:
                default_curiosity_value = DEFAULT_WEIGHT
            default_ucn = trait.get("default_ucn")
            try:
                default_ucn_value = float(default_ucn)
            except (TypeError, ValueError):
                default_ucn_value = 0.0
            if not math.isfinite(default_ucn_value):
                default_ucn_value = 0.0

            catalog[trait_id] = {
                "container_id": container_id,
                "container_label": label,
                "trait_label": str(trait.get("label") or trait_id),
                "decay": trait.get("decay"),
                "sensitivity": str(trait.get("sensitivity") or "medium").lower(),
                "curiosity_weight": curiosity_weight,
                "default_curiosity": default_curiosity_value,
                "default_ucn": default_ucn_value,
            }

    _CATALOG_CACHE = catalog
    return catalog


def seed_resolved(resolved: Dict[str, Any]) -> bool:
    """Ensure every trait has stubs for curiosity fields."""

    catalog = _ensure_catalog()
    changed = False

    for trait_id, meta in catalog.items():
        entry = resolved.setdefault(trait_id, {})
        if not isinstance(entry, dict):
            entry = {}
            resolved[trait_id] = entry

        if "resolved_value" not in entry:
            entry["resolved_value"] = None
            changed = True
        default_ucn = _safe_float(meta.get("default_ucn"), 0.0)
        if "ucn" not in entry or not isinstance(entry.get("ucn"), (int, float)):
            entry["ucn"] = default_ucn
            changed = True

        default_curiosity = _safe_float(meta.get("default_curiosity"), 1.0)
        if default_curiosity <= 0.0 or not math.isfinite(default_curiosity):
            default_curiosity = 1.0
        if "curiosity" not in entry or not isinstance(entry.get("curiosity"), (int, float)):
            entry["curiosity"] = default_curiosity
            changed = True
        if "last_updated" not in entry:
            entry["last_updated"] = None
            changed = True
        if entry.get("sensitivity") != meta.get("sensitivity"):
            entry["sensitivity"] = meta.get("sensitivity", "medium")
            changed = True
        if "container_id" not in entry:
            entry["container_id"] = meta.get("container_id")
            changed = True
        weight_value = float(meta.get("curiosity_weight", DEFAULT_WEIGHT) or DEFAULT_WEIGHT)
        if not math.isfinite(weight_value) or weight_value <= 0.0:
            weight_value = DEFAULT_WEIGHT
        if entry.get("curiosity_weight") != weight_value:
            entry["curiosity_weight"] = weight_value
            changed = True
        if "curiosity_source" not in entry:
            entry["curiosity_source"] = "unknown"
            changed = True
        if "curiosity_rr" not in entry:
            entry["curiosity_rr"] = None
            changed = True

    return changed


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_unit(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    if numeric > 1.0:
        numeric /= 100.0
    if numeric < 0.0:
        numeric = 0.0
    if numeric > 1.0:
        numeric = 1.0
    return numeric


def _decay_curiosity(value: float) -> float:
    return max(0.0, min(1.0, value * 0.98))


def update_curiosity(
    prior_resolved: Mapping[str, Any],
    resolved: Dict[str, Any],
    touched_traits: Iterable[str],
) -> None:
    """
    Update curiosity and timestamps in-place for the resolved map.

    CORE PRINCIPLE: Curiosity = 1000 - RR (or 1.0 - RR in 0-1 scale)

    This simple formula drives exploration:
    - High RR (rare/certain) → Low curiosity → No need to explore
    - Low RR (common/uncertain) → High curiosity → System requests more data

    The NUANCE is in what the system DOES with different curiosity values,
    not in the calculation itself. This function also handles:
    - Decay over time
    - Boosts for conflicts/contradictions
    - Sensitivity restrictions
    """

    catalog = _ensure_catalog()
    touched: Set[str] = {trait for trait in touched_traits if isinstance(trait, str)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

    for trait_id, entry in list(resolved.items()):
        if not isinstance(entry, dict):
            continue

        meta = catalog.get(trait_id, {})
        prev_entry = prior_resolved.get(trait_id) if isinstance(prior_resolved.get(trait_id), Mapping) else {}

        resolved_value_changed = entry.get("resolved_value") != prev_entry.get("resolved_value")

        sensitivity = str(entry.get("sensitivity") or meta.get("sensitivity") or "medium").lower()
        entry["sensitivity"] = sensitivity
        entry.setdefault("container_id", meta.get("container_id"))

        weight = entry.get("curiosity_weight")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = float(meta.get("curiosity_weight", DEFAULT_WEIGHT) or DEFAULT_WEIGHT)
        if not math.isfinite(weight) or weight <= 0.0:
            weight = DEFAULT_WEIGHT
        entry["curiosity_weight"] = weight

        rr_norm = _normalize_unit(entry.get("rr"))
        if rr_norm is None:
            rr_norm = _normalize_unit(prev_entry.get("rr"))

        ucn_norm = _normalize_unit(entry.get("ucn"))
        if ucn_norm is None:
            ucn_norm = _normalize_unit(prev_entry.get("ucn"))

        # CORE FORMULA: Curiosity = 1000 - RR (normalized to 0-1 here)
        if rr_norm is not None:
            base_curiosity = weight * (1.0 - rr_norm)  # Simple: inverse of rarity
            curiosity_source = "RR"
            entry["curiosity_rr"] = rr_norm
        else:
            # Fallback if RR not available (use UCN as proxy)
            if ucn_norm is None:
                ucn_norm = 1.0
            base_curiosity = weight * (1.0 - ucn_norm)
            curiosity_source = "UCN_FALLBACK"
            entry["curiosity_rr"] = None

        base_curiosity = max(0.0, min(base_curiosity, 1.0))

        prev_curiosity = _normalize_unit(prev_entry.get("curiosity"))
        if prev_curiosity is None:
            prev_curiosity = base_curiosity

        curiosity = base_curiosity
        reasons = entry.get("reasons") if isinstance(entry.get("reasons"), list) else []
        conflict_detected = any(isinstance(reason, str) and "conflict" in reason.lower() for reason in reasons)

        if trait_id in touched:
            entry["last_updated"] = now
            if resolved_value_changed:
                curiosity = min(1.0, max(curiosity, base_curiosity + 0.1))
            if conflict_detected:
                curiosity = min(1.0, max(curiosity, base_curiosity + 0.1))
        else:
            if curiosity_source == "RR" and prev_curiosity is not None:
                curiosity = 0.6 * prev_curiosity + 0.4 * curiosity
            elif prev_curiosity is not None:
                curiosity = max(curiosity, _decay_curiosity(prev_curiosity))
            if "last_updated" not in entry:
                entry["last_updated"] = prev_entry.get("last_updated")

        entry["curiosity_source"] = curiosity_source

        curiosity = max(0.0, min(curiosity, 1.0))

        if sensitivity == "restricted":
            curiosity = min(curiosity, 0.4)

        entry["curiosity"] = round(curiosity, 4)
        entry.setdefault("last_updated", None)


def compute_curiosity(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Compute curiosity deltas for a user.

    Returns list of dicts with 'trait', 'curiosity', 'container_id' keys.
    """
    from . import storage

    paths = storage.ensure_dirs_for_user(user_id)
    resolved_path = paths["udir"] / "resolved.json"

    if not resolved_path.exists():
        return []

    resolved = storage.load_json(resolved_path, default={})
    if not isinstance(resolved, dict):
        return []

    # Use top_traits to get curiosity-ranked list
    top_list = top_traits(resolved, limit=limit)

    # Convert to simpler format expected by plan_composer
    results = []
    for item in top_list:
        results.append({
            "trait": item.get("trait_id", ""),
            "curiosity": item.get("weighted", 0.0),
            "container_id": item.get("container_id", ""),
        })

    return results


def top_traits(resolved: Mapping[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    catalog = _ensure_catalog()
    rows: List[Dict[str, Any]] = []
    for trait_id, payload in resolved.items():
        if not isinstance(payload, Mapping):
            continue
        curiosity = _safe_float(payload.get("curiosity"), -1.0)
        if curiosity <= 0:
            continue
        meta = catalog.get(trait_id, {})
        container_id = payload.get("container_id") or meta.get("container_id")
        if not container_id:
            continue
        weight = payload.get("curiosity_weight")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = float(meta.get("curiosity_weight", DEFAULT_WEIGHT) or DEFAULT_WEIGHT)
        if not math.isfinite(weight) or weight <= 0.0:
            weight = DEFAULT_WEIGHT

        rr_norm = payload.get("curiosity_rr")
        if rr_norm is None:
            rr_norm = _normalize_unit(payload.get("rr"))

        rows.append(
            {
                "container_id": container_id,
                "trait_id": trait_id,
                "container_label": meta.get("container_label"),
                "trait_label": payload.get("trait_label") or meta.get("trait_label"),
                "curiosity": round(curiosity, 4),
                "ucn": _normalize_unit(payload.get("ucn")),
                "resolved_value": payload.get("resolved_value"),
                "last_updated": payload.get("last_updated"),
                "sensitivity": payload.get("sensitivity") or meta.get("sensitivity"),
                "weight": weight,
                "source": payload.get("curiosity_source"),
                "rr": rr_norm,
            }
        )

    rows.sort(key=lambda item: item.get("curiosity", 0.0), reverse=True)
    return rows[:limit]


def snapshot(resolved: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Produce a flat curiosity snapshot used by the public API."""

    catalog = _ensure_catalog()
    rows: List[Dict[str, Any]] = []
    for trait_id, payload in resolved.items():
        if not isinstance(payload, Mapping):
            continue
        curiosity = _safe_float(payload.get("curiosity"), -1.0)
        if curiosity < 0:
            continue
        meta = catalog.get(trait_id, {})
        container_id = payload.get("container_id") or meta.get("container_id")
        if not container_id:
            continue
        weight = payload.get("curiosity_weight")
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = float(meta.get("curiosity_weight", DEFAULT_WEIGHT) or DEFAULT_WEIGHT)
        if not math.isfinite(weight) or weight <= 0.0:
            weight = DEFAULT_WEIGHT

        rr_norm = payload.get("curiosity_rr")
        if rr_norm is None:
            rr_norm = _normalize_unit(payload.get("rr"))

        rows.append(
            {
                "container": container_id,
                "trait_id": trait_id,
                "curiosity": round(curiosity, 4),
                "ucn": _normalize_unit(payload.get("ucn")),
                "weight": weight,
                "source": payload.get("curiosity_source"),
                "rr": rr_norm,
                "resolved_value": payload.get("resolved_value"),
                "last_updated": payload.get("last_updated"),
            }
        )

    rows.sort(key=lambda item: item.get("curiosity", 0.0), reverse=True)
    return rows
