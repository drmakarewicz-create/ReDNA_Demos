"""
Curiosity Engine v3 scaffolding.

Builds on v2 agenda generation but adds:
- Curiosity debt tracking per container.
- Dynamic reprioritisation via contextual triggers.
- Daily Head Coach prompt generation summarising highest-debt areas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
DEFAULT_MIN_PRIORITY = 0.25
DEFAULT_DEBT_SCORE = 0.2
DEBT_BOOST_FACTOR = 0.25  # how aggressively debt influences priority
GLOBAL_DEBT_DECAY = 0.04  # added to all items before per-target adjustments
SELECTED_DEBT_REDUCTION = 0.18


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _namespace_from_target(target: str) -> str:
    if not target:
        return "unknown"
    return target.split(".", 1)[0]


class ReprioritizationTrigger(str, Enum):
    USER_CONTEXT_CHANGE = "user_context_change"
    CONVERSATION_SHIFT = "conversation_shift"
    TIME_OF_DAY = "time_of_day"
    USER_MENTION = "user_mention"
    ENGAGEMENT_CHANGE = "engagement_change"
    LIFE_EVENT = "life_event"
    PREREQUISITE_FILLED = "prerequisite_filled"
    SCHEDULED_REVIEW = "scheduled_review"


@dataclass
class ReprioritizationEvent:
    trigger: ReprioritizationTrigger
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    priority: str = "normal"


@dataclass
class CuriosityDebtRecord:
    container_id: str
    score: float = DEFAULT_DEBT_SCORE
    last_seen: Optional[str] = None


class CuriosityDebtTracker:
    """Persist and update curiosity debt scores per user/container."""

    def __init__(self, debt_dir: Path):
        self.debt_dir = debt_dir
        self.debt_dir.mkdir(parents=True, exist_ok=True)

    def load(self, user_id: str) -> Dict[str, CuriosityDebtRecord]:
        path = self.debt_dir / f"{user_id}.json"
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to read curiosity debt for %s: %s", user_id, exc)
            return {}

        records: Dict[str, CuriosityDebtRecord] = {}
        for target, entry in payload.get("items", {}).items():
            record = CuriosityDebtRecord(
                container_id=target,
                score=_clamp(float(entry.get("score", DEFAULT_DEBT_SCORE))),
                last_seen=entry.get("last_seen"),
            )
            records[target] = record
        return records

    def save(self, user_id: str, records: Dict[str, CuriosityDebtRecord]) -> None:
        path = self.debt_dir / f"{user_id}.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": {
                target: {
                    "score": round(record.score, 4),
                    "last_seen": record.last_seen,
                }
                for target, record in records.items()
                if record.score > 0.001
            },
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def touch(self, records: Dict[str, CuriosityDebtRecord], target: str, *, reduce: bool = False) -> None:
        record = records.setdefault(target, CuriosityDebtRecord(container_id=target))
        if reduce:
            record.score = _clamp(record.score - SELECTED_DEBT_REDUCTION)
        else:
            record.score = _clamp(record.score + GLOBAL_DEBT_DECAY)
        record.last_seen = datetime.now(timezone.utc).isoformat()


class DynamicReprioritizer:
    """Compute boost adjustments based on contextual triggers."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def compute_adjustments(
        self,
        items: Sequence[Dict[str, Any]],
        events: Sequence[ReprioritizationEvent],
    ) -> Dict[str, float]:
        if not events:
            return {}

        adjustments: Dict[str, float] = {}
        for event in events:
            handler = getattr(self, f"_handle_{event.trigger.value}", None)
            if handler is None:
                continue
            event_adjustments = handler(items, event)
            for target, value in event_adjustments.items():
                adjustments[target] = _clamp(adjustments.get(target, 0.0) + value, -0.5, 0.6)
        return adjustments

    # Individual trigger handlers -------------------------------------------------
    def _handle_user_context_change(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        boost_namespaces = set(event.context.get("priority_namespaces", []))
        reduce_namespaces = set(event.context.get("deprioritize", []) or event.context.get("deprioritise", []) or [])
        adjustments: Dict[str, float] = {}
        for item in items:
            namespace = _namespace_from_target(str(item.get("target", "")))
            if namespace in boost_namespaces:
                adjustments[str(item["target"])] = 0.25
            elif namespace in reduce_namespaces:
                adjustments[str(item["target"])] = -0.15
        return adjustments

    def _handle_conversation_shift(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        topic = str(event.context.get("topic", "")).lower()
        if not topic:
            return {}
        adjustments: Dict[str, float] = {}
        for item in items:
            target = str(item.get("target", "")).lower()
            if topic in target:
                adjustments[str(item["target"])] = 0.2
        return adjustments

    def _handle_user_mention(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        topic = str(event.context.get("topic", "")).lower()
        adjustments: Dict[str, float] = {}
        if not topic:
            return adjustments
        for item in items:
            target = str(item.get("target", "")).lower()
            if topic in target:
                adjustments[str(item["target"])] = 0.35
        return adjustments

    def _handle_engagement_change(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        level = str(event.context.get("engagement_level", "")).lower()
        if level == "high":
            return {str(item["target"]): 0.1 for item in items[:3]}
        if level in {"low", "distracted"}:
            return {str(item["target"]): -0.2 for item in items}
        return {}

    def _handle_life_event(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        event_type = str(event.context.get("event_type", "")).lower()
        namespace_map = {
            "new_job": {"CareerDNA", "GoalDNA", "StressDNA"},
            "relationship_change": {"RelationshipDNA", "EmotionalDNA", "CommStyleDNA"},
            "health_issue": {"HealthDNA", "StressDNA", "SupportDNA"},
            "relocation": {"EnvironmentDNA", "SocialDNA", "AdaptabilityDNA"},
            "financial_change": {"FinancialDNA", "GoalDNA", "SecurityDNA"},
        }
        boosts = namespace_map.get(event_type, set())
        return {
            str(item["target"]): 0.4
            for item in items
            if _namespace_from_target(str(item.get("target", ""))) in boosts
        }

    def _handle_prerequisite_filled(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        dependent_targets = set(event.context.get("dependent_containers", []))
        return {
            str(item["target"]): 0.3
            for item in items
            if str(item.get("target")) in dependent_targets
        }

    def _handle_time_of_day(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        hour = event.timestamp.astimezone(timezone.utc).hour
        if 5 <= hour < 12:
            return {str(item["target"]): 0.05 for item in items[:5]}
        if 22 <= hour or hour < 5:
            return {str(item["target"]): -0.1 for item in items}
        return {}

    def _handle_scheduled_review(
        self,
        items: Sequence[Dict[str, Any]],
        event: ReprioritizationEvent,
    ) -> Dict[str, float]:
        return {str(item["target"]): 0.1 for item in items}


class CuriosityEngineV3:
    def __init__(self, *, data_root: Optional[Path] = None):
        root = Path(data_root or Path("data"))
        self.data_root = root
        self.agenda_dir = root / "curiosity" / "agendas"
        self.agenda_dir.mkdir(parents=True, exist_ok=True)
        self.debt_tracker = CuriosityDebtTracker(root / "curiosity" / "debt")

    # ------------------------------------------------------------------ agenda API
    def generate_agenda(
        self,
        user_id: str,
        *,
        limit: int = DEFAULT_LIMIT,
        min_priority: float = DEFAULT_MIN_PRIORITY,
        triggers: Optional[Iterable[ReprioritizationEvent]] = None,
        base_agenda: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return adjusted curiosity agenda for user."""
        base_agenda = base_agenda or self._load_base_agenda(user_id, limit=limit, min_priority=min_priority)
        items = list(base_agenda.get("items", []))
        if not items:
            return base_agenda

        debt_records = self.debt_tracker.load(user_id)
        now = datetime.now(timezone.utc)

        # apply global drift before per-item adjustments
        for record in debt_records.values():
            record.score = _clamp(record.score + GLOBAL_DEBT_DECAY * 0.5)

        reprioritizer = DynamicReprioritizer(user_id)
        adjustments = reprioritizer.compute_adjustments(items, list(triggers or []))

        enriched_items: List[Dict[str, Any]] = []
        for raw in items:
            target = str(raw.get("target"))
            record = debt_records.setdefault(target, CuriosityDebtRecord(container_id=target))

            base_priority = float(raw.get("priority", 0.0))
            boost = adjustments.get(target, 0.0)
            adjusted = _clamp(base_priority + record.score * DEBT_BOOST_FACTOR + boost)

            record.last_seen = record.last_seen or now.isoformat()

            enriched = dict(raw)
            enriched["base_priority"] = base_priority
            enriched["priority"] = round(adjusted, 3)
            enriched["debt_score"] = round(record.score, 3)
            if boost:
                annotations = list(enriched.get("annotations", []))
                annotations.append(
                    {"type": "trigger_boost", "value": round(boost, 3)}
                )
                enriched["annotations"] = annotations

            enriched_items.append(enriched)

        # Re-sort by adjusted priority and limit items
        enriched_items.sort(key=lambda item: item.get("priority", 0.0), reverse=True)
        top_items = enriched_items[:limit]

        # Update debt: reduce for selected, increase for others
        top_targets = {str(item.get("target")) for item in top_items}
        for target, record in debt_records.items():
            if target in top_targets:
                record.score = _clamp(record.score - SELECTED_DEBT_REDUCTION)
                record.last_seen = now.isoformat()

        self.debt_tracker.save(user_id, debt_records)
        self._save_agenda(user_id, {"items": top_items, "generated_at": now.isoformat()})

        return {
            "user_id": user_id,
            "generated_at": now.isoformat(),
            "items": top_items,
            "metadata": {
                "min_priority": min_priority,
                "trigger_count": len(list(triggers or [])),
            },
        }

    def generate_daily_prompt(
        self,
        user_id: str,
        *,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """Summarise top curiosity debt items for HC daily brief."""
        debt_records = self.debt_tracker.load(user_id)
        if not debt_records:
            return {
                "user_id": user_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "prompt": None,
                "items": [],
            }

        sorted_records = sorted(
            debt_records.values(),
            key=lambda record: record.score,
            reverse=True,
        )[:limit]

        lines = []
        items = []
        for record in sorted_records:
            namespace = _namespace_from_target(record.container_id)
            lines.append(f"- {namespace}: {record.container_id} (debt {record.score:.2f})")
            items.append(
                {
                    "target": record.container_id,
                    "namespace": namespace,
                    "debt_score": round(record.score, 3),
                    "last_seen": record.last_seen,
                }
            )

        prompt = "Daily curiosity focus:\n" + "\n".join(lines)
        return {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "items": items,
        }

    # ------------------------------------------------------------------ helpers
    def _load_base_agenda(
        self,
        user_id: str,
        *,
        limit: int,
        min_priority: float,
    ) -> Dict[str, Any]:
        try:
            from .curiosity_engine_v2 import CuriosityEngine as CuriosityEngineV2

            engine_v2 = CuriosityEngineV2(data_root=self.data_root)
            return engine_v2.generate_agenda(
                user_id=user_id,
                limit=limit,
                min_priority=min_priority,
                fallback=True,
            )
        except Exception as exc:  # pragma: no cover - fallback
            logger.warning("Curiosity Engine v2 fallback engaged for %s: %s", user_id, exc)
            return {"user_id": user_id, "items": [], "generated_at": datetime.now(timezone.utc).isoformat()}

    def _save_agenda(self, user_id: str, agenda: Dict[str, Any]) -> None:
        """Persist most recent agenda for debugging purposes."""
        try:
            path = self.agenda_dir / f"{user_id}.json"
            path.write_text(json.dumps(agenda, indent=2, sort_keys=True))
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to persist curiosity agenda for %s: %s", user_id, exc)


def generate_agenda(
    user_id: str,
    *,
    limit: int = DEFAULT_LIMIT,
    min_priority: float = DEFAULT_MIN_PRIORITY,
    triggers: Optional[Iterable[ReprioritizationEvent]] = None,
) -> Dict[str, Any]:
    engine = CuriosityEngineV3()
    return engine.generate_agenda(
        user_id=user_id,
        limit=limit,
        min_priority=min_priority,
        triggers=triggers,
    )


__all__ = [
    "CuriosityEngineV3",
    "CuriosityDebtRecord",
    "CuriosityDebtTracker",
    "ReprioritizationEvent",
    "ReprioritizationTrigger",
    "generate_agenda",
]
