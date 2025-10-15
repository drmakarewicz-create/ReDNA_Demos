"""Escalation strategy for high risk conflicts."""

from __future__ import annotations

from datetime import datetime

from ..models import Conflict, Outcome


def escalation_required(conflict: Conflict, reason: str) -> Outcome:
    return Outcome(
        resolver="escalation",
        resolved_value=None,
        resolved_ucn=None,
        reason=reason,
        timestamp=datetime.utcnow(),
        audit_refs={"escalated": True},
    )

