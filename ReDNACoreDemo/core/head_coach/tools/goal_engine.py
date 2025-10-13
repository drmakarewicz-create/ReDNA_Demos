from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Goal:
    goal_id: str
    title: str
    description: str
    target_date: datetime
    category: str
    status: str = "active"
    progress_percentage: float = 0.0


class GoalEngine:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._data_path = Path("data") / "tools" / "goals" / f"{user_id}.json"

    def create_goal(
        self,
        *,
        title: str,
        description: str,
        category: str,
        target_date: datetime,
    ) -> Goal:
        return Goal(
            goal_id=f"goal-{datetime.now().timestamp():.0f}",
            title=title,
            description=description,
            category=category,
            target_date=target_date,
        )

    def progress_summary(self, goals: Optional[List[Goal]] = None) -> Dict[str, float]:
        goals = goals or []
        total = len(goals)
        completed = sum(1 for goal in goals if goal.progress_percentage >= 100.0)
        return {
            "total_goals": total,
            "completed": completed,
            "completion_rate": (completed / total) if total else 0.0,
        }

