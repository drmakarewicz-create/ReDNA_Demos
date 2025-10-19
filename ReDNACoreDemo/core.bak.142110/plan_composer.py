"""Plan Composer: Generates 3-step game plans from top curiosity deltas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json

from . import curiosity_engine, storage

_PLANS_DIR = "plans"
_INDEX_FILENAME = "index.json"


@dataclass
class Step:
    """Single step in a game plan."""
    number: int
    action: str
    rationale: str
    effort: str  # "low", "medium", "high"
    impact: str  # "low", "medium", "high"
    estimated_minutes: int
    coach_delegation: Optional[str] = None
    status: str = "pending"  # "pending", "completed", "skipped"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GamePlan:
    """3-step game plan focused on reducing curiosity in a specific area."""
    id: str
    user_id: str
    created_at: str
    focus_area: str  # Trait path (e.g., "PaDNA.LooksDNA.Style")
    curiosity_score: float
    goal: str
    steps: List[Step] = field(default_factory=list)
    status: str = "active"  # "active", "completed", "abandoned"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.as_dict() for step in self.steps]
        return payload

    def summary(self) -> Dict[str, Any]:
        """Lightweight summary for index."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "focus_area": self.focus_area,
            "curiosity_score": self.curiosity_score,
            "goal": self.goal,
            "status": self.status,
            "step_count": len(self.steps),
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _make_plan_id(user_id: str, focus_area: str, timestamp: str) -> str:
    """Generate unique plan ID."""
    token = f"{user_id}|{focus_area}|{timestamp}".encode("utf-8")
    return hashlib.sha1(token).hexdigest()[:12]


def _trait_family(trait_path: str) -> str:
    """Extract trait family from path (e.g., PaDNA.LooksDNA → LooksDNA)."""
    parts = trait_path.split(".")
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else "Unknown"


def _human_trait_name(trait_path: str) -> str:
    """Convert trait path to human-readable name."""
    return trait_path.split(".")[-1].replace("_", " ").title()


def _get_coach_for_family(family: str) -> Optional[str]:
    """Map trait family to responsible coach."""
    coach_map = {
        "LooksDNA": "Photo Coach",
        "StyleDNA": "Photo Coach",
        "RelationshipDNA": "Relationship Coach",
        "CareerDNA": "Career Coach",
        "HealthDNA": "Wellness Coach",
        "InterestsDNA": "Exploration Coach",
    }
    return coach_map.get(family)


def _generate_steps_rule_based(trait_path: str, curiosity_score: float) -> List[Step]:
    """Generate 3-step plan using rule-based templates."""
    family = _trait_family(trait_path)
    trait_name = _human_trait_name(trait_path)
    coach = _get_coach_for_family(family) or "Head Coach"

    # Step 1: Quick Data Gather (Low Effort, Medium Impact)
    step1 = Step(
        number=1,
        action=f"Ask {coach} to pose 2-3 direct questions about {trait_name}",
        rationale="Gather immediate signals through targeted questions",
        effort="low",
        impact="medium",
        estimated_minutes=3,
        coach_delegation=coach,
        status="pending",
    )

    # Step 2: Observation Task (Medium Effort, High Impact)
    if family in ["LooksDNA", "StyleDNA"]:
        step2_action = f"Review recent photos/outfits, note patterns in {trait_name}"
        step2_rationale = "Behavioral evidence from past choices reveals preferences"
    elif family == "RelationshipDNA":
        step2_action = f"Reflect on recent interactions, identify {trait_name} moments"
        step2_rationale = "Relationship patterns surface in reflection on real interactions"
    else:
        step2_action = f"Journal about recent experiences with {trait_name} (10 min)"
        step2_rationale = "Self-reflection uncovers nuanced signals and patterns"

    step2 = Step(
        number=2,
        action=step2_action,
        rationale=step2_rationale,
        effort="medium",
        impact="high",
        estimated_minutes=12,
        coach_delegation=coach,
        status="pending",
    )

    # Step 3: Behavioral Micro-Action (Low Effort, Low Impact)
    if family in ["LooksDNA", "StyleDNA"]:
        step3_action = f"Take one photo that highlights your {trait_name} preference"
        step3_rationale="Creates new evidence and reinforces self-awareness"
    elif family == "RelationshipDNA":
        step3_action = f"Try one small action that exercises your {trait_name} today"
        step3_rationale = "Micro-action surfaces trait in real behavior"
    else:
        step3_action = f"Note one instance where {trait_name} showed up today"
        step3_rationale = "Active noticing builds trait awareness over time"

    step3 = Step(
        number=3,
        action=step3_action,
        rationale=step3_rationale,
        effort="low",
        impact="low",
        estimated_minutes=5,
        coach_delegation=coach,
        status="pending",
    )

    return [step1, step2, step3]


def compose_plan(user_id: str, focus_override: Optional[str] = None) -> GamePlan:
    """
    Generate a 3-step game plan from top curiosity delta.

    Args:
        user_id: User identifier
        focus_override: Optional trait path to focus on (if None, uses top curiosity)

    Returns:
        GamePlan with 3 steps targeting focus area

    Example:
        >>> plan = compose_plan("test_user")
        >>> print(plan.focus_area)
        'PaDNA.LooksDNA.Style'
        >>> print(len(plan.steps))
        3
    """
    # Get focus area
    if focus_override:
        focus_area = focus_override
        curiosity_score = 0.75  # Default if override provided
    else:
        # Get top curiosity delta
        if not curiosity_engine.is_enabled():
            # Fallback if curiosity engine disabled
            focus_area = "PaDNA.General.Preferences"
            curiosity_score = 0.5
        else:
            try:
                deltas = curiosity_engine.compute_curiosity(user_id)
                if deltas and len(deltas) > 0:
                    top_delta = deltas[0]
                    focus_area = top_delta.get("trait", "PaDNA.General")
                    curiosity_score = top_delta.get("curiosity", 0.5)
                else:
                    focus_area = "PaDNA.General.Preferences"
                    curiosity_score = 0.3
            except Exception:
                focus_area = "PaDNA.General.Preferences"
                curiosity_score = 0.5

    # Generate timestamp and plan ID
    now = _now()
    timestamp = _iso(now)
    plan_id = _make_plan_id(user_id, focus_area, timestamp)

    # Generate goal
    trait_name = _human_trait_name(focus_area)
    goal = f"Reduce uncertainty around {trait_name}"

    # Generate 3 steps
    steps = _generate_steps_rule_based(focus_area, curiosity_score)

    # Create GamePlan
    plan = GamePlan(
        id=plan_id,
        user_id=user_id,
        created_at=timestamp,
        focus_area=focus_area,
        curiosity_score=curiosity_score,
        goal=goal,
        steps=steps,
        status="active",
        metadata={"generation_method": "rule_based"},
    )

    # Persist plan
    persist_plan(user_id, plan)

    return plan


def persist_plan(user_id: str, plan: GamePlan) -> None:
    """Save plan to user's plans directory and update index."""
    paths = storage.ensure_dirs_for_user(user_id)
    plans_dir = paths["udir"] / _PLANS_DIR
    plans_dir.mkdir(exist_ok=True)

    # Save full plan
    timestamp_slug = plan.created_at.replace(":", "").replace("-", "").split(".")[0]
    plan_filename = f"plan_{timestamp_slug}.json"
    plan_path = plans_dir / plan_filename
    storage.save_json(plan_path, plan.as_dict())

    # Update index
    index_path = plans_dir / _INDEX_FILENAME
    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        index = []

    # Add or update summary in index
    summary = plan.summary()
    # Remove old entry if exists
    index = [item for item in index if item.get("id") != plan.id]
    index.insert(0, summary)  # Most recent first

    # Keep only last 50 summaries
    index = index[:50]
    storage.save_json(index_path, index)


def get_plan_history(user_id: str, limit: int = 10) -> List[GamePlan]:
    """
    Load past plans from storage (most recent first).

    Args:
        user_id: User identifier
        limit: Max number of plans to return

    Returns:
        List of GamePlan objects
    """
    paths = storage.ensure_dirs_for_user(user_id)
    plans_dir = paths["udir"] / _PLANS_DIR
    index_path = plans_dir / _INDEX_FILENAME

    if not index_path.exists():
        return []

    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        return []

    plans: List[GamePlan] = []
    for summary in index[:limit]:
        plan_id = summary.get("id")
        if not plan_id:
            continue

        # Find plan file (search by ID in filename or load all and filter)
        # For simplicity, we'll reconstruct filename from created_at
        created_at = summary.get("created_at", "")
        if not created_at:
            continue

        timestamp_slug = created_at.replace(":", "").replace("-", "").split(".")[0]
        plan_filename = f"plan_{timestamp_slug}.json"
        plan_path = plans_dir / plan_filename

        if not plan_path.exists():
            continue

        plan_data = storage.load_json(plan_path, default={})
        if not isinstance(plan_data, dict):
            continue

        # Reconstruct GamePlan from dict
        steps_data = plan_data.get("steps", [])
        steps = [Step(**step_dict) for step_dict in steps_data if isinstance(step_dict, dict)]

        plan = GamePlan(
            id=plan_data.get("id", plan_id),
            user_id=plan_data.get("user_id", user_id),
            created_at=plan_data.get("created_at", ""),
            focus_area=plan_data.get("focus_area", ""),
            curiosity_score=plan_data.get("curiosity_score", 0.0),
            goal=plan_data.get("goal", ""),
            steps=steps,
            status=plan_data.get("status", "active"),
            metadata=plan_data.get("metadata", {}),
        )
        plans.append(plan)

    return plans


def update_plan_status(user_id: str, plan_id: str, status: str) -> Optional[GamePlan]:
    """
    Update plan status (active, completed, abandoned).

    Args:
        user_id: User identifier
        plan_id: Plan ID
        status: New status

    Returns:
        Updated GamePlan or None if not found
    """
    if status not in ["active", "completed", "abandoned"]:
        raise ValueError(f"Invalid status: {status}")

    paths = storage.ensure_dirs_for_user(user_id)
    plans_dir = paths["udir"] / _PLANS_DIR
    index_path = plans_dir / _INDEX_FILENAME

    if not index_path.exists():
        return None

    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        return None

    # Find plan in index
    plan_summary = None
    for summary in index:
        if summary.get("id") == plan_id:
            plan_summary = summary
            break

    if not plan_summary:
        return None

    # Load full plan
    created_at = plan_summary.get("created_at", "")
    timestamp_slug = created_at.replace(":", "").replace("-", "").split(".")[0]
    plan_filename = f"plan_{timestamp_slug}.json"
    plan_path = plans_dir / plan_filename

    if not plan_path.exists():
        return None

    plan_data = storage.load_json(plan_path, default={})
    if not isinstance(plan_data, dict):
        return None

    # Update status
    plan_data["status"] = status
    storage.save_json(plan_path, plan_data)

    # Update index
    for summary in index:
        if summary.get("id") == plan_id:
            summary["status"] = status
            break
    storage.save_json(index_path, index)

    # Reconstruct and return
    steps_data = plan_data.get("steps", [])
    steps = [Step(**step_dict) for step_dict in steps_data if isinstance(step_dict, dict)]

    return GamePlan(
        id=plan_data.get("id", plan_id),
        user_id=plan_data.get("user_id", user_id),
        created_at=plan_data.get("created_at", ""),
        focus_area=plan_data.get("focus_area", ""),
        curiosity_score=plan_data.get("curiosity_score", 0.0),
        goal=plan_data.get("goal", ""),
        steps=steps,
        status=status,
        metadata=plan_data.get("metadata", {}),
    )


def update_step_status(user_id: str, plan_id: str, step_number: int, status: str) -> Optional[GamePlan]:
    """
    Update individual step status within a plan.

    Args:
        user_id: User identifier
        plan_id: Plan ID
        step_number: Step number (1, 2, or 3)
        status: New status ("pending", "completed", "skipped")

    Returns:
        Updated GamePlan or None if not found
    """
    if status not in ["pending", "completed", "skipped"]:
        raise ValueError(f"Invalid step status: {status}")

    paths = storage.ensure_dirs_for_user(user_id)
    plans_dir = paths["udir"] / _PLANS_DIR
    index_path = plans_dir / _INDEX_FILENAME

    if not index_path.exists():
        return None

    index = storage.load_json(index_path, default=[])
    if not isinstance(index, list):
        return None

    # Find plan in index
    plan_summary = None
    for summary in index:
        if summary.get("id") == plan_id:
            plan_summary = summary
            break

    if not plan_summary:
        return None

    # Load full plan
    created_at = plan_summary.get("created_at", "")
    timestamp_slug = created_at.replace(":", "").replace("-", "").split(".")[0]
    plan_filename = f"plan_{timestamp_slug}.json"
    plan_path = plans_dir / plan_filename

    if not plan_path.exists():
        return None

    plan_data = storage.load_json(plan_path, default={})
    if not isinstance(plan_data, dict):
        return None

    # Update step status
    steps_data = plan_data.get("steps", [])
    for step_dict in steps_data:
        if step_dict.get("number") == step_number:
            step_dict["status"] = status
            break

    plan_data["steps"] = steps_data
    storage.save_json(plan_path, plan_data)

    # Check if all steps completed → mark plan complete
    all_completed = all(s.get("status") == "completed" for s in steps_data)
    if all_completed and plan_data.get("status") == "active":
        plan_data["status"] = "completed"
        storage.save_json(plan_path, plan_data)
        # Update index
        for summary in index:
            if summary.get("id") == plan_id:
                summary["status"] = "completed"
                break
        storage.save_json(index_path, index)

    # Reconstruct and return
    steps = [Step(**step_dict) for step_dict in steps_data if isinstance(step_dict, dict)]

    return GamePlan(
        id=plan_data.get("id", plan_id),
        user_id=plan_data.get("user_id", user_id),
        created_at=plan_data.get("created_at", ""),
        focus_area=plan_data.get("focus_area", ""),
        curiosity_score=plan_data.get("curiosity_score", 0.0),
        goal=plan_data.get("goal", ""),
        steps=steps,
        status=plan_data.get("status", "active"),
        metadata=plan_data.get("metadata", {}),
    )


__all__ = [
    "Step",
    "GamePlan",
    "compose_plan",
    "persist_plan",
    "get_plan_history",
    "update_plan_status",
    "update_step_status",
]
