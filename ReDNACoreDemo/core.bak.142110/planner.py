"""Curiosity gap planner and ask queue persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Mapping, Tuple
import hashlib

from . import storage
from .events import capture

_DEFAULT_TTL_MINUTES = 1440  # 24h
_DEFAULT_SNOOZE_MINUTES = 120
_STATUS_PENDING = "pending"
_STATUS_APPROVED = "approved"
_STATUS_SNOOZED = "snoozed"
_STATUS_SKIPPED = "skipped"
_SENSITIVE_TOKENS = ("relationship", "family", "sexual", "medical", "health")


@dataclass
class Gap:
    container: str
    gap: str
    confidence: float


@dataclass
class Ask:
    id: str
    container: str
    gap: str
    confidence: float
    ask_type: str
    phrasing_stub: str
    sensitivity: bool
    created_at: str
    expires_at: str
    next_available_at: str
    ttl_minutes: int = _DEFAULT_TTL_MINUTES
    snooze_minutes: int = _DEFAULT_SNOOZE_MINUTES
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "container": self.container,
            "gap": self.gap,
            "confidence": self.confidence,
            "ask_type": self.ask_type,
            "phrasing_stub": self.phrasing_stub,
            "sensitivity": self.sensitivity,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "next_available_at": self.next_available_at,
            "ttl_minutes": self.ttl_minutes,
            "snooze_minutes": self.snooze_minutes,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


def _now(ts: Optional[str] = None) -> datetime:
    if ts:
        return datetime.fromisoformat(ts)
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _make_id(container: str, gap: str) -> str:
    token = f"{container}|{gap}".encode("utf-8")
    return hashlib.sha1(token).hexdigest()


def _ask_type_from_confidence(confidence: float) -> str:
    if confidence >= 0.7:
        return "action"
    if confidence >= 0.4:
        return "confirm"
    return "explore"


def _phrasing_stub(container: str, gap: str, ask_type: str) -> str:
    human_gap = gap.replace("_", " ").replace(".", " → ")
    if ask_type == "action":
        return f"Invite user to act on {human_gap} ({container})."
    if ask_type == "confirm":
        return f"Check readiness around {human_gap} in {container}."
    return f"Open question about {human_gap} ({container})."


def _is_sensitive(container: str, gap: str) -> bool:
    text = f"{container}.{gap}".lower()
    return any(token in text for token in _SENSITIVE_TOKENS)


def _load_queue(user_id: str) -> List[Dict[str, Any]]:
    paths = storage.ensure_dirs_for_user(user_id)
    queue_path = paths["udir"] / storage.ASK_QUEUE_FILENAME
    raw = storage.load_json(queue_path, default=[])
    return raw if isinstance(raw, list) else []


def _save_queue(user_id: str, queue: List[Dict[str, Any]]) -> None:
    paths = storage.ensure_dirs_for_user(user_id)
    queue_path = paths["udir"] / storage.ASK_QUEUE_FILENAME
    storage.save_json(queue_path, queue)


def _prune(queue: List[Dict[str, Any]], *, now: datetime) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    for item in queue:
        expires = item.get("expires_at")
        if expires:
            try:
                if _now(expires) < now:
                    continue
            except ValueError:
                continue
        item.setdefault("status", _STATUS_PENDING)
        kept.append(item)
    return kept


def _dedupe(queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for item in queue:
        key = item.get("id")
        if not key:
            continue
        current = seen.get(key)
        if current is None or item.get("confidence", 0) > current.get("confidence", 0):
            seen[key] = item
    return list(seen.values())


def _build_ask(gap: Gap, *, now: datetime) -> Ask:
    ask_type = _ask_type_from_confidence(gap.confidence)
    phrasing = _phrasing_stub(gap.container, gap.gap, ask_type)
    sensitivity = _is_sensitive(gap.container, gap.gap)
    identifier = _make_id(gap.container, gap.gap)
    expires_at = now + timedelta(minutes=_DEFAULT_TTL_MINUTES)
    return Ask(
        id=identifier,
        container=gap.container,
        gap=gap.gap,
        confidence=float(gap.confidence),
        ask_type=ask_type,
        phrasing_stub=phrasing,
        sensitivity=sensitivity,
        created_at=_iso(now),
        expires_at=_iso(expires_at),
        next_available_at=_iso(now),
        metadata={"source": "curiosity_planner"},
    )


def plan_gaps(user_id: str, gaps: Sequence[Mapping[str, Any]], *, now: Optional[datetime] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Update the ask queue for ``user_id`` based on ranked curiosity gaps.

    Existing asks are pruned by TTL and deduplicated, then new asks are added
    for the top ``limit`` gaps that are not already pending.
    """

    now_dt = now or datetime.now(timezone.utc)
    queue = _prune(_load_queue(user_id), now=now_dt)
    queue = _dedupe(queue)

    ranked = sorted(
        (
            Gap(
                container=str(item.get("container", "")),
                gap=str(item.get("gap", "")),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in gaps
            if item and item.get("container") and item.get("gap")
        ),
        key=lambda g: g.confidence,
        reverse=True,
    )

    added = 0
    for gap in ranked:
        if added >= limit:
            break
        ask_id = _make_id(gap.container, gap.gap)
        existing = next((item for item in queue if item.get("id") == ask_id), None)
        if existing:
            # Refresh confidence and metadata but keep original created timestamp.
            existing["confidence"] = float(gap.confidence)
            existing.setdefault("metadata", {})["last_refreshed"] = _iso(now_dt)
            continue
        ask = _build_ask(gap, now=now_dt)
        queue.append(ask.as_dict())
        added += 1

    queue = sorted(queue, key=lambda item: item.get("confidence", 0.0), reverse=True)
    _save_queue(user_id, queue)
    return queue


def _policy_entry(*, allowed: bool, reason: Optional[str]) -> Dict[str, Any]:
    return {"allowed": bool(allowed), "reason": reason or None}


def _policy_for_ask(ask: Dict[str, Any], *, now: datetime) -> Dict[str, Any]:
    status = ask.get("status") or _STATUS_PENDING
    next_available_at = ask.get("next_available_at")
    snooze_reason = None
    approve_allowed = status not in {_STATUS_APPROVED, _STATUS_SKIPPED}
    skip_allowed = status != _STATUS_SKIPPED

    next_available_dt: Optional[datetime] = None
    if next_available_at:
        try:
            next_available_dt = _now(next_available_at)
        except ValueError:
            next_available_dt = None

    if status == _STATUS_APPROVED:
        approve_allowed = False
    if status == _STATUS_SKIPPED:
        approve_allowed = False

    snooze_allowed = True
    if next_available_dt and next_available_dt > now:
        snooze_allowed = False
        delta = int((next_available_dt - now).total_seconds() // 60)
        snooze_reason = f"Available again in {max(delta, 1)} minutes"
    if status in {_STATUS_APPROVED, _STATUS_SKIPPED}:
        snooze_allowed = False
        if status == _STATUS_APPROVED:
            snooze_reason = "Ask already approved"
        elif status == _STATUS_SKIPPED:
            snooze_reason = "Ask skipped"

    approve_reason = None if approve_allowed else "Ask already completed"
    skip_reason = None if skip_allowed else "Ask already skipped"

    return {
        "approve": _policy_entry(allowed=approve_allowed, reason=approve_reason),
        "snooze": _policy_entry(allowed=snooze_allowed, reason=snooze_reason),
        "skip": _policy_entry(allowed=skip_allowed, reason=skip_reason),
    }


def _normalise_queue(user_id: str, *, now: datetime) -> List[Dict[str, Any]]:
    queue = _load_queue(user_id)
    filtered = _prune(queue, now=now)
    changed = len(filtered) != len(queue)
    for item in filtered:
        status = item.get("status") or _STATUS_PENDING
        next_available = item.get("next_available_at")
        item["status"] = status
        if not next_available:
            next_available = _iso(now)
            item["next_available_at"] = next_available
        else:
            try:
                resume_dt = _now(next_available)
            except ValueError:
                resume_dt = None
            if status == _STATUS_SNOOZED and resume_dt and resume_dt <= now:
                item["status"] = _STATUS_PENDING
        if item.get("status") == _STATUS_PENDING:
            item.pop("snoozed_until", None)
        item.setdefault("snooze_minutes", _DEFAULT_SNOOZE_MINUTES)
    if changed:
        _save_queue(user_id, filtered)
    return sorted(filtered, key=lambda item: item.get("confidence", 0.0), reverse=True)


def _view_for_ask(ask: Dict[str, Any], *, now: datetime) -> Dict[str, Any]:
    view = dict(ask)
    view["status"] = ask.get("status", _STATUS_PENDING)
    view["policy"] = _policy_for_ask(ask, now=now)
    view["default_snooze_minutes"] = ask.get("snooze_minutes", _DEFAULT_SNOOZE_MINUTES)
    return view


def list_for_ui(user_id: str, *, limit: int = 5, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    queue = _normalise_queue(user_id, now=now_dt)
    result = [_view_for_ask(ask, now=now_dt) for ask in queue]
    return result[:limit] if limit else result


def _append_history(ask: Dict[str, Any], *, action: str, now: datetime, meta: Optional[Dict[str, Any]] = None) -> None:
    history = ask.setdefault("history", [])
    entry = {"action": action, "ts": _iso(now)}
    if meta:
        entry.update(meta)
    history.append(entry)


def apply_action(
    user_id: str,
    ask_id: str,
    action: str,
    *,
    snooze_minutes: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Tuple[bool, Dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    queue = _normalise_queue(user_id, now=now_dt)
    ask = next((item for item in queue if item.get("id") == ask_id), None)
    if not ask:
        return False, {"reason": "ASK_NOT_FOUND"}

    action_lower = action.lower()
    policy = _policy_for_ask(ask, now=now_dt)

    if action_lower == "approve":
        if not policy["approve"]["allowed"]:
            return False, {"reason": policy["approve"].get("reason") or "Approve blocked", "ask": _view_for_ask(ask, now=now_dt)}
        ask["status"] = _STATUS_APPROVED
        ask["completed_at"] = _iso(now_dt)
        _append_history(ask, action="approve", now=now_dt)
    elif action_lower == "snooze":
        if not policy["snooze"]["allowed"]:
            return False, {"reason": policy["snooze"].get("reason") or "Snooze blocked", "ask": _view_for_ask(ask, now=now_dt)}
        minutes = snooze_minutes or ask.get("snooze_minutes") or _DEFAULT_SNOOZE_MINUTES
        minutes = max(int(minutes), 1)
        resume = now_dt + timedelta(minutes=minutes)
        ask["next_available_at"] = _iso(resume)
        ask["status"] = _STATUS_SNOOZED
        ask["snoozed_until"] = ask["next_available_at"]
        _append_history(ask, action="snooze", now=now_dt, meta={"minutes": minutes})
    elif action_lower == "skip":
        if not policy["skip"]["allowed"]:
            return False, {"reason": policy["skip"].get("reason") or "Skip blocked", "ask": _view_for_ask(ask, now=now_dt)}
        ask["status"] = _STATUS_SKIPPED
        ask["skipped_at"] = _iso(now_dt)
        _append_history(ask, action="skip", now=now_dt)
    else:
        return False, {"reason": "INVALID_ACTION"}

    _save_queue(user_id, queue)

    capture(
        user_id,
        f"ask_action_{int(now_dt.timestamp() * 1000)}",
        {
            "ask_id": ask_id,
            "action": action_lower,
            "status": ask.get("status", _STATUS_PENDING),
            "snooze_until": ask.get("next_available_at"),
        },
    )

    ask_view = _view_for_ask(ask, now=now_dt)
    return True, {"ask": ask_view}


def load_active_asks(user_id: str, *, now: Optional[datetime] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    now_dt = now or datetime.now(timezone.utc)
    queue = _prune(_load_queue(user_id), now=now_dt)
    queue = _dedupe(queue)
    active: List[Dict[str, Any]] = []
    for item in queue:
        available = item.get("next_available_at")
        if available and _now(available) > now_dt:
            continue
        active.append(item)
    active = sorted(active, key=lambda item: item.get("confidence", 0.0), reverse=True)
    if limit is not None:
        active = active[:limit]
    return active


def snooze(user_id: str, ask_id: str, *, minutes: Optional[int] = None, now: Optional[datetime] = None) -> bool:
    queue = _load_queue(user_id)
    if not queue:
        return False
    now_dt = now or datetime.now(timezone.utc)
    duration = minutes if minutes is not None else _DEFAULT_SNOOZE_MINUTES
    changed = False
    for item in queue:
        if item.get("id") != ask_id:
            continue
        next_at = now_dt + timedelta(minutes=duration)
        item["next_available_at"] = _iso(next_at)
        item.setdefault("metadata", {})["snoozed_at"] = _iso(now_dt)
        changed = True
        break
    if changed:
        _save_queue(user_id, queue)
    return changed


def remove(user_id: str, ask_id: str) -> bool:
    queue = _load_queue(user_id)
    filtered = [item for item in queue if item.get("id") != ask_id]
    if len(filtered) == len(queue):
        return False
    _save_queue(user_id, filtered)
    return True


def queue_summary(user_id: str) -> Dict[str, Any]:
    queue = _load_queue(user_id)
    return {
        "total": len(queue),
        "active": len(load_active_asks(user_id)),
    }


def add_demo_ask(
    user_id: str,
    *,
    title: str,
    summary: Optional[str] = None,
    persona: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Insert a lightweight demo ask into the queue for quick UI experiments."""

    trimmed_user = user_id.strip()
    if not trimmed_user:
        raise ValueError("user_id is required")

    title_text = title.strip()
    if not title_text:
        raise ValueError("title is required")

    now_dt = datetime.now(timezone.utc)
    normalized_persona = (persona or "head_coach").strip().lower().replace(" ", "_") or "head_coach"

    gap_seed = title_text.lower().strip().replace(" ", "_").replace("__", "_")
    if not gap_seed:
        gap_seed = f"focus_{int(now_dt.timestamp())}"

    identifier_seed = f"{normalized_persona}|{gap_seed}|{int(now_dt.timestamp() * 1000)}"
    identifier = hashlib.sha1(identifier_seed.encode("utf-8")).hexdigest()

    if confidence is None:
        # Bias towards mid-confidence to keep policy actions available.
        effective_confidence = 0.55
    else:
        try:
            effective_confidence = float(confidence)
        except (TypeError, ValueError):
            effective_confidence = 0.55
    effective_confidence = max(0.05, min(0.95, effective_confidence))

    ask_type = _ask_type_from_confidence(effective_confidence)
    phrasing = summary.strip() if isinstance(summary, str) and summary.strip() else _phrasing_stub(normalized_persona, gap_seed, ask_type)

    ask = Ask(
        id=identifier,
        container=normalized_persona,
        gap=gap_seed,
        confidence=effective_confidence,
        ask_type=ask_type,
        phrasing_stub=phrasing,
        sensitivity=_is_sensitive(normalized_persona, gap_seed),
        created_at=_iso(now_dt),
        expires_at=_iso(now_dt + timedelta(minutes=_DEFAULT_TTL_MINUTES)),
        next_available_at=_iso(now_dt),
        metadata={
            "demo": True,
            "title": title_text,
            "summary": phrasing,
            "persona": normalized_persona,
        },
    )

    queue = _load_queue(trimmed_user)
    queue.insert(0, ask.as_dict())
    _save_queue(trimmed_user, queue)

    capture(
        trimmed_user,
        f"ask_demo_{identifier}",
        {"title": title_text, "persona": normalized_persona, "confidence": round(effective_confidence, 2)},
    )

    ask_view = _view_for_ask(queue[0], now=now_dt) if queue else ask.as_dict()
    return ask_view
