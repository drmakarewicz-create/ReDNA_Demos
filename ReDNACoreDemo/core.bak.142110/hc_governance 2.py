"""
Head Coach Governance & Safeguards

Implements guardrails to prevent Head Coaches from exceeding policy bounds,
with violation detection and audit trails.

Phase 5.A: Autonomy Graduation
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .hc_autonomy import load_autonomy_policy, AutonomyPolicy


class GovernanceViolation(Exception):
    """Raised when an action violates governance rules."""
    pass


def verify_learning_delta_bounds(
    user_id: str,
    proposed_deltas: Dict[str, float]
) -> Tuple[bool, List[str]]:
    """
    Verify that proposed learning deltas are within policy bounds.

    Returns:
        (is_valid, violations)
    """
    policy = load_autonomy_policy(user_id)
    max_delta = policy.guardrails.get("max_learning_delta_per_week", 0.15)

    violations = []

    for trait, delta in proposed_deltas.items():
        if abs(delta) > max_delta:
            violations.append(
                f"Learning delta for {trait} ({delta:.3f}) exceeds max_learning_delta_per_week ({max_delta})"
            )

    return len(violations) == 0, violations


def verify_tone_creativity_bounds(
    user_id: str,
    tone_shift: Optional[float] = None,
    creativity_shift: Optional[float] = None
) -> Tuple[bool, List[str]]:
    """
    Verify that tone/creativity shifts are within policy bounds.

    Returns:
        (is_valid, violations)
    """
    policy = load_autonomy_policy(user_id)

    violations = []

    if tone_shift is not None:
        max_tone = policy.guardrails.get("tone_shift_bounds", 0.25)
        if abs(tone_shift) > max_tone:
            violations.append(
                f"Tone shift ({tone_shift:.3f}) exceeds tone_shift_bounds ({max_tone})"
            )

    if creativity_shift is not None:
        max_creativity = policy.guardrails.get("creativity_shift_bounds", 0.25)
        if abs(creativity_shift) > max_creativity:
            violations.append(
                f"Creativity shift ({creativity_shift:.3f}) exceeds creativity_shift_bounds ({max_creativity})"
            )

    return len(violations) == 0, violations


def verify_consent_scope(
    user_id: str,
    action: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify that an action is within the user's consent scope.

    Returns:
        (is_allowed, reason)
    """
    policy = load_autonomy_policy(user_id)

    # Check if action requires consent
    require_consent = policy.guardrails.get("require_consent_for", [])

    if action in require_consent:
        # Check if consent is granted
        if action in policy.consent_scope or _consent_granted_in_scope(action, policy.consent_scope):
            return True, None
        else:
            return False, f"Action '{action}' requires consent but is not in consent_scope"

    # No consent required
    return True, None


def _consent_granted_in_scope(action: str, consent_scope: List[str]) -> bool:
    """Check if action is covered by consent scope patterns."""
    # Simple pattern matching
    for scope in consent_scope:
        if scope == action:
            return True
        # Pattern: rsc_* covers rsc_invite, rsc_accept, etc.
        if scope.endswith("*") and action.startswith(scope[:-1]):
            return True

    return False


def verify_prohibited_actions(
    user_id: str,
    action: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify that an action is not prohibited by policy.

    Returns:
        (is_allowed, reason)
    """
    policy = load_autonomy_policy(user_id)

    prohibited = policy.guardrails.get("prohibited_actions", [])

    if action in prohibited:
        return False, f"Action '{action}' is prohibited by policy"

    return True, None


def enforce_daily_action_limit(user_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if user has exceeded daily action limit.

    Returns:
        (within_limit, reason)
    """
    from .hc_scheduler import load_schedule_state

    policy = load_autonomy_policy(user_id)
    state = load_schedule_state(user_id)

    max_actions = policy.guardrails.get("max_self_actions_per_day", 5)

    # Reset if new day
    today = datetime.utcnow().date().isoformat()
    if state.last_reset != today:
        return True, None

    if state.actions_today >= max_actions:
        return False, f"Daily action limit reached ({state.actions_today}/{max_actions})"

    return True, None


def check_governance_compliance(
    user_id: str,
    action: str,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive governance check for an action.

    Returns:
        {
            "allowed": bool,
            "violations": List[str],
            "warnings": List[str]
        }
    """
    violations = []
    warnings = []

    # Check prohibited actions
    allowed, reason = verify_prohibited_actions(user_id, action)
    if not allowed:
        violations.append(reason)

    # Check consent scope
    allowed, reason = verify_consent_scope(user_id, action)
    if not allowed:
        violations.append(reason)

    # Check daily limits
    within_limit, reason = enforce_daily_action_limit(user_id)
    if not within_limit:
        violations.append(reason)

    # Parameter-specific checks
    if parameters:
        # Learning deltas
        if "learning_deltas" in parameters:
            valid, delta_violations = verify_learning_delta_bounds(
                user_id, parameters["learning_deltas"]
            )
            if not valid:
                violations.extend(delta_violations)

        # Tone/creativity shifts
        if "tone_shift" in parameters or "creativity_shift" in parameters:
            valid, shift_violations = verify_tone_creativity_bounds(
                user_id,
                parameters.get("tone_shift"),
                parameters.get("creativity_shift")
            )
            if not valid:
                violations.extend(shift_violations)

    # Warnings (non-blocking)
    policy = load_autonomy_policy(user_id)

    if policy.level < 2 and action.startswith("self_"):
        warnings.append(f"Action '{action}' typically requires autonomy level >= 2")

    if action == "rsc_invite" and not policy.rsc_enabled:
        warnings.append("RSC not enabled in policy")

    # Emit audit if violations found
    if violations:
        _emit_governance_violation(user_id, action, violations)

    return {
        "allowed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings
    }


def review_autonomy_compliance(user_id: str) -> Dict[str, Any]:
    """
    Review overall autonomy compliance for a user.

    Returns comprehensive governance report.
    """
    from .hc_scheduler import load_schedule_state
    from .hc_autonomy import evaluate_autonomy_policy

    policy = load_autonomy_policy(user_id)
    state = load_schedule_state(user_id)

    # Policy evaluation
    policy_eval = evaluate_autonomy_policy(policy)

    # Recent violations
    violations = _get_recent_violations(user_id, days=7)

    # Action quota usage
    max_actions = policy.guardrails.get("max_self_actions_per_day", 5)
    quota_usage = state.actions_today / max_actions if max_actions > 0 else 0.0

    # Task health
    task_health = _evaluate_task_health(state)

    # Overall compliance score
    compliance_score = _calculate_compliance_score(
        policy_eval, violations, quota_usage, task_health
    )

    return {
        "user_id": user_id,
        "compliance_score": compliance_score,
        "policy_evaluation": policy_eval,
        "recent_violations": violations,
        "quota_usage": {
            "today": state.actions_today,
            "max": max_actions,
            "percentage": quota_usage
        },
        "task_health": task_health,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def _evaluate_task_health(state) -> Dict[str, Any]:
    """Evaluate health of scheduled tasks."""
    total_tasks = len(state.tasks)
    enabled_tasks = sum(1 for t in state.tasks.values() if t.enabled)
    tasks_with_failures = sum(1 for t in state.tasks.values() if t.failure_count > 0)

    total_runs = sum(t.run_count for t in state.tasks.values())
    total_failures = sum(t.failure_count for t in state.tasks.values())

    success_rate = 1.0 - (total_failures / total_runs) if total_runs > 0 else 1.0

    return {
        "total_tasks": total_tasks,
        "enabled_tasks": enabled_tasks,
        "tasks_with_failures": tasks_with_failures,
        "success_rate": success_rate,
        "total_runs": total_runs,
        "total_failures": total_failures
    }


def _calculate_compliance_score(
    policy_eval: Dict[str, Any],
    violations: List[Dict],
    quota_usage: float,
    task_health: Dict[str, Any]
) -> float:
    """Calculate overall compliance score (0-1)."""
    score = 0.0

    # Policy readiness (40%)
    score += policy_eval["readiness"] * 0.4

    # Violations (30% - deduct for violations)
    violation_penalty = min(len(violations) * 0.05, 0.3)
    score += (0.3 - violation_penalty)

    # Quota usage (15% - good if not maxed out)
    if quota_usage < 0.9:
        score += 0.15
    else:
        score += 0.15 * (1.0 - quota_usage)

    # Task health (15%)
    score += task_health["success_rate"] * 0.15

    return min(1.0, max(0.0, score))


def _get_recent_violations(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
    """Get recent governance violations from audit log."""
    violations = []

    try:
        audit_dir = Path(__file__).parent.parent / "data" / "telemetry" / "agents"
        audit_file = audit_dir / "agent_activity.jsonl"

        if not audit_file.exists():
            return []

        cutoff = datetime.utcnow() - timedelta(days=days)

        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                    if event.get("event_type") == "autonomy_violation_detected":
                        if event.get("user_id") == user_id:
                            timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", ""))
                            if timestamp >= cutoff:
                                violations.append(event)
                except:
                    continue

    except Exception as e:
        print(f"[hc_governance] Error reading violations: {e}")

    return violations


def _emit_governance_violation(user_id: str, action: str, violations: List[str]):
    """Emit audit event for governance violation."""
    try:
        audit_dir = Path(__file__).parent.parent / "data" / "telemetry" / "agents"
        audit_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "event_type": "autonomy_violation_detected",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "action": action,
            "violations": violations
        }

        audit_file = audit_dir / "agent_activity.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    except Exception as e:
        print(f"[hc_governance] Failed to emit violation event: {e}")


def emit_governance_review_required(user_id: str, reason: str):
    """Emit audit event indicating governance review is needed."""
    try:
        audit_dir = Path(__file__).parent.parent / "data" / "telemetry" / "agents"
        audit_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "event_type": "governance_review_required",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "reason": reason
        }

        audit_file = audit_dir / "agent_activity.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    except Exception as e:
        print(f"[hc_governance] Failed to emit review event: {e}")
