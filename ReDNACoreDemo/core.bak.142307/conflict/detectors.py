"""Conflict detection helpers."""

from __future__ import annotations

import itertools
from datetime import datetime
from typing import Iterable, List, Optional

from .models import Conflict, Evidence


def make_conflict(
    *,
    conflict_id: str,
    user_id: str,
    kind: str,
    severity: str,
    path: Optional[str],
    evidence: Iterable[Evidence],
    signals: Optional[dict] = None,
) -> Conflict:
    """Build a conflict model from raw evidence."""

    evidence_list: List[Evidence] = list(evidence)
    participants = sorted({ev.module for ev in evidence_list if ev.module} | {ev.source_type for ev in evidence_list})
    return Conflict(
        conflict_id=conflict_id,
        user_id=user_id,
        kind=kind,  # type: ignore[arg-type]
        path=path,
        created_at=datetime.utcnow(),
        severity=severity,  # type: ignore[arg-type]
        participants=[p for p in participants if p],
        evidence=evidence_list,
        signals=signals or {},
    )


def summarize_evidence_values(evidence: Iterable[Evidence]) -> dict:
    """Utility used by dashboards to provide quick summaries."""

    numeric_values = [ev.value for ev in evidence if isinstance(ev.value, (int, float))]
    categorical_values = [ev.value for ev in evidence if isinstance(ev.value, str)]
    return {
        "numeric": numeric_values,
        "categorical": categorical_values,
        "sources": sorted({ev.source_type for ev in evidence}),
    }

