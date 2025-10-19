from __future__ import annotations

"""
Agent policy persistence utilities.

Each Head Coach agent is governed by a per-user policy file that declares
allowed namespaces, sensitive scopes, quotas, and escalation rules. Policies
live under `ReDNACoreDemo/agents/policies` and are copied to the runtime
workspace on first access.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .registry import DEFAULT_NAMESPACES, DEFAULT_SENSITIVE, AGENTS_ROOT, VALID_AUTONOMY, ensure_agent_record


POLICIES_DIR = AGENTS_ROOT / "policies"
POLICIES_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_list(items: Optional[Iterable[str]]) -> List[str]:
    values: List[str] = []
    if not items:
        return values
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text:
                values.append(text)
    return values


class PolicyValidationError(ValueError):
    """Invalid policy update."""


@dataclass
class AgentPolicy:
    user_id: str
    agent_id: str
    autonomy: str = "semi"
    quotas: Dict[str, int] = field(default_factory=lambda: {"jobs_per_day": 50})
    permissions: Dict[str, List[str]] = field(
        default_factory=lambda: {"namespaces": list(DEFAULT_NAMESPACES), "sensitive": list(DEFAULT_SENSITIVE)}
    )
    escalation: Dict[str, Any] = field(
        default_factory=lambda: {
            "manual_review": ["core.refinement.resolve"],
            "notify": ["sensitive.read"],
        }
    )
    features: Dict[str, Any] = field(default_factory=dict)
    rsc_enabled: bool = False
    rsc_partners_allow: List[str] = field(default_factory=list)
    rsc_partners_deny: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["permissions"] = {
            "namespaces": list(self.permissions.get("namespaces", [])),
            "sensitive": list(self.permissions.get("sensitive", [])),
        }
        payload["quotas"] = dict(self.quotas)
        payload["escalation"] = dict(self.escalation)
        payload["features"] = dict(self.features)
        payload["rsc_enabled"] = self.rsc_enabled
        payload["rsc_partners_allow"] = list(self.rsc_partners_allow)
        payload["rsc_partners_deny"] = list(self.rsc_partners_deny)
        if payload.get("autonomy") == "manual":
            payload["autonomy"] = None
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AgentPolicy":
        user_id = str(payload.get("user_id") or "").strip()
        agent_id = str(payload.get("agent_id") or "").strip()
        if not user_id or not agent_id:
            raise PolicyValidationError("Policy requires user_id and agent_id")

        raw_autonomy = payload.get("autonomy")
        if raw_autonomy is None:
            autonomy = "manual"
        else:
            autonomy = str(raw_autonomy).lower()
            if autonomy not in VALID_AUTONOMY:
                autonomy = "semi"

        quotas = payload.get("quotas")
        if not isinstance(quotas, dict):
            quotas = {}
        normalized_quotas: Dict[str, int] = {}
        for key, value in quotas.items():
            try:
                normalized_quotas[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        if "jobs_per_day" not in normalized_quotas:
            normalized_quotas["jobs_per_day"] = 50

        permissions = payload.get("permissions")
        if not isinstance(permissions, dict):
            permissions = {}
        namespaces = _normalize_list(permissions.get("namespaces"))
        sensitive = _normalize_list(permissions.get("sensitive"))
        if not namespaces:
            namespaces = list(DEFAULT_NAMESPACES)
        if not sensitive:
            sensitive = list(DEFAULT_SENSITIVE)

        escalation = payload.get("escalation")
        if not isinstance(escalation, dict):
            escalation = {}

        features = payload.get("features")
        if not isinstance(features, dict):
            features = {}

        rsc_enabled = bool(payload.get("rsc_enabled", False))
        rsc_partners_allow = _normalize_list(payload.get("rsc_partners_allow"))
        rsc_partners_deny = _normalize_list(payload.get("rsc_partners_deny"))

        return cls(
            user_id=user_id,
            agent_id=agent_id,
            autonomy=autonomy,
            quotas=normalized_quotas,
            permissions={"namespaces": namespaces, "sensitive": sensitive},
            escalation=escalation,
            features=features,
            rsc_enabled=rsc_enabled,
            rsc_partners_allow=rsc_partners_allow,
            rsc_partners_deny=rsc_partners_deny,
        )


def _policy_path(user_id: str) -> Path:
    normalized_id = str(user_id or "").strip()
    if not normalized_id:
        raise PolicyValidationError("user_id is required")
    return POLICIES_DIR / f"hc_{normalized_id}.json"


def default_policy(user_id: str) -> AgentPolicy:
    record = ensure_agent_record(user_id)
    return AgentPolicy(user_id=record.user_id, agent_id=record.agent_id, autonomy=record.autonomy)


def get_agent_policy(user_id: str, *, create: bool = True) -> AgentPolicy:
    """
    Load the policy for a user. Creates a default policy if missing.
    """
    path = _policy_path(user_id)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return AgentPolicy.from_dict(payload)
        except json.JSONDecodeError as exc:
            raise PolicyValidationError(f"Invalid policy JSON for {user_id}: {exc}") from exc

    if not create:
        raise FileNotFoundError(f"No policy file for user {user_id}")

    policy = default_policy(user_id)
    path.write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")
    return policy


def update_policy(user_id: str, changes: Dict[str, Any]) -> AgentPolicy:
    """
    Apply a shallow update to a user's policy.
    """
    if not isinstance(changes, dict):
        raise PolicyValidationError("changes must be a dict")

    policy = get_agent_policy(user_id)

    autonomy_provided = "autonomy" in changes
    if autonomy_provided:
        autonomy_value = changes.get("autonomy")
        if autonomy_value is None:
            policy.autonomy = "manual"
        else:
            autonomy_text = str(autonomy_value).lower()
            if autonomy_text not in VALID_AUTONOMY:
                raise PolicyValidationError(f"Invalid autonomy value: {autonomy_text}")
            policy.autonomy = autonomy_text

    if "quotas" in changes:
        quotas = changes["quotas"]
        if not isinstance(quotas, dict):
            raise PolicyValidationError("quotas must be a dict")
        normalized: Dict[str, int] = {}
        for key, value in quotas.items():
            try:
                normalized[str(key)] = int(value)
            except (TypeError, ValueError) as exc:
                raise PolicyValidationError(f"Invalid quota value for {key}: {value}") from exc
        if "jobs_per_day" not in normalized:
            normalized["jobs_per_day"] = policy.quotas.get("jobs_per_day", 50)
        policy.quotas = normalized

    if "permissions" in changes:
        permissions = changes["permissions"]
        if not isinstance(permissions, dict):
            raise PolicyValidationError("permissions must be a dict")
        raw_namespaces = permissions.get("namespaces")
        namespaces = _normalize_list(raw_namespaces)
        if raw_namespaces is not None and not namespaces:
            raise PolicyValidationError("permissions.namespaces cannot be empty")
        if not namespaces:
            namespaces = policy.permissions.get("namespaces", []) or list(DEFAULT_NAMESPACES)

        raw_sensitive = permissions.get("sensitive")
        sensitive = _normalize_list(raw_sensitive)
        if raw_sensitive is not None and not sensitive:
            sensitive = []
        if not sensitive:
            sensitive = policy.permissions.get("sensitive", []) or list(DEFAULT_SENSITIVE)

        policy.permissions = {"namespaces": namespaces, "sensitive": sensitive}

    if "escalation" in changes:
        if not isinstance(changes["escalation"], dict):
            raise PolicyValidationError("escalation must be a dict")
        policy.escalation = dict(changes["escalation"])

    if "features" in changes:
        features = changes["features"]
        if not isinstance(features, dict):
            raise PolicyValidationError("features must be a dict")
        policy.features = dict(features)

    if "rsc_enabled" in changes:
        policy.rsc_enabled = bool(changes["rsc_enabled"])

    if "rsc_partners_allow" in changes:
        policy.rsc_partners_allow = _normalize_list(changes["rsc_partners_allow"])

    if "rsc_partners_deny" in changes:
        policy.rsc_partners_deny = _normalize_list(changes["rsc_partners_deny"])

    path = _policy_path(user_id)
    path.write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")
    return policy


def can_send_rsc_message(from_policy: AgentPolicy, to_agent_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if sender is allowed to send RSC messages to recipient.
    Returns (allowed, reason_if_denied).
    """
    if not from_policy.rsc_enabled:
        return False, "rsc_disabled"

    # Check deny list first
    if to_agent_id in from_policy.rsc_partners_deny:
        return False, "partner_denied"

    # If allow list is empty, allow all (unless denied above)
    if not from_policy.rsc_partners_allow:
        return True, None

    # If allow list has entries, recipient must be in it
    if to_agent_id not in from_policy.rsc_partners_allow:
        return False, "partner_not_allowed"

    return True, None


def can_receive_rsc_message(to_policy: AgentPolicy, from_agent_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if recipient is allowed to receive RSC messages from sender.
    Returns (allowed, reason_if_denied).
    """
    if not to_policy.rsc_enabled:
        return False, "rsc_disabled"

    # Check deny list first
    if from_agent_id in to_policy.rsc_partners_deny:
        return False, "partner_denied"

    # If allow list is empty, allow all (unless denied above)
    if not to_policy.rsc_partners_allow:
        return True, None

    # If allow list has entries, sender must be in it
    if from_agent_id not in to_policy.rsc_partners_allow:
        return False, "partner_not_allowed"

    return True, None
