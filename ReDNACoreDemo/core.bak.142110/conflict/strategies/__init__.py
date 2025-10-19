"""Conflict resolution strategies."""

from .auto_merge import auto_merge_conflict
from .hierarchical import hierarchical_resolution
from .policy_gate import policy_gate_resolution
from .escalation import escalation_required

__all__ = [
    "auto_merge_conflict",
    "hierarchical_resolution",
    "policy_gate_resolution",
    "escalation_required",
]
