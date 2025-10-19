"""
Head Coach Self-Scheduling System

Implements per-agent schedule registry and task execution hooks
for autonomous maintenance tasks.

Phase 5.A: Autonomy Graduation
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from .hc_autonomy import load_autonomy_policy, get_autonomy_dir


class TaskType(Enum):
    """Supported autonomous task types."""
    LIFE_WEEKLY_REVIEW = "life_weekly_review"
    NARRATOR_WEEKLY_SUMMARY = "narrator_weekly_summary"
    LEARNING_UPDATE = "learning_update"
    LIFE_VOICE_SUMMARY = "life_voice_summary"


@dataclass
class ScheduleTask:
    """A scheduled task for a Head Coach."""
    task_type: str
    interval_days: int = 7
    last_run: Optional[str] = None  # ISO timestamp
    next_run: Optional[str] = None  # ISO timestamp
    enabled: bool = True
    run_count: int = 0
    failure_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ScheduleState:
    """Schedule state for a user's Head Coach."""
    user_id: str
    tasks: Dict[str, ScheduleTask] = field(default_factory=dict)
    actions_today: int = 0
    last_reset: str = field(default_factory=lambda: datetime.utcnow().date().isoformat())
    total_actions: int = 0
    version: str = "5.A.1"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "tasks": {k: asdict(v) for k, v in self.tasks.items()},
            "actions_today": self.actions_today,
            "last_reset": self.last_reset,
            "total_actions": self.total_actions,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduleState':
        """Create from dictionary."""
        tasks = {}
        for k, v in data.get("tasks", {}).items():
            tasks[k] = ScheduleTask(**v)

        return cls(
            user_id=data["user_id"],
            tasks=tasks,
            actions_today=data.get("actions_today", 0),
            last_reset=data.get("last_reset", datetime.utcnow().date().isoformat()),
            total_actions=data.get("total_actions", 0),
            version=data.get("version", "5.A.1")
        )


def load_schedule_state(user_id: str) -> ScheduleState:
    """Load schedule state for user."""
    state_path = get_autonomy_dir(user_id) / "schedule_state.json"

    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScheduleState.from_dict(data)
        except Exception as e:
            print(f"[hc_scheduler] Error loading schedule state for {user_id}: {e}")
            return _create_default_schedule(user_id)
    else:
        return _create_default_schedule(user_id)


def save_schedule_state(state: ScheduleState) -> bool:
    """Save schedule state."""
    state_path = get_autonomy_dir(state.user_id) / "schedule_state.json"

    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)
        return True
    except Exception as e:
        print(f"[hc_scheduler] Error saving schedule state: {e}")
        return False


def _create_default_schedule(user_id: str) -> ScheduleState:
    """Create default schedule with standard tasks."""
    state = ScheduleState(user_id=user_id)

    # Default tasks
    state.tasks[TaskType.LIFE_WEEKLY_REVIEW.value] = ScheduleTask(
        task_type=TaskType.LIFE_WEEKLY_REVIEW.value,
        interval_days=7,
        enabled=True
    )

    state.tasks[TaskType.NARRATOR_WEEKLY_SUMMARY.value] = ScheduleTask(
        task_type=TaskType.NARRATOR_WEEKLY_SUMMARY.value,
        interval_days=7,
        enabled=True
    )

    state.tasks[TaskType.LEARNING_UPDATE.value] = ScheduleTask(
        task_type=TaskType.LEARNING_UPDATE.value,
        interval_days=7,
        enabled=True
    )

    state.tasks[TaskType.LIFE_VOICE_SUMMARY.value] = ScheduleTask(
        task_type=TaskType.LIFE_VOICE_SUMMARY.value,
        interval_days=7,
        enabled=False  # Optional, off by default
    )

    # Calculate initial next_run times (stagger them)
    now = datetime.utcnow()
    for i, task_key in enumerate(state.tasks.keys()):
        # Stagger by days to avoid running all at once
        offset_days = i * 2
        state.tasks[task_key].next_run = (now + timedelta(days=offset_days)).isoformat() + "Z"

    save_schedule_state(state)
    return state


def get_eligible_tasks(user_id: str) -> List[ScheduleTask]:
    """
    Get tasks eligible to run now.

    Checks:
      - Policy allows self-scheduling
      - Task is enabled
      - next_run time has passed
      - Daily quota not exceeded
    """
    policy = load_autonomy_policy(user_id)

    # Must have self-scheduling enabled
    if not policy.self_schedule:
        return []

    state = load_schedule_state(user_id)

    # Reset daily counter if new day
    today = datetime.utcnow().date().isoformat()
    if state.last_reset != today:
        state.actions_today = 0
        state.last_reset = today
        save_schedule_state(state)

    # Check daily quota
    max_actions = policy.guardrails.get("max_self_actions_per_day", 5)
    if state.actions_today >= max_actions:
        return []

    # Find eligible tasks
    eligible = []
    now = datetime.utcnow()

    for task in state.tasks.values():
        if not task.enabled:
            continue

        # First run or time has passed
        if task.next_run is None:
            eligible.append(task)
        else:
            next_run_dt = datetime.fromisoformat(task.next_run.replace("Z", ""))
            if now >= next_run_dt:
                eligible.append(task)

    # Limit to remaining quota
    remaining = max_actions - state.actions_today
    return eligible[:remaining]


def execute_task(user_id: str, task_type: str) -> Dict[str, Any]:
    """
    Execute a scheduled task.

    Returns:
        {"success": bool, "result": Any, "error": Optional[str]}
    """
    state = load_schedule_state(user_id)
    policy = load_autonomy_policy(user_id)

    # Verify task exists
    if task_type not in state.tasks:
        return {
            "success": False,
            "result": None,
            "error": f"Unknown task type: {task_type}"
        }

    task = state.tasks[task_type]

    # Verify policy allows this
    if not _verify_task_allowed(task_type, policy):
        return {
            "success": False,
            "result": None,
            "error": f"Policy does not allow task: {task_type}"
        }

    # Execute task
    try:
        result = _execute_task_impl(user_id, task_type)

        # Update state on success
        now = datetime.utcnow()
        task.last_run = now.isoformat() + "Z"
        task.next_run = (now + timedelta(days=task.interval_days)).isoformat() + "Z"
        task.run_count += 1
        task.last_error = None

        state.actions_today += 1
        state.total_actions += 1

        save_schedule_state(state)

        # Emit audit event
        _emit_task_execution_audit(user_id, task_type, success=True)

        return {
            "success": True,
            "result": result,
            "error": None
        }

    except Exception as e:
        error_msg = str(e)
        task.failure_count += 1
        task.last_error = error_msg
        save_schedule_state(state)

        # Emit audit event
        _emit_task_execution_audit(user_id, task_type, success=False, error=error_msg)

        return {
            "success": False,
            "result": None,
            "error": error_msg
        }


def _verify_task_allowed(task_type: str, policy) -> bool:
    """Verify policy allows this task type."""
    if task_type == TaskType.LIFE_WEEKLY_REVIEW.value:
        return policy.self_reflect

    if task_type == TaskType.NARRATOR_WEEKLY_SUMMARY.value:
        return policy.self_narrate

    if task_type == TaskType.LEARNING_UPDATE.value:
        return policy.self_reflect

    if task_type == TaskType.LIFE_VOICE_SUMMARY.value:
        return policy.self_narrate

    return False


def _execute_task_impl(user_id: str, task_type: str) -> Any:
    """
    Execute the actual task implementation.

    This delegates to existing systems (life OS, narrator, learning).
    """
    if task_type == TaskType.LIFE_WEEKLY_REVIEW.value:
        return _run_weekly_review(user_id)

    elif task_type == TaskType.NARRATOR_WEEKLY_SUMMARY.value:
        return _run_narrator_summary(user_id)

    elif task_type == TaskType.LEARNING_UPDATE.value:
        return _run_learning_update(user_id)

    elif task_type == TaskType.LIFE_VOICE_SUMMARY.value:
        return _run_voice_summary(user_id)

    else:
        raise ValueError(f"Unknown task type: {task_type}")


def _run_weekly_review(user_id: str) -> Dict[str, Any]:
    """Run weekly life review."""
    try:
        from .hc_narrator import build_weekly_life_summary

        summary = build_weekly_life_summary(user_id)

        return {
            "task": "life_weekly_review",
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise RuntimeError(f"Weekly review failed: {e}")


def _run_narrator_summary(user_id: str) -> Dict[str, Any]:
    """Run narrator weekly summary."""
    try:
        from .hc_narrator import build_weekly_life_summary

        # Same as weekly review for now
        summary = build_weekly_life_summary(user_id)

        return {
            "task": "narrator_weekly_summary",
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise RuntimeError(f"Narrator summary failed: {e}")


def _run_learning_update(user_id: str) -> Dict[str, Any]:
    """Run learning system update."""
    try:
        from .hc_learning import compute_deltas

        # Load user data
        user_data_dir = Path(__file__).parent.parent / "data" / "users" / user_id
        observations_file = user_data_dir / "observations.json"

        if not observations_file.exists():
            return {
                "task": "learning_update",
                "status": "no_observations",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

        with open(observations_file, "r", encoding="utf-8") as f:
            observations = json.load(f)

        # Compute deltas (this updates learning state internally)
        deltas = compute_deltas(user_id, observations)

        return {
            "task": "learning_update",
            "deltas_count": len(deltas) if deltas else 0,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise RuntimeError(f"Learning update failed: {e}")


def _run_voice_summary(user_id: str) -> Dict[str, Any]:
    """Run voice summary generation."""
    try:
        from .hc_voice import generate_voice_summary

        summary = generate_voice_summary(user_id)

        return {
            "task": "life_voice_summary",
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        # Voice is optional, don't fail hard
        return {
            "task": "life_voice_summary",
            "status": "skipped",
            "reason": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


def run_scheduler_cycle(user_id: str) -> Dict[str, Any]:
    """
    Run one scheduler cycle for a user.

    Returns:
        {
            "tasks_executed": int,
            "results": List[Dict],
            "errors": List[str]
        }
    """
    eligible = get_eligible_tasks(user_id)

    results = []
    errors = []

    for task in eligible:
        result = execute_task(user_id, task.task_type)
        results.append({
            "task_type": task.task_type,
            "success": result["success"],
            "error": result.get("error")
        })

        if not result["success"]:
            errors.append(f"{task.task_type}: {result['error']}")

    return {
        "tasks_executed": len(results),
        "results": results,
        "errors": errors
    }


def _emit_task_execution_audit(user_id: str, task_type: str, success: bool, error: Optional[str] = None):
    """Emit audit event for task execution."""
    try:
        audit_dir = Path(__file__).parent.parent / "data" / "telemetry" / "agents"
        audit_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "event_type": "self_scheduled_job",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "task_type": task_type,
            "success": success,
            "error": error
        }

        audit_file = audit_dir / "agent_activity.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    except Exception as e:
        print(f"[hc_scheduler] Failed to emit audit event: {e}")
