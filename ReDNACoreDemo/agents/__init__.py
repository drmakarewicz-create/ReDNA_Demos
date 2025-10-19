"""
Head Coach agent package for ReDNACoreDemo.

This namespace provides helpers to manage agent registry entries, policy files,
runtime state, and mailbox interactions. Higher-level services (CLI, daemon,
DevX APIs) build on these primitives.
"""

from .registry import (
    AgentRecord,
    ensure_agent_record,
    get_agent_record,
    list_agents,
    update_agent_record,
)
from .policy import AgentPolicy, PolicyValidationError, get_agent_policy, update_policy
from .state import AgentState, AgentStateStore
from .mailbox import AgentMailbox

__all__ = [
    "AgentMailbox",
    "AgentPolicy",
    "AgentRecord",
    "AgentState",
    "AgentStateStore",
    "PolicyValidationError",
    "ensure_agent_record",
    "get_agent_policy",
    "get_agent_record",
    "list_agents",
    "update_agent_policy",
    "update_agent_record",
]


def update_agent_policy(user_id: str, changes):
    """Compatibility wrapper for policy.update_policy."""
    return update_policy(user_id, changes)
