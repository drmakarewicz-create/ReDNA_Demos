"""
Agent job providers for the agentic Head Coach daemon.

Connects the agent daemon to ReDNA's curiosity engine, refinement system,
and self-improvement loop to generate actionable job proposals.

Phase 3b: Adds learning_executor for weekly adaptive feedback loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

from ReDNACoreDemo import agents
from ReDNACoreDemo.core.storage import ensure_dirs_for_user

logger = logging.getLogger(__name__)


def curiosity_provider(
    user_id: str, policy: agents.AgentPolicy, state: agents.AgentState
) -> Sequence[Dict[str, Any]]:
    """
    Generate curiosity-driven exploration jobs based on gap analysis.

    Returns up to 3 high-priority traits/containers for the user to explore.
    """
    try:
        from ReDNACoreDemo.core.curiosity.curiosity_engine_v2 import CuriosityEngine

        engine = CuriosityEngine()
        agenda = engine.generate_agenda(user_id, limit=3)

        # Agenda is a dict with "items" key
        items = agenda.get("items", []) if isinstance(agenda, dict) else []

        jobs: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            # Items use "target" not "trait_id"
            target = item.get("target", "unknown")
            jobs.append({
                "job_id": f"curiosity-{user_id}-{idx}",
                "kind": "nudge",
                "payload": {
                    "trait_id": target,
                    "target": target,
                    "priority": item.get("priority"),
                    "reason": item.get("reason", "curiosity_gap"),
                    "suggested_prompt": item.get("suggested_prompt"),
                    "suggested_coach": item.get("suggested_coach"),
                },
                "required_autonomy": "semi",  # Curiosity nudges require user consent
            })

        logger.info(f"Curiosity provider generated {len(jobs)} jobs for {user_id}")
        return jobs

    except Exception as exc:
        logger.warning(f"Curiosity provider failed for {user_id}: {exc}")
        return []


def refinement_provider(
    user_id: str, policy: agents.AgentPolicy, state: agents.AgentState
) -> Sequence[Dict[str, Any]]:
    """
    Generate refinement jobs for traits with conflicts or low confidence.

    Checks the user's refinement queue and conflict log for pending work.
    """
    try:
        dirs = ensure_dirs_for_user(user_id)
        user_dir = dirs.get("udir")
        if not user_dir:
            return []

        refinement_dir = Path(user_dir) / "refinement"
        conflict_log = Path(user_dir) / "conflict_log.jsonl"

        jobs: List[Dict[str, Any]] = []

        # Check for pending refinement jobs
        if refinement_dir.exists():
            pending_files = list(refinement_dir.glob("pending_*.json"))
            for idx, file_path in enumerate(pending_files[:3]):  # Max 3
                try:
                    import json
                    with open(file_path, "r") as f:
                        refinement_data = json.load(f)

                    jobs.append({
                        "job_id": f"refine-{user_id}-{idx}",
                        "kind": "refine",
                        "payload": {
                            "trait_id": refinement_data.get("trait_id"),
                            "reason": "pending_refinement",
                            "file": str(file_path),
                        },
                        "required_autonomy": "semi",
                    })
                except Exception as exc:
                    logger.debug(f"Could not parse refinement file {file_path}: {exc}")

        # Check for unresolved conflicts
        if conflict_log.exists():
            import json
            conflicts = []
            try:
                with open(conflict_log, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            conflicts.append(json.loads(line))
            except Exception as exc:
                logger.debug(f"Could not parse conflict log: {exc}")

            # Look for recent unresolved conflicts
            unresolved = [c for c in conflicts if c.get("status") != "resolved"][-3:]
            for idx, conflict in enumerate(unresolved):
                jobs.append({
                    "job_id": f"resolve-{user_id}-{idx}",
                    "kind": "resolve",
                    "payload": {
                        "trait_id": conflict.get("trait_id"),
                        "reason": "unresolved_conflict",
                        "conflict_score": conflict.get("score"),
                    },
                    "required_autonomy": "auto",  # Conflict resolution can be automatic
                })

        logger.info(f"Refinement provider generated {len(jobs)} jobs for {user_id}")
        return jobs

    except Exception as exc:
        logger.warning(f"Refinement provider failed for {user_id}: {exc}")
        return []


def improvement_provider(
    user_id: str, policy: agents.AgentPolicy, state: agents.AgentState
) -> Sequence[Dict[str, Any]]:
    """
    Generate self-improvement analysis jobs based on telemetry.

    Proposes analysis jobs when sufficient telemetry has accumulated.
    """
    try:
        from ReDNACoreDemo.core.learning.telemetry_analyzer import get_recent_telemetry_count

        # Check if we have enough telemetry to warrant analysis
        telemetry_count = get_recent_telemetry_count(user_id, days=7)

        # Only propose improvement if we have at least 5 recent interactions
        # and haven't run improvement recently
        last_improvement_count = state.job_counts.get("analyze", 0)

        if telemetry_count >= 5 and last_improvement_count < 3:
            jobs: List[Dict[str, Any]] = [{
                "job_id": f"improve-{user_id}-analysis",
                "kind": "analyze",
                "payload": {
                    "name": "self-improvement-cycle",
                    "telemetry_count": telemetry_count,
                    "reason": "sufficient_telemetry",
                },
                "required_autonomy": "auto",  # Analysis can run automatically
            }]
            logger.info(f"Improvement provider generated 1 job for {user_id}")
            return jobs

        return []

    except Exception as exc:
        logger.warning(f"Improvement provider failed for {user_id}: {exc}")
        return []


# Fallback helper for telemetry counting
def get_recent_telemetry_count(user_id: str, days: int = 7) -> int:
    """
    Count recent telemetry events for a user.

    Fallback implementation if learning module doesn't export this.
    """
    try:
        from datetime import datetime, timedelta, timezone
        import json
        from ReDNACoreDemo.core.storage import ensure_dirs_for_user

        dirs = ensure_dirs_for_user(user_id)
        user_dir = dirs.get("udir")
        if not user_dir:
            return 0

        events_dir = Path(user_dir) / "events"
        if not events_dir.exists():
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0

        for event_file in events_dir.glob("chat_turn_*.json"):
            try:
                stat = event_file.stat()
                if datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc) > cutoff:
                    count += 1
            except Exception:
                continue

        return count

    except Exception as exc:
        logger.debug(f"Telemetry count failed: {exc}")
        return 0


# Monkey-patch the telemetry analyzer if it doesn't have this function
try:
    from ReDNACoreDemo.core.learning import telemetry_analyzer
    if not hasattr(telemetry_analyzer, 'get_recent_telemetry_count'):
        telemetry_analyzer.get_recent_telemetry_count = get_recent_telemetry_count
except ImportError:
    pass


def life_os_daily_provider(
    user_id: str, policy: agents.AgentPolicy, state: agents.AgentState
) -> Sequence[Dict[str, Any]]:
    """
    Generate daily Life OS nudge jobs for Today's 3 tasks.

    Proposes "Today's 3" when:
    - It's the start of a new day (8am local or first daemon run after midnight)
    - The user has no tasks scheduled for today
    - User has L2+ autonomy

    For L1 (propose-only), just logs a proposed set.
    For L2+ (auto), can auto-populate from high-priority goals.
    """
    try:
        from datetime import datetime, timezone
        from ReDNACoreDemo.core import hc_life

        # Check if we need to propose Today's 3
        today_todos = hc_life.list_todos(user_id, scope="today", status="open")

        # Only propose if empty
        if len(today_todos) > 0:
            return []

        # Check when we last proposed (to avoid spamming) using job_counts as proxy
        # Count existing "life_daily_three" jobs to avoid proposing too frequently
        daily_count = state.job_counts.get("life_daily_three", 0)
        if daily_count > 0:
            # Already proposed at least once - skip for now
            # TODO: Add time-based check in future iteration
            return []

        # Try to get Important/Urgent task from priority matrix (Phase 2)
        suggestions = []
        try:
            from ReDNACoreDemo.core.hc_life_projects import get_important_urgent_task
            urgent_todo_id = get_important_urgent_task(user_id)
            if urgent_todo_id:
                urgent_todo = hc_life.get_todo(user_id, urgent_todo_id)
                if urgent_todo:
                    suggestions.append({
                        "text": urgent_todo.text,
                        "todo_id": urgent_todo.id,
                        "priority": 1.0,
                        "reason": "Important & Urgent from Priority Matrix"
                    })
        except ImportError:
            pass  # Phase 2 not yet available

        # Get active goals to derive suggestions
        active_goals = hc_life.list_goals(user_id, status="active")

        # Build suggested todos from goals' first_step and due dates
        for goal in active_goals[:3]:  # Top 3 goals
            if goal.first_step:
                suggestions.append({
                    "text": goal.first_step,
                    "goal_id": goal.id,
                    "priority": goal.confidence,
                    "reason": f"Next step for: {goal.text}"
                })

        # Limit to top 3
        suggestions = suggestions[:3]

        # If we have suggestions, create a job
        if suggestions:
            jobs: List[Dict[str, Any]] = [{
                "job_id": f"life-daily-{user_id}",
                "kind": "life_daily_three",
                "payload": {
                    "suggestions": suggestions,
                    "reason": "today_three_empty",
                },
                "required_autonomy": "semi",  # Requires user approval
                "metadata": {
                    "proposed_at": datetime.now(timezone.utc).isoformat()
                }
            }]
            logger.info(f"Life OS daily provider generated 1 job for {user_id}")
            return jobs

        return []

    except Exception as exc:
        logger.warning(f"Life OS daily provider failed for {user_id}: {exc}")
        return []


def learning_executor(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute learning update job (Phase 3b).

    Computes learning deltas from Life OS insights and applies them to user state.
    Updates agent state metadata with last_learning_update timestamp.

    Args:
        user_id: User identifier
        payload: Job payload with 'days' parameter

    Returns:
        Dict with execution result
    """
    try:
        from ReDNACoreDemo.core import hc_learning
        from datetime import datetime, timezone

        days = payload.get("days", 14)

        # Compute and apply learning deltas
        deltas = hc_learning.compute_learning_deltas(user_id, days=days)
        state = hc_learning.apply_learning_deltas(user_id, deltas)

        # Update agent state metadata (called by daemon after execution)
        # The daemon will handle this via state.metadata update

        logger.info(f"Learning update completed for {user_id}: update_count={state.update_count}")

        return {
            "status": "ok",
            "message": "Learning state updated successfully",
            "update_count": state.update_count,
            "tone_bias": state.tone_bias,
            "creativity_bias": state.creativity_bias,
            "nudge_frequency_multiplier": state.nudge_frequency_multiplier,
            "focus_areas": list(state.focus_weights.keys())[:5],
            "insights_snapshot": deltas.get("insights_snapshot", {})
        }

    except Exception as exc:
        logger.error(f"Learning executor failed for {user_id}: {exc}")
        return {
            "status": "error",
            "message": str(exc)
        }
