"""Policy gate strategy for policy/permission conflicts."""

from __future__ import annotations

from datetime import datetime

from ..models import Conflict, Outcome


def policy_gate_resolution(conflict: Conflict, explanation: str = "Denied by policy gate") -> Outcome:
    return Outcome(
        resolver="policy_gate",
        resolved_value=None,
        resolved_ucn=None,
        reason=explanation,
        timestamp=datetime.utcnow(),
    )

