"""Automatic conflict merging strategy."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, Iterable

from ..evidence_weighting import compute_effective_weight
from ..models import Conflict, Evidence, Outcome


def auto_merge_conflict(conflict: Conflict, *, user_assertion_weight: float) -> Outcome:
    """Resolve low severity conflicts automatically using weighting rules."""

    numeric_values = []
    categorical_votes: Dict[str, float] = {}
    total_weight = 0.0

    for ev in conflict.evidence:
        breakdown = compute_effective_weight(ev, user_base=user_assertion_weight if ev.source_type == "user_assertion" else None)
        weight = breakdown.total
        total_weight += weight

        if isinstance(ev.value, (int, float)):
            numeric_values.append((float(ev.value), weight))
        elif isinstance(ev.value, str):
            support = float(ev.provenance.get("support", 1.0))
            categorical_votes[ev.value] = categorical_votes.get(ev.value, 0.0) + weight * support

    resolved_value = None
    resolved_ucn = None
    reason = ""

    if numeric_values:
        numerator = sum(value * wt for value, wt in numeric_values)
        denom = sum(wt for _, wt in numeric_values)
        resolved_value = numerator / denom if denom else None
        reason = "Weighted average applied"
        if denom:
            resolved_ucn = max(ev.ucn or 0.0 for ev in conflict.evidence)
    elif categorical_votes:
        resolved_value = max(categorical_votes.items(), key=lambda item: item[1])[0]
        reason = "Log-odds categorical merge"
        resolved_ucn = max(ev.ucn or 0.0 for ev in conflict.evidence)
    else:
        reason = "No mergeable signals; conflict retained"

    status_reason = reason
    return Outcome(
        resolver="auto_merge",
        resolved_value=resolved_value,
        resolved_ucn=resolved_ucn,
        reason=status_reason,
        timestamp=datetime.utcnow(),
    )

