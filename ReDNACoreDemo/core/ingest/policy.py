"""
Ingestion policy helpers for evidence tiering and supersession handling.

This module keeps all policy logic pure & deterministic so it can be tested
without touching the rest of the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..priority import trait_importance_for


ISO_FORMATS = ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z")


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    for fmt in ISO_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _source_reliability(source: Optional[str]) -> float:
    if not source:
        return 0.35
    normalized = source.lower()
    if any(token in normalized for token in ("photo", "image", "external", "document")):
        return 0.9
    if any(token in normalized for token in ("lab", "verified", "import")):
        return 0.8
    if any(token in normalized for token in ("coach", "system", "auto")):
        return 0.7
    if any(token in normalized for token in ("chat", "user", "self", "note")):
        return 0.5
    return 0.4


def _values_equal(old_value: Any, new_value: Any) -> bool:
    if old_value == new_value:
        return True
    if isinstance(old_value, dict) and isinstance(new_value, dict):
        return old_value == new_value
    return False


def _trait_importance(trait_id: Optional[str]) -> float:
    if not trait_id:
        return 0.3
    try:
        return float(trait_importance_for(trait_id))
    except Exception:
        return 0.3


def should_persist_raw(
    evidence: Dict[str, Any],
    *,
    existing: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Decide whether raw evidence should be retained and for how long.

    Returns:
        dict with keys:
            tier: "hot" | "warm" | "cold" | "drop"
            ttl_days: int
            reliability: float (0-1)
            importance: float (0-1)
            reason: short text summary
            conflict: bool
    """
    current = now or _now()
    trait_id = evidence.get("trait_id")
    importance = _trait_importance(trait_id)
    reliability = _source_reliability(evidence.get("source"))

    ts = _parse_ts(evidence.get("ts"))
    recency_days: Optional[float] = None
    if ts:
        recency_days = max(0.0, (current - ts).total_seconds() / 86400.0)

    existing_value = None
    existing_status = None
    if isinstance(existing, dict):
        existing_value = existing.get("value")
        existing_status = existing.get("status")

    conflict = False
    if existing_value is not None:
        conflict = not _values_equal(existing_value, evidence.get("value"))

    # Base tier selection
    tier = "warm"
    reason_parts = []

    if conflict:
        tier = "hot"
        reason_parts.append("conflict")
    elif importance >= 0.7 or reliability >= 0.75:
        tier = "hot"
        reason_parts.append("high_signal")
    elif importance <= 0.2 and reliability <= 0.4:
        tier = "cold"
        reason_parts.append("low_priority")

    if recency_days is not None:
        if recency_days > 365 and not conflict:
            tier = "drop"
            reason_parts.append("too_old")
        elif recency_days > 180 and tier == "warm":
            tier = "cold"
            reason_parts.append("aging")

    novelty = conflict or existing_value is None
    if not novelty and tier != "drop":
        # Redundant information can live in cold storage
        tier = "cold"
        reason_parts.append("redundant")

    if existing_status in {"contradicted", "warming"} and novelty:
        tier = "hot"
        reason_parts.append("pending_resolution")

    ttl_map = {
        "hot": 365,
        "warm": 180,
        "cold": 60,
        "drop": 0,
    }
    ttl_days = ttl_map[tier]

    if not reason_parts:
        reason_parts.append("baseline")

    return {
        "tier": tier,
        "ttl_days": ttl_days,
        "reliability": reliability,
        "importance": importance,
        "reason": ",".join(sorted(set(reason_parts))),
        "conflict": conflict,
        "recency_days": recency_days,
        "novelty": novelty,
    }


@dataclass(frozen=True)
class SupersessionDecision:
    action: str
    new_status: str
    old_status: Optional[str]
    ucn_multiplier: float
    last_confirmed_at: Optional[str]
    history_entry: Optional[Dict[str, Any]]
    context: Dict[str, Any]


def apply_supersession(
    trait_path: str,
    old_evt: Optional[Dict[str, Any]],
    new_evt: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> SupersessionDecision:
    """
    Determine how conflicting evidence should update resolved state.
    """
    current_ts = now or _now()
    old_value = old_evt.get("value") if isinstance(old_evt, dict) else None
    old_status = old_evt.get("status") if isinstance(old_evt, dict) else None
    new_value = new_evt.get("value")
    reliability = float(new_evt.get("_reliability", _source_reliability(new_evt.get("source"))))

    same_value = _values_equal(old_value, new_value)
    history_entry: Optional[Dict[str, Any]] = None
    last_confirmed_at: Optional[str] = None
    context: Dict[str, Any] = {
        "trait": trait_path,
        "reliability": reliability,
    }

    if not old_evt or old_value is None:
        # New trait
        status = "stable" if reliability >= 0.6 else "warming"
        if status == "stable":
            last_confirmed_at = current_ts.isoformat().replace("+00:00", "Z")
        return SupersessionDecision(
            action="new",
            new_status=status,
            old_status=None,
            ucn_multiplier=1.0 if status == "stable" else 0.85,
            last_confirmed_at=last_confirmed_at,
            history_entry=None,
            context=context,
        )

    if same_value:
        # Reinforcement
        if reliability >= 0.6:
            last_confirmed_at = current_ts.isoformat().replace("+00:00", "Z")
            status = "stable"
            multiplier = 1.05
        else:
            status = old_status or "stable"
            multiplier = 1.0
        return SupersessionDecision(
            action="reinforced",
            new_status=status,
            old_status=old_status,
            ucn_multiplier=multiplier,
            last_confirmed_at=last_confirmed_at,
            history_entry=None,
            context=context,
        )

    # Values differ
    history_entry = {
        "value": old_value,
        "status": "superseded",
        "timestamp": current_ts.isoformat().replace("+00:00", "Z"),
        "previous_status": old_status or "stable",
    }

    if reliability >= 0.75:
        new_status = "superseded"
        last_confirmed_at = current_ts.isoformat().replace("+00:00", "Z")
        multiplier = 0.95
        action = "superseded"
        context["resolution"] = "confirmed"
    else:
        new_status = "contradicted"
        multiplier = 0.6
        action = "contradiction"
        context["resolution"] = "pendingConfirmation"

    history_entry["action"] = action

    return SupersessionDecision(
        action=action,
        new_status=new_status,
        old_status="superseded",
        ucn_multiplier=multiplier,
        last_confirmed_at=last_confirmed_at,
        history_entry=history_entry,
        context=context,
    )


def migrate_trait_record(trait: Dict[str, Any], *, default_ts: Optional[str] = None) -> None:
    """
    Ensure a resolved trait record carries the new policy fields.
    """
    if not isinstance(trait, dict):
        return
    trait.setdefault("status", "stable")
    ts = trait.get("last_updated") or default_ts or _now().isoformat().replace("+00:00", "Z")
    trait.setdefault("last_confirmed_at", ts if trait["status"] == "stable" else None)
    history = trait.get("history")
    if not isinstance(history, list):
        trait["history"] = []
