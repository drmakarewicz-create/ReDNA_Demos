from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Any, Dict, List, Mapping, Optional, Sequence

import math
import re
from collections import Counter

try:  # pragma: no cover - planner optional in some build contexts
    from ReDNACoreDemo.core import planner as _planner
except Exception:  # pragma: no cover - keep runtime resilient
    _planner = None


@dataclass
class TurnObservationResult:
    metrics: Dict[str, Any]
    observations: List[Dict[str, Any]]
    state: Dict[str, Any]


_CLARIFICATION_PATTERNS: Sequence[re.Pattern[str]] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(can|could|would)\s+you\s+clarify\b",
        r"\b(help|make)\s+me\s+understand\b",
        r"\bwhat\s+do\s+you\s+mean\b",
        r"\b(can|could|would)\s+you\s+(explain|expand|rephrase)\b",
        r"\bclarify\s+that\b",
        r"\bspell\s+that\s+out\b",
    )
)
_REPAIR_PHRASES: Sequence[str] = (
    "i meant",
    "i mean",
    "let me restate",
    "let me rephrase",
    "sorry",
    "my bad",
    "actually",
    "to clarify",
    "what i meant",
)
_HUMOR_MARKERS: Sequence[str] = (
    "lol",
    "lmao",
    "rofl",
    "haha",
    "hehe",
    "😂",
    "🤣",
    "😅",
    "😆",
)
_POLITENESS_MARKERS: Sequence[str] = (
    "please",
    "thank you",
    "thanks",
    "i'd appreciate",
    "would you mind",
    "could you please",
    "if you could",
    "appreciate it",
)
_SLANG_TOKENS: Sequence[str] = (
    "lol",
    "lmao",
    "gonna",
    "wanna",
    "kinda",
    "sorta",
    "ya",
    "y'all",
    "omg",
    "wtf",
)
_ASSERTIVE_TOKENS: Sequence[str] = (
    "must",
    "need",
    "require",
    "definitely",
    "absolutely",
    "should",
    "have",
    "insist",
    "demand",
    "now",
)
_ASSERTIVE_PHRASES: Sequence[str] = (
    "have to",
    "need to",
    "must",
    "it's essential",
    "it's critical",
    "do it now",
    "no choice",
    "make sure",
)
_ACK_MARKERS: Sequence[str] = (
    "thank you",
    "thanks",
    "got it",
    "gotcha",
    "okay",
    "ok",
    "cool",
    "sounds good",
    "understood",
    "makes sense",
)
_QUESTION_OPENERS: Sequence[str] = (
    "who",
    "what",
    "when",
    "where",
    "why",
    "how",
    "do",
    "did",
    "can",
    "could",
    "would",
    "will",
    "is",
    "are",
    "am",
    "should",
)
_POSITIVE_WORDS: Sequence[str] = (
    "great",
    "good",
    "awesome",
    "fantastic",
    "love",
    "like",
    "enjoy",
    "happy",
    "wonderful",
    "glad",
)
_NEGATIVE_WORDS: Sequence[str] = (
    "bad",
    "terrible",
    "awful",
    "hate",
    "dislike",
    "upset",
    "sad",
    "angry",
    "annoyed",
    "frustrated",
)


def last_assistant_timestamp(history: Sequence[Dict[str, Any]]) -> Optional[str]:
    for message in reversed(history):
        if message.get("role") != "assistant":
            continue
        meta = message.get("meta") or {}
        ts = meta.get("ts")
        if isinstance(ts, str):
            return ts
    return None


def capture_turn_observation(
    *,
    user_id: Optional[str],
    user_text: str,
    user_ts: str,
    last_assistant_ts: Optional[str],
    state: Optional[Dict[str, Any]] = None,
    source: str = "head_coach_observation",
) -> TurnObservationResult:
    current_state = dict(state or {})
    metrics = _compute_turn_metrics(user_text=user_text, user_ts=user_ts, last_assistant_ts=last_assistant_ts)

    current_state["last_user_ts"] = user_ts
    current_state["last_user_text"] = user_text
    current_state["turns_observed"] = int(current_state.get("turns_observed", 0)) + 1

    latency_history: List[int] = list(current_state.get("latency_history_ms", []))
    latency_ms = metrics.get("response_latency_ms")
    if isinstance(latency_ms, (int, float)):
        latency_history.append(int(latency_ms))
        if len(latency_history) > 50:
            latency_history = latency_history[-50:]
        current_state["latency_history_ms"] = latency_history
        if latency_history:
            metrics["rolling_latency_avg_ms"] = float(mean(latency_history))
            metrics["rolling_latency_median_ms"] = float(median(latency_history))
            histogram = Counter(_latency_bucket(value) or "unknown" for value in latency_history)
            metrics["latency_histogram"] = dict(histogram)
    else:
        latency_history = list(current_state.get("latency_history_ms", []))

    cadence_bucket = metrics.get("response_latency_bucket")
    if latency_history:
        cadence_bucket = _latency_bucket(int(median(latency_history)))
    if cadence_bucket:
        metrics["cadence_bucket"] = cadence_bucket

    dialog_history: List[str] = list(current_state.get("dialog_history", []))
    dialog_act = metrics.get("dialog_act")
    if dialog_act:
        dialog_history.append(dialog_act)
        if len(dialog_history) > 50:
            dialog_history = dialog_history[-50:]
        current_state["dialog_history"] = dialog_history
        metrics["dialog_act_counts"] = dict(Counter(dialog_history))

    observations: List[Dict[str, Any]] = []
    if user_id:
        observations = _metrics_to_observations(
            user_id=user_id,
            user_ts=user_ts,
            metrics=metrics,
            source=source,
        )

    return TurnObservationResult(metrics=metrics, observations=observations, state=current_state)


def load_ask_queue(user_id: Optional[str], limit: int = 5) -> List[Dict[str, Any]]:
    """Return the current ask queue for display in Explorer surfaces."""

    if not user_id or _planner is None:
        return []
    try:
        return _planner.load_active_asks(user_id, limit=limit)
    except Exception:
        return []


def _compute_turn_metrics(
    *,
    user_text: str,
    user_ts: str,
    last_assistant_ts: Optional[str],
) -> Dict[str, Any]:
    tokens = _tokenize(user_text)
    lowered = user_text.lower()
    word_count = len(tokens)

    latency_ms = _latency_ms(last_assistant_ts, user_ts)
    latency_bucket = _latency_bucket(latency_ms)

    dialog_act = _dialog_act(tokens, lowered)

    clarification_matches = sum(1 for pattern in _CLARIFICATION_PATTERNS if pattern.search(user_text))
    clarification_score = min(1.0, clarification_matches * 0.4)

    repair_hits = sorted({phrase for phrase in _REPAIR_PHRASES if phrase in lowered})

    humor_hits = sorted({marker for marker in _HUMOR_MARKERS if marker in lowered})

    politeness_hits = sorted({marker for marker in _POLITENESS_MARKERS if marker in lowered})

    sentiment_score = _sentiment(tokens)
    formality_score = _formality(tokens, lowered)

    assertive_hits = _assertiveness(tokens, lowered)

    metrics: Dict[str, Any] = {
        "response_latency_ms": latency_ms,
        "response_latency_bucket": latency_bucket,
        "turn_length_words": word_count,
        "clarification_matches": clarification_matches,
        "clarification_score": clarification_score,
        "repair_phrases": repair_hits,
        "humor_markers": humor_hits,
        "politeness_markers": politeness_hits,
        "sentiment_score": sentiment_score,
        "formality_score": formality_score,
        "assertiveness_score": assertive_hits,
        "dialog_act": dialog_act,
    }

    return metrics


def _metrics_to_observations(
    *,
    user_id: str,
    user_ts: str,
    metrics: Mapping[str, Any],
    source: str,
) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    base = {
        "user_id": user_id,
        "ts": user_ts,
        "source": source,
        "ucn": 20.0,
        "confidence": "low",
        "provenance": "observed_chat_turn",
        "decay": True,
    }

    latency_bucket = metrics.get("response_latency_bucket")
    if latency_bucket:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.response_latency",
                "trait": "conversation.response_latency",
                "value": latency_bucket,
            }
        )

    if metrics.get("turn_length_words") is not None:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.turn_length",
                "trait": "conversation.turn_length",
                "value": int(metrics["turn_length_words"]),
            }
        )

    dialog_act = metrics.get("dialog_act")
    if dialog_act:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.dialog_act",
                "trait": "conversation.dialog_act",
                "value": dialog_act,
            }
        )

    cadence_bucket = metrics.get("cadence_bucket")
    if cadence_bucket:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.cadence",
                "trait": "conversation.cadence",
                "value": cadence_bucket,
            }
        )

    histogram = metrics.get("latency_histogram")
    if histogram:
        summary = ", ".join(f"{bucket}:{count}" for bucket, count in sorted(histogram.items()))
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.cadence_histogram",
                "trait": "conversation.cadence_histogram",
                "value": summary,
            }
        )

    median_latency = metrics.get("rolling_latency_median_ms")
    if median_latency is not None:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.response_latency_median",
                "trait": "conversation.response_latency_median",
                "value": float(median_latency),
            }
        )

    avg_latency = metrics.get("rolling_latency_avg_ms")
    if avg_latency is not None:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.response_latency_mean",
                "trait": "conversation.response_latency_mean",
                "value": float(avg_latency),
            }
        )

    dialog_counts = metrics.get("dialog_act_counts")
    if dialog_counts:
        summary = ", ".join(f"{label}:{count}" for label, count in sorted(dialog_counts.items()))
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.dialog_distribution",
                "trait": "conversation.dialog_distribution",
                "value": summary,
            }
        )

    clarification_score = metrics.get("clarification_score")
    if clarification_score and clarification_score > 0.0:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.clarification_need",
                "trait": "conversation.clarification_need",
                "value": float(_clamp(clarification_score)),
            }
        )

    repair_phrases = metrics.get("repair_phrases") or []
    if repair_phrases:
        observations.append(
            {
                **base,
                "container": "conversational_dynamics",
                "trait_id": "conversation.repair_patterns",
                "trait": "conversation.repair_patterns",
                "value": ", ".join(repair_phrases),
            }
        )

    sentiment_score = metrics.get("sentiment_score")
    if sentiment_score is not None:
        observations.append(
            {
                **base,
                "container": "communication_tone",
                "trait_id": "tone.sentiment_polarity",
                "trait": "tone.sentiment_polarity",
                "value": float(_clamp(sentiment_score)),
            }
        )

    formality_score = metrics.get("formality_score")
    if formality_score is not None:
        observations.append(
            {
                **base,
                "container": "communication_tone",
                "trait_id": "tone.formality_gradient",
                "trait": "tone.formality_gradient",
                "value": float(_clamp(formality_score)),
            }
        )

    humor_markers = metrics.get("humor_markers") or []
    if humor_markers:
        observations.append(
            {
                **base,
                "container": "communication_tone",
                "trait_id": "tone.humor_style",
                "trait": "tone.humor_style",
                "value": ", ".join(humor_markers),
            }
        )

    assertiveness_score = metrics.get("assertiveness_score")
    if assertiveness_score and assertiveness_score > 0.0:
        observations.append(
            {
                **base,
                "container": "communication_tone",
                "trait_id": "tone.aggression_assertiveness",
                "trait": "tone.aggression_assertiveness",
                "value": float(_clamp(assertiveness_score)),
            }
        )

    politeness_markers = metrics.get("politeness_markers") or []
    if politeness_markers:
        observations.append(
            {
                **base,
                "container": "communication_tone",
                "trait_id": "tone.politeness_strategies",
                "trait": "tone.politeness_strategies",
                "value": ", ".join(politeness_markers),
            }
        )

    return observations


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    cleaned = ts
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _latency_ms(previous_ts: Optional[str], current_ts: str) -> Optional[int]:
    prior = _parse_iso(previous_ts)
    current = _parse_iso(current_ts)
    if not prior or not current:
        return None
    delta = current - prior
    return int(delta.total_seconds() * 1000)


def _latency_bucket(latency_ms: Optional[int]) -> Optional[str]:
    if latency_ms is None:
        return None
    if latency_ms < 4000:
        return "fast"
    if latency_ms < 15000:
        return "steady"
    return "slow"


def _sentiment(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.5
    positives = sum(1 for token in tokens if token in _POSITIVE_WORDS)
    negatives = sum(1 for token in tokens if token in _NEGATIVE_WORDS)
    total = positives + negatives
    if total == 0:
        return 0.5
    score = (positives - negatives) / total
    return _clamp(0.5 + (score / 2.0))


def _formality(tokens: Sequence[str], lowered: str) -> float:
    if not tokens:
        return 0.5
    long_words = sum(1 for token in tokens if len(token) >= 6)
    contractions = sum(1 for token in tokens if "'" in token)
    slang = sum(1 for token in tokens if token in _SLANG_TOKENS)

    long_ratio = long_words / max(len(tokens), 1)
    contraction_ratio = contractions / max(len(tokens), 1)
    slang_ratio = slang / max(len(tokens), 1)

    score = 0.5
    score += 0.3 * (long_ratio - 0.2)
    score -= 0.4 * contraction_ratio
    score -= 0.2 * slang_ratio
    if re.search(r"\b(dear|sir|madam)\b", lowered):
        score += 0.1
    return _clamp(score)


def _assertiveness(tokens: Sequence[str], lowered: str) -> float:
    if not tokens:
        return 0.0
    hits = 0
    for phrase in _ASSERTIVE_PHRASES:
        if phrase in lowered:
            hits += 1
    hits += sum(1 for token in tokens if token in _ASSERTIVE_TOKENS)
    density = hits / max(len(tokens), 1)
    return _clamp(density * 5.0)


def _dialog_act(tokens: Sequence[str], lowered: str) -> str:
    if not lowered:
        return "silence"
    if any(marker in lowered for marker in _REPAIR_PHRASES):
        return "repair"
    if "?" in lowered or any(lowered.startswith(f"{word} ") for word in _QUESTION_OPENERS):
        return "question"
    if any(marker in lowered for marker in _ACK_MARKERS):
        return "ack"
    if len(tokens) <= 2 and any(token in {"ok", "okay", "sure", "yep", "yeah"} for token in tokens):
        return "ack"
    return "answer"


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if math.isnan(value) or math.isinf(value):
        return minimum
    return max(minimum, min(maximum, value))


__all__ = [
    "TurnObservationResult",
    "capture_turn_observation",
    "last_assistant_timestamp",
]
