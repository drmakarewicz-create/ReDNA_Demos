"""Bridge helpers for involving the Head Coach in conflict resolution."""

from __future__ import annotations

from datetime import datetime

from ..conflict.models import Conflict, Outcome


def adjudicate(conflict: Conflict) -> Outcome:
    """Lightweight adjudication stub.

    In production this would involve prompting the Head Coach model with the conflicting
    evidence. For the demo we compute a simple rationale based on existing signals.
    """

    summary_parts = []
    for ev in conflict.evidence:
        label = ev.module or ev.source_type
        summary_parts.append(f"{label}: {ev.value}")

    reason = "Head Coach reviewed inputs: " + ", ".join(summary_parts)

    # Default to first evidence value if available
    resolved_value = conflict.evidence[0].value if conflict.evidence else None
    resolved_ucn = conflict.evidence[0].ucn if conflict.evidence and conflict.evidence[0].ucn else None

    return Outcome(
        resolver="head_coach",
        resolved_value=resolved_value,
        resolved_ucn=resolved_ucn,
        reason=reason,
        timestamp=datetime.utcnow(),
    )

