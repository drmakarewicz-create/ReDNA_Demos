"""
Head Coach empathy monitoring and bonding scaffolding (Evergreen 2).

Tracks emotional signals across turns, surfaces recommended responses, and
persists lightweight telemetry to support human bonding metrics.
"""

from __future__ import annotations

import json
import re
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence


POSITIVE_WORDS = {
    "glad",
    "happy",
    "excited",
    "grateful",
    "relieved",
    "hopeful",
    "proud",
}
NEGATIVE_WORDS = {
    "sad",
    "upset",
    "tired",
    "anxious",
    "angry",
    "frustrated",
    "worried",
    "stressed",
    "overwhelmed",
    "lonely",
}
FEAR_WORDS = {"afraid", "scared", "nervous", "terrified", "worried"}
JOY_WORDS = {"joy", "glad", "delighted", "celebrate", "amazing"}
SUPPORTIVE_WORDS = {"thank", "appreciate", "grateful", "helped", "support"}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class EmotionalState(str, Enum):
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    TRUST = "trust"
    ANTICIPATION = "anticipation"
    NEUTRAL = "neutral"
    MIXED = "mixed"


@dataclass
class EmpathySignal:
    kind: str
    value: str
    intensity: float
    confidence: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EmpathySnapshot:
    emotional_state: EmotionalState
    intensity: float
    confidence: float
    primary_needs: List[str]
    recommended_actions: List[str]
    bonding_metrics: Dict[str, Any]
    signals: List[EmpathySignal] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotional_state": self.emotional_state.value,
            "intensity": round(self.intensity, 3),
            "confidence": round(self.confidence, 3),
            "primary_needs": self.primary_needs,
            "recommended_actions": self.recommended_actions,
            "bonding_metrics": self.bonding_metrics,
            "signals": [
                {
                    "kind": signal.kind,
                    "value": signal.value,
                    "intensity": round(signal.intensity, 3),
                    "confidence": round(signal.confidence, 3),
                    "timestamp": signal.timestamp.isoformat(),
                }
                for signal in self.signals
            ],
        }


class EmpathyMonitor:
    """Simple empathy state tracker with rolling bonding metrics."""

    def __init__(
        self,
        user_id: str,
        *,
        data_root: Optional[Path] = None,
        history_window: int = 25,
    ):
        self.user_id = user_id
        root = Path(data_root or Path(__file__).resolve().parents[2] / "data")
        self.telemetry_dir = root / "telemetry" / "empathy"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)

        self._history: Deque[EmpathySnapshot] = deque(maxlen=history_window)
        self._bonding_state = {
            "turns_observed": 0,
            "positive_turns": 0,
            "last_positive_turn": None,
            "trust_score": 0.5,
            "rapport_score": 0.5,
        }

    # ------------------------------------------------------------------ public API
    def observe_turn(
        self,
        *,
        message_text: str,
        recent_history: Sequence[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmpathySnapshot:
        metadata = metadata or {}
        signals = self._collect_signals(message_text, recent_history, metadata)
        emotional_state, intensity = self._infer_emotional_state(signals)
        confidence = self._estimate_confidence(signals)
        needs = self._map_needs(emotional_state, metadata)
        actions = self._recommend_actions(emotional_state, needs, metadata)

        bonding_metrics = self._update_bonding_metrics(emotional_state, intensity, metadata)

        snapshot = EmpathySnapshot(
            emotional_state=emotional_state,
            intensity=intensity,
            confidence=confidence,
            primary_needs=needs,
            recommended_actions=actions,
            bonding_metrics=bonding_metrics,
            signals=signals,
        )

        self._history.append(snapshot)
        self._write_telemetry(snapshot)
        return snapshot

    # ------------------------------------------------------------------ internals
    def _collect_signals(
        self,
        message_text: str,
        recent_history: Sequence[str],
        metadata: Dict[str, Any],
    ) -> List[EmpathySignal]:
        tokens = re.findall(r"\w+", message_text.lower())
        counter = Counter(tokens)
        signals: List[EmpathySignal] = []

        total_words = max(1, len(tokens))
        exclamations = message_text.count("!")
        questions = message_text.count("?")

        if exclamations:
            signals.append(
                EmpathySignal(
                    kind="punctuation",
                    value="exclamation",
                    intensity=min(1.0, exclamations * 0.25),
                    confidence=0.5,
                )
            )
        if questions:
            signals.append(
                EmpathySignal(
                    kind="punctuation",
                    value="question",
                    intensity=min(1.0, questions * 0.2),
                    confidence=0.4,
                )
            )

        pos_hits = sum(counter[word] for word in POSITIVE_WORDS if word in counter)
        neg_hits = sum(counter[word] for word in NEGATIVE_WORDS if word in counter)
        fear_hits = sum(counter[word] for word in FEAR_WORDS if word in counter)

        if pos_hits:
            signals.append(
                EmpathySignal(
                    kind="keyword",
                    value="positive",
                    intensity=min(1.0, pos_hits / total_words * 4),
                    confidence=0.7,
                )
            )
        if neg_hits:
            signals.append(
                EmpathySignal(
                    kind="keyword",
                    value="negative",
                    intensity=min(1.0, neg_hits / total_words * 4),
                    confidence=0.7,
                )
            )
        if fear_hits:
            signals.append(
                EmpathySignal(
                    kind="keyword",
                    value="fear",
                    intensity=min(1.0, fear_hits / total_words * 5),
                    confidence=0.75,
                )
            )

        if metadata.get("user_shared_vulnerability"):
            signals.append(
                EmpathySignal(
                    kind="context",
                    value="vulnerability",
                    intensity=0.85,
                    confidence=0.8,
                )
            )

        # History-based signal: abrupt short reply
        if len(tokens) <= 3 and recent_history:
            signals.append(
                EmpathySignal(
                    kind="brevity",
                    value="terse",
                    intensity=0.6,
                    confidence=0.5,
                )
            )

        if not signals:
            signals.append(
                EmpathySignal(
                    kind="baseline",
                    value="neutral",
                    intensity=0.2,
                    confidence=0.3,
                )
            )
        return signals

    def _infer_emotional_state(self, signals: Iterable[EmpathySignal]) -> (EmotionalState, float):
        score = Counter()
        intensity_sum = 0.0
        for signal in signals:
            weight = signal.intensity * signal.confidence
            intensity_sum += weight
            if signal.value == "positive":
                score[EmotionalState.JOY] += weight
                score[EmotionalState.TRUST] += weight * 0.4
            elif signal.value == "negative":
                score[EmotionalState.SADNESS] += weight * 0.7
                score[EmotionalState.ANGER] += weight * 0.3
            elif signal.value == "fear":
                score[EmotionalState.FEAR] += weight
            elif signal.value == "vulnerability":
                score[EmotionalState.TRUST] += weight * 0.8
                score[EmotionalState.SADNESS] += weight * 0.2
            elif signal.value == "terse":
                score[EmotionalState.ANTICIPATION] += weight * 0.5
                score[EmotionalState.SADNESS] += weight * 0.3
            elif signal.value == "exclamation":
                score[EmotionalState.SURPRISE] += weight

        if not score:
            return EmotionalState.NEUTRAL, _clamp(intensity_sum)

        top_state, top_value = score.most_common(1)[0]
        if len(score) > 1:
            second_value = score.most_common(2)[1][1]
            if top_value - second_value < 0.2:
                return EmotionalState.MIXED, _clamp(intensity_sum)
        return top_state, _clamp(intensity_sum)

    def _estimate_confidence(self, signals: Iterable[EmpathySignal]) -> float:
        signals_list = list(signals)
        total_confidence = sum(signal.confidence for signal in signals_list)
        return _clamp(total_confidence / max(1, len(signals_list)))

    def _map_needs(self, emotional_state: EmotionalState, metadata: Dict[str, Any]) -> List[str]:
        needs_map = {
            EmotionalState.SADNESS: ["comfort", "validation", "hope"],
            EmotionalState.ANGER: ["validation", "perspective", "problem_solving"],
            EmotionalState.FEAR: ["reassurance", "safety", "support"],
            EmotionalState.JOY: ["celebration", "connection", "amplification"],
            EmotionalState.TRUST: ["reinforcement", "shared_experience", "gratitude"],
            EmotionalState.ANTICIPATION: ["clarity", "alignment", "encouragement"],
        }
        needs = list(needs_map.get(emotional_state, ["engagement", "exploration"]))
        if metadata.get("user_asked_question"):
            needs.append("information")
        if metadata.get("user_shared_vulnerability"):
            needs.append("trust_deepening")
        return sorted(set(needs))

    def _recommend_actions(
        self,
        emotional_state: EmotionalState,
        needs: Sequence[str],
        metadata: Dict[str, Any],
    ) -> List[str]:
        recommendations: List[str] = []
        primary_need = needs[0] if needs else "connection"

        if primary_need == "comfort":
            recommendations.append("Reflect their feelings and acknowledge the difficulty.")
        if primary_need == "validation":
            recommendations.append("State explicitly that their reaction makes sense.")
        if primary_need == "support":
            recommendations.append("Offer concrete help or check-ins.")
        if primary_need == "celebration":
            recommendations.append("Celebrate with enthusiasm and suggest sharing the win.")
        if primary_need == "trust_deepening":
            recommendations.append("Thank them for the vulnerability and reinforce safety.")
        if metadata.get("user_asked_question"):
            recommendations.append("Answer their question clearly before nudging elsewhere.")

        if emotional_state in (EmotionalState.JOY, EmotionalState.TRUST):
            recommendations.append("Invite them to build on the positive momentum.")

        if not recommendations:
            recommendations.append("Ask a gentle follow-up to surface more context.")

        return recommendations

    def _update_bonding_metrics(
        self,
        emotional_state: EmotionalState,
        intensity: float,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        state = self._bonding_state
        state["turns_observed"] += 1

        positive_turn = emotional_state in {EmotionalState.JOY, EmotionalState.TRUST}
        if positive_turn:
            state["positive_turns"] += 1
            state["last_positive_turn"] = datetime.now(timezone.utc).isoformat()

        ratio = state["positive_turns"] / max(1, state["turns_observed"])
        state["trust_score"] = _clamp(0.4 + ratio * 0.6)

        if metadata.get("user_shared_vulnerability"):
            state["rapport_score"] = _clamp(state["rapport_score"] + 0.05)
        elif positive_turn:
            state["rapport_score"] = _clamp(state["rapport_score"] + intensity * 0.03)
        else:
            state["rapport_score"] = _clamp(state["rapport_score"] - 0.01)

        return dict(state)

    def _write_telemetry(self, snapshot: EmpathySnapshot) -> None:
        path = self.telemetry_dir / f"{self.user_id}.jsonl"
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": self.user_id,
            **snapshot.to_dict(),
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")


__all__ = [
    "EmpathyMonitor",
    "EmpathySnapshot",
    "EmpathySignal",
    "EmotionalState",
]
