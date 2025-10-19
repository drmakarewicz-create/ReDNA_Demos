from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FinancialGoal:
    goal_id: str
    name: str
    target_amount: float
    current_amount: float
    target_date: datetime
    priority: str  # "high", "medium", "low"
    category: str  # "savings", "debt_payoff", etc.


@dataclass
class BudgetSnapshot:
    month: str
    income: float
    expenses: float
    savings_rate: float


class FinancialPlanner:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._data_path = Path("data") / "tools" / "financial" / f"{user_id}.json"

    def summarize_finances(self) -> Dict[str, float]:
        # Dummy placeholder logic for scaffolding
        return {
            "monthly_income": 0.0,
            "monthly_expenses": 0.0,
            "net_savings": 0.0,
        }

    def track_goal(self, goal: FinancialGoal) -> Dict[str, float]:
        remaining = max(0.0, goal.target_amount - goal.current_amount)
        days_left = max(1, (goal.target_date - datetime.now()).days)
        daily_needed = remaining / days_left
        return {
            "goal_id": goal.goal_id,
            "remaining": remaining,
            "daily_needed": daily_needed,
        }

    def budget_overview(self) -> BudgetSnapshot:
        return BudgetSnapshot(month=datetime.now().strftime("%Y-%m"), income=0.0, expenses=0.0, savings_rate=0.0)

