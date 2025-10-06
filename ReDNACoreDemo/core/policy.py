"""Inbox/nudge policy evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

_ISO_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in _ISO_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class PolicyInput:
    now: datetime
    last_sent: Optional[datetime]
    ttl_minutes: int
    snooze_minutes: int
    rate_cap_per_day: Optional[int]
    sent_count_today: int
    cohort: Optional[str]
    cohort_allow: Optional[str]


def _coerce_payload(payload: Dict[str, Any]) -> PolicyInput:
    now_dt = _parse_iso(payload.get("now")) or datetime.now(timezone.utc)
    ttl = int(payload.get("ttl", payload.get("ttl_minutes", 1440)) or 0)
    snooze = int(payload.get("snooze", payload.get("snooze_minutes", 120)) or 0)
    rate_cap = payload.get("rate_cap_per_day")
    rate_cap_int = int(rate_cap) if rate_cap is not None else None
    sent_count = int(payload.get("sent_count_today", 0) or 0)
    cohort = payload.get("ab_cohort")
    cohort_allow = payload.get("allowed_cohort")
    last_sent = _parse_iso(payload.get("last_sent"))
    return PolicyInput(
        now=now_dt,
        last_sent=last_sent,
        ttl_minutes=ttl,
        snooze_minutes=snooze,
        rate_cap_per_day=rate_cap_int,
        sent_count_today=max(sent_count, 0),
        cohort=cohort,
        cohort_allow=cohort_allow,
    )


def evaluate_nudge_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return {"allow": bool, "reason": str} for the supplied payload."""

    inputs = _coerce_payload(payload)

    if inputs.cohort_allow and inputs.cohort and inputs.cohort not in {c.strip() for c in inputs.cohort_allow.split(",") if c.strip()}:
        return {"allow": False, "reason": "cohort_block"}

    if inputs.rate_cap_per_day is not None and inputs.sent_count_today >= inputs.rate_cap_per_day:
        return {"allow": False, "reason": "rate_cap"}

    if inputs.last_sent is not None:
        ttl_delta = timedelta(minutes=max(inputs.ttl_minutes, 0))
        if inputs.now < inputs.last_sent + ttl_delta:
            return {"allow": False, "reason": "ttl_active"}

    snooze_until = payload.get("snoozed_until")
    if snooze_until:
        snooze_dt = _parse_iso(snooze_until)
        if snooze_dt and inputs.now < snooze_dt:
            return {"allow": False, "reason": "snoozed"}

    snooze_start = payload.get("last_snoozed_at")
    if snooze_start:
        snooze_started = _parse_iso(snooze_start)
        if snooze_started:
            snooze_delta = timedelta(minutes=max(inputs.snooze_minutes, 0))
            if inputs.now < snooze_started + snooze_delta:
                return {"allow": False, "reason": "snoozed"}

    return {"allow": True, "reason": "ok"}


__all__ = ["evaluate_nudge_policy"]
