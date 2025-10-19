"""
Head Coach Autonomy Policy Framework

Defines structured autonomy policies for Head Coaches, enabling safe,
bounded self-governance within explicit guardrails.

Phase 5.A: Autonomy Graduation
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


@dataclass
class AutonomyPolicy:
    """
    Structured autonomy policy for a Head Coach.

    Levels:
      0 = Dormant (no autonomy)
      1 = Semi-autonomous (manual approval)
      2 = Supervised autonomy (logged, soft limits)
      3 = Trusted autonomy (within guardrails)
      4 = Full autonomy (advanced, rare)
    """
    level: int = 1
    self_schedule: bool = False
    self_reflect: bool = False
    self_narrate: bool = False
    rsc_enabled: bool = False
    consent_scope: List[str] = field(default_factory=lambda: ["learning", "reflection"])
    guardrails: Dict[str, Any] = field(default_factory=lambda: {
        "max_self_actions_per_day": 5,
        "tone_shift_bounds": 0.25,
        "creativity_shift_bounds": 0.25,
        "max_learning_delta_per_week": 0.15,
        "require_consent_for": ["rsc_invite", "data_export"],
        "prohibited_actions": ["policy_self_modify", "user_data_delete"]
    })
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    version: str = "5.A.1"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutonomyPolicy':
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> List[str]:
        """
        Validate policy consistency.
        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Level bounds
        if not 0 <= self.level <= 4:
            errors.append(f"Invalid autonomy level: {self.level} (must be 0-4)")

        # Level consistency
        if self.level == 0:
            if self.self_schedule or self.self_reflect or self.self_narrate or self.rsc_enabled:
                errors.append("Level 0 (dormant) cannot have self-* capabilities enabled")

        if self.level == 1:
            if self.self_schedule:
                errors.append("Level 1 (semi) cannot have self_schedule enabled")

        if self.rsc_enabled and self.level < 2:
            errors.append("RSC requires autonomy level >= 2")

        # Guardrail validation
        if "max_self_actions_per_day" in self.guardrails:
            if self.guardrails["max_self_actions_per_day"] < 1:
                errors.append("max_self_actions_per_day must be >= 1")

        if "tone_shift_bounds" in self.guardrails:
            if not 0 <= self.guardrails["tone_shift_bounds"] <= 1.0:
                errors.append("tone_shift_bounds must be in [0, 1.0]")

        if "creativity_shift_bounds" in self.guardrails:
            if not 0 <= self.guardrails["creativity_shift_bounds"] <= 1.0:
                errors.append("creativity_shift_bounds must be in [0, 1.0]")

        return errors


def get_autonomy_dir(user_id: str) -> Path:
    """Get autonomy directory for user."""
    base = Path(__file__).parent.parent / "data" / "users" / user_id / "hc_autonomy"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_autonomy_policy(user_id: str) -> AutonomyPolicy:
    """
    Load autonomy policy for user.
    Creates default policy if none exists.
    """
    policy_path = get_autonomy_dir(user_id) / "policy.json"

    if policy_path.exists():
        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            policy = AutonomyPolicy.from_dict(data)

            # Validate
            errors = policy.validate()
            if errors:
                print(f"[hc_autonomy] Policy validation errors for {user_id}: {errors}")
                # Return default on validation failure
                return AutonomyPolicy()

            return policy
        except Exception as e:
            print(f"[hc_autonomy] Error loading policy for {user_id}: {e}")
            return AutonomyPolicy()
    else:
        # Create default policy
        default_policy = AutonomyPolicy()
        save_autonomy_policy(user_id, default_policy)
        return default_policy


def save_autonomy_policy(user_id: str, policy: AutonomyPolicy) -> bool:
    """
    Save autonomy policy for user.
    Validates before saving.
    """
    errors = policy.validate()
    if errors:
        print(f"[hc_autonomy] Cannot save invalid policy: {errors}")
        return False

    policy_path = get_autonomy_dir(user_id) / "policy.json"

    try:
        # Update timestamp
        policy.last_updated = datetime.utcnow().isoformat() + "Z"

        with open(policy_path, "w", encoding="utf-8") as f:
            json.dump(policy.to_dict(), f, indent=2)

        # Emit audit event
        _emit_policy_change_audit(user_id, policy)

        return True
    except Exception as e:
        print(f"[hc_autonomy] Error saving policy for {user_id}: {e}")
        return False


def apply_autonomy_policy(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply updates to autonomy policy.

    Returns:
        {"success": bool, "policy": dict, "errors": list}
    """
    current_policy = load_autonomy_policy(user_id)

    # Apply updates
    for key, value in updates.items():
        if hasattr(current_policy, key):
            # Special handling for nested guardrails
            if key == "guardrails" and isinstance(value, dict):
                current_policy.guardrails.update(value)
            else:
                setattr(current_policy, key, value)
        else:
            return {
                "success": False,
                "policy": None,
                "errors": [f"Unknown policy field: {key}"]
            }

    # Validate and save
    errors = current_policy.validate()
    if errors:
        return {
            "success": False,
            "policy": None,
            "errors": errors
        }

    success = save_autonomy_policy(user_id, current_policy)

    return {
        "success": success,
        "policy": current_policy.to_dict() if success else None,
        "errors": [] if success else ["Failed to save policy"]
    }


def evaluate_autonomy_policy(policy: AutonomyPolicy) -> Dict[str, Any]:
    """
    Evaluate policy for readiness and compliance.

    Returns:
        {
            "readiness": float,  # 0-1 score
            "compliance": bool,
            "warnings": list,
            "recommendations": list
        }
    """
    warnings = []
    recommendations = []

    # Validation errors = not compliant
    errors = policy.validate()
    if errors:
        return {
            "readiness": 0.0,
            "compliance": False,
            "warnings": errors,
            "recommendations": ["Fix validation errors before proceeding"]
        }

    # Readiness scoring
    readiness_score = 0.0
    max_score = 5.0

    # Base readiness from level
    readiness_score += policy.level * 0.5

    # Guardrails present
    if policy.guardrails:
        readiness_score += 1.0

    # Consent scope defined
    if policy.consent_scope:
        readiness_score += 1.0

    # Appropriate capabilities for level
    if policy.level >= 2 and policy.self_schedule:
        readiness_score += 0.5
    elif policy.level < 2 and not policy.self_schedule:
        readiness_score += 0.5

    if policy.level >= 2 and policy.self_reflect:
        readiness_score += 0.5

    if policy.level >= 3 and policy.self_narrate:
        readiness_score += 0.5

    # Warnings for edge cases
    if policy.level >= 3 and not policy.self_schedule:
        warnings.append("Level 3+ typically enables self_schedule")

    if policy.self_schedule and not policy.self_reflect:
        warnings.append("Self-scheduling without self-reflection may limit effectiveness")

    if policy.rsc_enabled and "rsc_invite" not in policy.guardrails.get("require_consent_for", []):
        warnings.append("RSC enabled but rsc_invite not in consent requirements")

    # Recommendations
    if policy.level == 1:
        recommendations.append("Consider level 2 (supervised) for basic autonomy")

    if not policy.self_schedule and policy.level >= 2:
        recommendations.append("Enable self_schedule for regular maintenance")

    if policy.guardrails.get("max_self_actions_per_day", 5) < 3:
        recommendations.append("Consider increasing max_self_actions_per_day to at least 3")

    readiness = min(1.0, readiness_score / max_score)

    return {
        "readiness": readiness,
        "compliance": True,
        "warnings": warnings,
        "recommendations": recommendations
    }


def get_default_policy_for_level(level: int) -> AutonomyPolicy:
    """
    Get recommended default policy for a given autonomy level.
    """
    if level == 0:
        return AutonomyPolicy(
            level=0,
            self_schedule=False,
            self_reflect=False,
            self_narrate=False,
            rsc_enabled=False
        )

    elif level == 1:
        return AutonomyPolicy(
            level=1,
            self_schedule=False,
            self_reflect=True,
            self_narrate=False,
            rsc_enabled=False
        )

    elif level == 2:
        return AutonomyPolicy(
            level=2,
            self_schedule=True,
            self_reflect=True,
            self_narrate=True,
            rsc_enabled=False,
            guardrails={
                "max_self_actions_per_day": 5,
                "tone_shift_bounds": 0.25,
                "creativity_shift_bounds": 0.25,
                "max_learning_delta_per_week": 0.15,
                "require_consent_for": ["rsc_invite", "data_export"],
                "prohibited_actions": ["policy_self_modify", "user_data_delete"]
            }
        )

    elif level == 3:
        return AutonomyPolicy(
            level=3,
            self_schedule=True,
            self_reflect=True,
            self_narrate=True,
            rsc_enabled=True,
            consent_scope=["learning", "reflection", "narration", "rsc_basic"],
            guardrails={
                "max_self_actions_per_day": 10,
                "tone_shift_bounds": 0.30,
                "creativity_shift_bounds": 0.30,
                "max_learning_delta_per_week": 0.20,
                "require_consent_for": ["rsc_invite", "data_export", "cross_user_learning"],
                "prohibited_actions": ["policy_self_modify", "user_data_delete"]
            }
        )

    else:  # level 4
        return AutonomyPolicy(
            level=4,
            self_schedule=True,
            self_reflect=True,
            self_narrate=True,
            rsc_enabled=True,
            consent_scope=["learning", "reflection", "narration", "rsc_full", "cross_user_learning"],
            guardrails={
                "max_self_actions_per_day": 20,
                "tone_shift_bounds": 0.40,
                "creativity_shift_bounds": 0.40,
                "max_learning_delta_per_week": 0.25,
                "require_consent_for": ["data_export"],
                "prohibited_actions": ["user_data_delete"]
            }
        )


def _emit_policy_change_audit(user_id: str, policy: AutonomyPolicy):
    """Emit audit event for policy change."""
    try:
        audit_dir = Path(__file__).parent.parent / "data" / "telemetry" / "agents"
        audit_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "event_type": "autonomy_level_changed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "autonomy_level": policy.level,
            "self_schedule": policy.self_schedule,
            "self_reflect": policy.self_reflect,
            "self_narrate": policy.self_narrate,
            "rsc_enabled": policy.rsc_enabled,
            "version": policy.version
        }

        audit_file = audit_dir / "agent_activity.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    except Exception as e:
        print(f"[hc_autonomy] Failed to emit audit event: {e}")
