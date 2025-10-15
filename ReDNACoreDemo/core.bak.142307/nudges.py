"""Nudge inbox helpers for the Head Coach UI shells."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from . import storage, policy
from .events import capture

NUDGES_FILENAME = "nudges.json"
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_DISMISSED = "dismissed"


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _ensure_defaults(nudge: Dict[str, Any], *, now: datetime) -> None:
    nudge.setdefault("status", STATUS_PENDING)
    nudge.setdefault("created_ts", _iso(now))
    nudge.setdefault("ttl_minutes", 1440)
    nudge.setdefault("snooze_minutes", 120)


def _nudge_path(user_id: str) -> Any:
    paths = storage.ensure_dirs_for_user(user_id)
    return paths["udir"] / NUDGES_FILENAME


def _load_nudges(user_id: str) -> List[Dict[str, Any]]:
    path = _nudge_path(user_id)
    data = storage.load_json(path, default=[])
    return data if isinstance(data, list) else []


def _save_nudges(user_id: str, nudges: List[Dict[str, Any]]) -> None:
    path = _nudge_path(user_id)
    storage.save_json(path, nudges)


def _prune_expired(nudges: List[Dict[str, Any]], *, now: datetime) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for entry in nudges:
        ttl_minutes = int(entry.get("ttl_minutes", 0) or 0)
        created_ts = entry.get("created_ts")
        if created_ts and ttl_minutes > 0:
            try:
                created_dt = datetime.fromisoformat(created_ts)
            except ValueError:
                created_dt = None
            if created_dt and created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if created_dt and created_dt + timedelta(minutes=ttl_minutes) < now:
                continue
        kept.append(entry)
    return kept


def _policy_for_nudge(nudge: Dict[str, Any], *, now: datetime) -> Dict[str, Any]:
    payload = {
        "now": _iso(now),
        "ttl_minutes": nudge.get("ttl_minutes"),
        "snooze_minutes": nudge.get("snooze_minutes"),
        "last_sent": nudge.get("created_ts"),
        "snoozed_until": nudge.get("snoozed_until"),
        "last_snoozed_at": nudge.get("last_snoozed_at"),
        "rate_cap_per_day": nudge.get("rate_cap_per_day"),
        "sent_count_today": nudge.get("sent_count_today", 0),
        "ab_cohort": nudge.get("cohort"),
        "allowed_cohort": nudge.get("allowed_cohort"),
    }
    policy_result = policy.evaluate_nudge_policy(payload)
    status = nudge.get("status", STATUS_PENDING)

    accept_allowed = policy_result.get("allow", True) and status == STATUS_PENDING
    dismiss_allowed = status == STATUS_PENDING
    undo_allowed = status in {STATUS_ACCEPTED, STATUS_DISMISSED}

    def _entry(allowed: bool, reason: Optional[str]) -> Dict[str, Any]:
        return {"allowed": bool(allowed), "reason": reason if reason else None}

    accept_reason = None if accept_allowed else policy_result.get("reason") or "already_completed"
    dismiss_reason = None if dismiss_allowed else "already_completed"
    undo_reason = None if undo_allowed else "no_previous_action"

    return {
        "accept": _entry(accept_allowed, accept_reason),
        "dismiss": _entry(dismiss_allowed, dismiss_reason),
        "undo": _entry(undo_allowed, undo_reason),
    }


def _view_for_nudge(nudge: Dict[str, Any], *, now: datetime) -> Dict[str, Any]:
    view = dict(nudge)
    view["policy"] = _policy_for_nudge(nudge, now=now)
    return view


def list_for_ui(user_id: str, *, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    nudges = _load_nudges(user_id)
    for entry in nudges:
        _ensure_defaults(entry, now=now_dt)
    filtered = _prune_expired(nudges, now=now_dt)
    if len(filtered) != len(nudges):
        _save_nudges(user_id, filtered)
    return [_view_for_nudge(entry, now=now_dt) for entry in filtered]


def apply_action(
    user_id: str,
    nudge_id: str,
    action: str,
    *,
    now: Optional[datetime] = None,
) -> Tuple[bool, Dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    original = _load_nudges(user_id)
    raw_nudges = _prune_expired(original, now=now_dt)
    if len(raw_nudges) != len(original):
        _save_nudges(user_id, raw_nudges)
    target = None
    for entry in raw_nudges:
        _ensure_defaults(entry, now=now_dt)
        if str(entry.get("id")) == nudge_id:
            target = entry
            break
    if target is None:
        return False, {"reason": "NUDGE_NOT_FOUND"}

    policy_view = _policy_for_nudge(target, now=now_dt)

    action_lower = action.lower()
    metadata = target.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        target["metadata"] = metadata
    if "original_status" not in metadata and target.get("status"):
        metadata["original_status"] = target.get("status")
    metadata["last_action"] = action_lower

    if action_lower == "accept":
        if not policy_view["accept"]["allowed"]:
            return False, {"reason": policy_view["accept"].get("reason") or "accept_blocked", "nudge": _view_for_nudge(target, now=now_dt)}
        target["status"] = STATUS_ACCEPTED
        target["accepted_at"] = _iso(now_dt)
        target.pop("dismissed_at", None)
        target.pop("resumed_at", None)
    elif action_lower == "dismiss":
        if not policy_view["dismiss"]["allowed"]:
            return False, {"reason": policy_view["dismiss"].get("reason") or "dismiss_blocked", "nudge": _view_for_nudge(target, now=now_dt)}
        target["status"] = STATUS_DISMISSED
        target["dismissed_at"] = _iso(now_dt)
        target.pop("accepted_at", None)
        target.pop("resumed_at", None)
    elif action_lower == "undo":
        if not policy_view["undo"]["allowed"]:
            return False, {"reason": policy_view["undo"].get("reason") or "undo_blocked", "nudge": _view_for_nudge(target, now=now_dt)}
        original_status = metadata.get("original_status") if isinstance(metadata, dict) else None
        if isinstance(original_status, str) and original_status:
            target["status"] = original_status
        else:
            target["status"] = STATUS_PENDING
        target["resumed_at"] = _iso(now_dt)
        target.pop("accepted_at", None)
        target.pop("dismissed_at", None)
    else:
        return False, {"reason": "INVALID_ACTION"}

    history = target.setdefault("history", [])
    history.append({"action": action_lower, "ts": _iso(now_dt)})

    _save_nudges(user_id, raw_nudges)

    capture(
        user_id,
        f"nudge_action_{int(now_dt.timestamp() * 1000)}",
        {
            "nudge_id": nudge_id,
            "action": action_lower,
            "status": target.get("status", STATUS_PENDING),
        },
    )

    return True, {"nudge": _view_for_nudge(target, now=now_dt)}


__all__ = ["list_for_ui", "apply_action"]
