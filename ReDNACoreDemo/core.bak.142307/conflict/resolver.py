"""Conflict resolver orchestrator."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml

from .calibration import CalibrationManager
from .learning import get_learning_snapshot
from .models import Conflict, Outcome
from .storage import append_conflict_record
from .strategies import (
    auto_merge_conflict,
    escalation_required,
    hierarchical_resolution,
    policy_gate_resolution,
)


SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _load_rules() -> Dict:
    rules_path = Path(__file__).resolve().parent / "policy" / "conflict_rules.yaml"
    with rules_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@dataclass
class ResolverResult:
    conflict: Conflict
    outcome: Outcome


class ConflictResolver:
    """High level resolver responsible for deciding strategy routes."""

    def __init__(self) -> None:
        self.rules = _load_rules()
        self.calibration = CalibrationManager()

    def resolve(self, conflict: Conflict) -> ResolverResult:
        if conflict.kind in {"policy", "permission"}:
            outcome = policy_gate_resolution(conflict, explanation="Policy requires explicit capability")
            conflict.status = "denied"
            conflict.outcome = outcome
            append_conflict_record(conflict)
            return ResolverResult(conflict, outcome)

        user_base = self.calibration.get_weight(conflict.user_id, conflict.path or "generic")

        if self._requires_corrob(conflict):
            outcome = escalation_required(conflict, "Awaiting corroboration for sensitive trait")
            conflict.status = "escalated"
            conflict.outcome = outcome
            append_conflict_record(conflict)
            return ResolverResult(conflict, outcome)

        severity_rank = SEVERITY_ORDER.get(conflict.severity, 0)
        auto_max = SEVERITY_ORDER.get(self.rules["routing"].get("auto_merge_max_severity", "low"), 0)
        hierarchical_min = SEVERITY_ORDER.get(self.rules["routing"].get("hierarchical_min_severity", "medium"), 1)

        if severity_rank <= auto_max:
            outcome = auto_merge_conflict(conflict, user_assertion_weight=user_base)
            conflict.status = "auto_resolved"
        elif severity_rank >= hierarchical_min:
            outcome = hierarchical_resolution(conflict)
            conflict.status = "resolved" if outcome.resolved_value is not None else "escalated"
        else:
            outcome = auto_merge_conflict(conflict, user_assertion_weight=user_base)
            conflict.status = "auto_resolved"

        conflict.outcome = outcome
        append_conflict_record(conflict)
        if conflict.outcome and conflict.path:
            result_flag = "confirmed" if conflict.status in {"auto_resolved", "resolved"} else "pending"
            self.calibration.record_outcome(conflict.user_id, conflict.path, result_flag)
        return ResolverResult(conflict, outcome)

    def _requires_corrob(self, conflict: Conflict) -> bool:
        routing = self.rules.get("routing", {})
        if not routing.get("escalate_if_sensitive_and_uncorroborated", True):
            return False
        if not conflict.is_sensitive:
            return False
        flips = self.rules.get("flips", {})
        min_sources = int(flips.get("min_distinct_sources", 2))
        min_signals = int(flips.get("min_signals", 5))
        if conflict.distinct_sources() < min_sources:
            return True
        if conflict.signal_count() < min_signals:
            return True
        return False
