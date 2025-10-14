"""Hierarchical resolution using Head Coach adjudication."""

from __future__ import annotations

from datetime import datetime

from ..models import Conflict, Outcome
from ...head_coach import conflict_bridge


def hierarchical_resolution(conflict: Conflict) -> Outcome:
    """Delegate to the Head Coach adjudication pipeline."""

    outcome = conflict_bridge.adjudicate(conflict)
    if outcome:
        return outcome

    return Outcome(
        resolver="hierarchical_fallback",
        resolved_value=None,
        resolved_ucn=None,
        reason="Head Coach adjudication unavailable",
        timestamp=datetime.utcnow(),
    )

