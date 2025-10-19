"""
Phase 10 adaptive analytics metrics engine.

Transforms ontology telemetry and Life OS data into persona-aware metrics that
feed adaptive analytics, predictive insights, and DevX visualizations.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

from ..storage import USERS_DIR

# -----------------------------------------------------------------------------
# Helper data structures
# -----------------------------------------------------------------------------


def _parse_iso_ts(value: str) -> datetime:
    """Parse ISO-8601 timestamps with safe fallbacks."""
    if not value:
        return datetime.now(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        # Attempt truncated seconds
        try:
            return datetime.fromisoformat(normalized.split(".")[0] + "+00:00")
        except Exception:
            return datetime.now(timezone.utc)


def _to_date(ts: datetime) -> date:
    """Convert timestamp to UTC date."""
    return ts.astimezone(timezone.utc).date()


@dataclass
class ContainerUsageEvent:
    container_id: str
    persona: str
    timestamp: datetime
    weight: float = 1.0


@dataclass
class LifeOsMetrics:
    user_id: str
    tasks_completed_by_day: Dict[date, int] = field(default_factory=dict)
    curiosity_delta_by_day: Dict[date, float] = field(default_factory=dict)
    goal_confidence_avg: float = 0.0
    goals_total: int = 0
    curated_notes: Dict[str, float] = field(default_factory=dict)

    @property
    def daily_learning_velocity(self) -> List[Tuple[date, float]]:
        """Combine task completions and curiosity deltas per day."""
        days = sorted({*self.tasks_completed_by_day.keys(), *self.curiosity_delta_by_day.keys()})
        result: List[Tuple[date, float]] = []
        for day in days:
            tasks = self.tasks_completed_by_day.get(day, 0)
            curiosity = self.curiosity_delta_by_day.get(day, 0.0)
            # Weighted contribution: tasks drive core velocity, curiosity nudges finesse.
            velocity = tasks + curiosity
            result.append((day, velocity))
        return result

    @property
    def rolling_7d_average(self) -> float:
        """Compute adaptive rolling average over the last 7 days."""
        if not self.daily_learning_velocity:
            return 0.0

        cutoff = date.today() - timedelta(days=6)
        recent_values = [value for day, value in self.daily_learning_velocity if day >= cutoff]

        if not recent_values:
            return 0.0

        return sum(recent_values) / len(recent_values)


@dataclass
class MetricsSnapshot:
    user_id: str
    persona_totals: Dict[str, float]
    container_totals: Dict[str, float]
    container_persona_counts: Dict[str, Dict[str, float]]
    life_os: LifeOsMetrics

    def serialize_learning_velocity(self) -> List[Dict[str, str | float]]:
        """Return learning velocity data in JSON-serializable format."""
        return [
            {"date": day.isoformat(), "value": value}
            for day, value in self.life_os.daily_learning_velocity
        ]


# -----------------------------------------------------------------------------
# Metrics Engine
# -----------------------------------------------------------------------------


class MetricsEngine:
    """
    Collects ontology telemetry, persona usage, and Life OS metrics.

    Responsible for normalizing disparate data sources and producing snapshots
    that downstream adaptive analytics components can consume.
    """

    def __init__(self, users_dir: Path | None = None):
        self.users_dir = Path(users_dir) if users_dir else USERS_DIR
        self._snapshots: Dict[str, MetricsSnapshot] = {}
        self._last_refresh: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, force: bool = False) -> Dict[str, MetricsSnapshot]:
        """
        Refresh metrics from disk.

        Args:
            force: When True, ignore caching and rebuild snapshots immediately.
        """
        if not force and self._last_refresh:
            if (datetime.now(timezone.utc) - self._last_refresh) < timedelta(seconds=5):
                return self._snapshots

        snapshots: Dict[str, MetricsSnapshot] = {}

        if not self.users_dir.exists():
            self._snapshots = {}
            self._last_refresh = datetime.now(timezone.utc)
            return self._snapshots

        for user_dir in sorted(p for p in self.users_dir.iterdir() if p.is_dir()):
            user_id = user_dir.name
            container_events = self._load_container_usage(user_dir)
            if not container_events:
                # Even without telemetry, attempt to pull Life OS metrics so the
                # dashboard can surface progress, otherwise skip the user.
                life_os_metrics = self._load_life_os_metrics(user_id, user_dir)
                if not life_os_metrics.daily_learning_velocity:
                    continue
                snapshot = MetricsSnapshot(
                    user_id=user_id,
                    persona_totals={},
                    container_totals={},
                    container_persona_counts={},
                    life_os=life_os_metrics,
                )
                snapshots[user_id] = snapshot
                continue

            persona_totals: DefaultDict[str, float] = defaultdict(float)
            container_totals: DefaultDict[str, float] = defaultdict(float)
            container_persona_counts: DefaultDict[str, DefaultDict[str, float]] = defaultdict(lambda: defaultdict(float))

            for event in container_events:
                persona_totals[event.persona] += event.weight
                container_totals[event.container_id] += event.weight
                container_persona_counts[event.container_id][event.persona] += event.weight

            life_os_metrics = self._load_life_os_metrics(user_id, user_dir)

            snapshot = MetricsSnapshot(
                user_id=user_id,
                persona_totals=dict(persona_totals),
                container_totals=dict(container_totals),
                container_persona_counts={
                    container: dict(persona_counts)
                    for container, persona_counts in container_persona_counts.items()
                },
                life_os=life_os_metrics,
            )
            snapshots[user_id] = snapshot

        self._snapshots = snapshots
        self._last_refresh = datetime.now(timezone.utc)
        return self._snapshots

    def snapshot(self, user_id: str) -> Optional[MetricsSnapshot]:
        """Return cached snapshot for a user."""
        if user_id not in self._snapshots:
            self.refresh()
        return self._snapshots.get(user_id)

    def all_snapshots(self) -> Dict[str, MetricsSnapshot]:
        """Return all cached snapshots (refreshing when needed)."""
        self.refresh()
        return self._snapshots

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _load_container_usage(self, user_dir: Path) -> List[ContainerUsageEvent]:
        """Load container usage events from observation logs."""
        events: List[ContainerUsageEvent] = []

        flat_json = user_dir / "observations.json"
        if flat_json.exists():
            try:
                data = json.loads(flat_json.read_text(encoding="utf-8"))
                items = data.get("items", [])
                events.extend(self._parse_observation_items(items))
            except json.JSONDecodeError:
                pass

        jsonl_path = user_dir / "observations.jsonl"
        if jsonl_path.exists():
            events.extend(self._parse_jsonl_observations(jsonl_path))

        # Additional refinement directory events
        refinement_dir = user_dir / "refinement"
        if refinement_dir.exists():
            for jsonl in refinement_dir.glob("*.jsonl"):
                events.extend(self._parse_jsonl_observations(jsonl))

        return events

    def _parse_observation_items(self, items: Iterable[Dict[str, object]]) -> List[ContainerUsageEvent]:
        """Parse structured observation JSON items."""
        events: List[ContainerUsageEvent] = []
        for item in items:
            container_id = str(item.get("container") or item.get("trait_id") or "")
            if not container_id:
                continue
            persona = str(item.get("persona") or "unspecified").lower()
            timestamp = _parse_iso_ts(str(item.get("ts") or ""))
            weight = float(item.get("weight") or 1.0)
            events.append(ContainerUsageEvent(container_id=container_id, persona=persona, timestamp=timestamp, weight=weight))
        return events

    def _parse_jsonl_observations(self, path: Path) -> List[ContainerUsageEvent]:
        """Parse observation entries from JSONL log."""
        events: List[ContainerUsageEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                container_id = str(payload.get("container") or payload.get("trait_id") or "")
                if not container_id:
                    continue
                persona = str(payload.get("persona") or "unspecified").lower()
                timestamp = _parse_iso_ts(str(payload.get("ts") or payload.get("created_at") or ""))
                weight = float(payload.get("weight") or 1.0)
                events.append(ContainerUsageEvent(container_id=container_id, persona=persona, timestamp=timestamp, weight=weight))
        return events

    def _load_life_os_metrics(self, user_id: str, user_dir: Path) -> LifeOsMetrics:
        """Load Life OS metrics (task completion, goal confidence, curiosity)."""
        metrics = LifeOsMetrics(user_id=user_id)
        life_dir = user_dir / "hc_life"
        if not life_dir.exists():
            return metrics

        # Goals (confidence averages)
        goals_path = life_dir / "goals.jsonl"
        if goals_path.exists():
            confidences: List[float] = []
            with goals_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    confidence = record.get("confidence")
                    if confidence is not None:
                        confidences.append(float(confidence))
            if confidences:
                metrics.goal_confidence_avg = sum(confidences) / len(confidences)
                metrics.goals_total = len(confidences)

        # Todos (task completion + curiosity metadata)
        todos_path = life_dir / "todos.jsonl"
        if todos_path.exists():
            with todos_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    status = record.get("status")
                    timestamp = _parse_iso_ts(str(record.get("updated_at") or record.get("created_at") or ""))
                    day = _to_date(timestamp)

                    if status == "done":
                        metrics.tasks_completed_by_day[day] = metrics.tasks_completed_by_day.get(day, 0) + 1

                    metadata = record.get("metadata") or {}
                    curiosity_delta = metadata.get("curiosity_delta")
                    if curiosity_delta is not None:
                        metrics.curiosity_delta_by_day[day] = metrics.curiosity_delta_by_day.get(day, 0.0) + float(curiosity_delta)

                    if metadata:
                        for key, value in metadata.items():
                            if isinstance(value, (int, float)):
                                metrics.curated_notes[key] = metrics.curated_notes.get(key, 0.0) + float(value)

        return metrics


__all__ = [
    "MetricsEngine",
    "MetricsSnapshot",
    "LifeOsMetrics",
    "ContainerUsageEvent",
]
