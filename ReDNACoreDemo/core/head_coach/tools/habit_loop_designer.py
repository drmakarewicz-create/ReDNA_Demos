from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Habit:
    habit_id: str
    name: str
    cue: str
    routine: str
    reward: str
    streak: int = 0
    longest_streak: int = 0
    status: str = "active"


class HabitLoopDesigner:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._data_path = Path("data") / "tools" / "habits" / f"{user_id}.json"

    def design_habit(self, *, behavior: str, cue: str, reward: str) -> Habit:
        return Habit(
            habit_id=f"habit-{datetime.now().timestamp():.0f}",
            name=behavior,
            cue=cue,
            routine=behavior,
            reward=reward,
        )

    def log_completion(self, habit: Habit, completed: bool) -> Habit:
        if completed:
            habit.streak += 1
            habit.longest_streak = max(habit.longest_streak, habit.streak)
        else:
            habit.streak = 0
        return habit

