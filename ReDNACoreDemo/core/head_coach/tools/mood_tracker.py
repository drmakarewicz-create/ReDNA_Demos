from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class MoodLevel(Enum):
    VERY_NEGATIVE = 1
    NEGATIVE = 2
    NEUTRAL = 3
    POSITIVE = 4
    VERY_POSITIVE = 5


@dataclass
class MoodEntry:
    entry_id: str
    timestamp: datetime
    mood_level: MoodLevel
    emotions: List[str]
    intensity: float
    context: Dict[str, str]
    notes: Optional[str]


class MoodTracker:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._data_path = Path("data") / "tools" / "mood" / f"{user_id}.json"

    def log_mood(
        self,
        *,
        mood_level: MoodLevel,
        emotions: Optional[List[str]] = None,
        context: Optional[Dict[str, str]] = None,
        notes: Optional[str] = None,
    ) -> MoodEntry:
        entry = MoodEntry(
            entry_id=f"mood-{datetime.now().timestamp():.0f}",
            timestamp=datetime.now(),
            mood_level=mood_level,
            emotions=emotions or [],
            intensity=min(1.0, max(0.0, len(emotions or []) * 0.1 + 0.5)),
            context=context or {},
            notes=notes,
        )
        return entry

    def summarize_recent(self, *, days: int = 7) -> Dict[str, float]:
        cutoff = datetime.now() - timedelta(days=days)
        # Placeholder: no persistence yet
        return {"average_mood": MoodLevel.NEUTRAL.value, "entries_count": 0, "period_days": days, "since": cutoff.isoformat()}

