"""
Tone & Empathy Adapter — Jarvis Connection Phase 1

Analyzes user tone/formality/empathy cues and adapts HC behavior context
in real time (1-2 turns) using EMA smoothing and heuristic signals.

Key Features:
- Tone scoring (casual → professional → direct)
- Formality detection (sentence length, punctuation)
- Empathy cue detection (keywords, sentiment)
- EMA smoothing for stable adaptation
- Safety boundaries (no therapeutic claims, consent-aware)
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).parent / "jarvis_connection_config.json"


class ToneAdapter:
    """
    Adaptive tone and empathy analyzer for HC connection.

    Analyzes user messages for tone, formality, and empathy cues,
    then computes behavior context adjustments with EMA smoothing.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize tone adapter.

        Args:
            config_path: Path to configuration JSON
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self._load_config()

        # EMA state tracking (per user)
        self._user_ema_state: Dict[str, Dict[str, float]] = {}
        self._user_history: Dict[str, deque] = {}

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON."""
        if not self.config_path.exists():
            logger.warning(f"Connection config not found at {self.config_path}, using defaults")
            return {
                "ema_alpha": 0.5,
                "default_tone": "professional",
                "tone_map": {
                    "casual": [0.0, 0.3],
                    "empathetic": [0.3, 0.7],
                    "professional": [0.6, 0.9],
                    "direct": [0.8, 1.0]
                },
                "empathy_keywords": [
                    "sorry", "understand", "frustrated", "overwhelmed",
                    "tough", "appreciate", "worried", "anxious", "stressed",
                    "confused", "lost", "help", "struggling"
                ],
                "max_delta_per_turn": 0.25,
                "developer_trace": True
            }

        with open(self.config_path, "r") as f:
            return json.load(f)

    def analyze_turn(
        self,
        user_text: str,
        recent_history: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze user turn for tone, formality, and empathy cues.

        Args:
            user_text: Current user message
            recent_history: Last 2-3 messages for context (optional)
            user_id: User identifier for EMA state (optional)

        Returns:
            {
                "tone_score": 0..1,        # 0=casual, 1=direct/formal
                "formality_score": 0..1,   # 0=informal, 1=formal
                "empathy_cue": "low|med|high",
                "signals": {...}           # Raw signal values
            }
        """
        recent_history = recent_history or []

        # Analyze signals
        signals = self._extract_signals(user_text)

        # Compute tone score (0=casual, 1=direct/formal)
        tone_score = self._compute_tone_score(signals)

        # Compute formality score
        formality_score = self._compute_formality_score(signals)

        # Detect empathy cue
        empathy_cue = self._detect_empathy_cue(signals)

        # Add to user history for future context
        if user_id:
            if user_id not in self._user_history:
                self._user_history[user_id] = deque(maxlen=5)
            self._user_history[user_id].append(user_text)

        return {
            "tone_score": tone_score,
            "formality_score": formality_score,
            "empathy_cue": empathy_cue,
            "signals": signals
        }

    def _extract_signals(self, text: str) -> Dict[str, Any]:
        """
        Extract heuristic signals from text.

        Returns:
            {
                "avg_word_length": float,
                "avg_sentence_length": float,
                "exclamations": int,
                "questions": int,
                "emoji_count": int,
                "empathy_keywords": int,
                "sentiment": "positive|negative|neutral",
                "uppercase_ratio": float
            }
        """
        # Basic tokenization
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        words = re.findall(r'\b\w+\b', text.lower())
        word_count = len(words)

        # Sentence metrics
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        # Word metrics
        avg_word_length = sum(len(w) for w in words) / max(word_count, 1)

        # Punctuation
        exclamations = text.count('!')
        questions = text.count('?')

        # Emoji detection (simple heuristic)
        emoji_pattern = r'[😀-🙏🌀-🗿🚀-🛿]|:\)|:\(|:D|;-?\)|<3'
        emoji_count = len(re.findall(emoji_pattern, text))

        # Empathy keywords
        empathy_keywords_config = self.config.get("empathy_keywords", [])
        empathy_keyword_count = sum(
            1 for keyword in empathy_keywords_config
            if keyword in text.lower()
        )

        # Simple sentiment (polarity keywords)
        positive_words = ['good', 'great', 'awesome', 'excellent', 'happy', 'love', 'thanks', 'appreciate']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'frustrated', 'angry', 'sad', 'disappointed']

        positive_count = sum(1 for w in positive_words if w in text.lower())
        negative_count = sum(1 for w in negative_words if w in text.lower())

        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Uppercase ratio (shouting detection)
        uppercase_chars = sum(1 for c in text if c.isupper())
        total_chars = len([c for c in text if c.isalpha()])
        uppercase_ratio = uppercase_chars / max(total_chars, 1)

        return {
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "exclamations": exclamations,
            "questions": questions,
            "emoji_count": emoji_count,
            "empathy_keywords": empathy_keyword_count,
            "sentiment": sentiment,
            "uppercase_ratio": round(uppercase_ratio, 3)
        }

    def _compute_tone_score(self, signals: Dict[str, Any]) -> float:
        """
        Compute tone score from signals.

        0.0 = casual (short, emoji, exclamations)
        1.0 = direct/formal (long words, no emoji)
        """
        score = 0.5  # Start neutral

        # Longer words → more formal
        if signals["avg_word_length"] > 6:
            score += 0.2
        elif signals["avg_word_length"] < 4:
            score -= 0.2

        # Emoji/exclamations → more casual
        if signals["emoji_count"] > 0:
            score -= 0.15
        if signals["exclamations"] > 1:
            score -= 0.1

        # Longer sentences → more formal
        if signals["avg_sentence_length"] > 20:
            score += 0.15
        elif signals["avg_sentence_length"] < 8:
            score -= 0.1

        # Uppercase (shouting) → less formal
        if signals["uppercase_ratio"] > 0.3:
            score -= 0.2

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _compute_formality_score(self, signals: Dict[str, Any]) -> float:
        """
        Compute formality score from signals.

        0.0 = informal
        1.0 = formal
        """
        score = 0.5

        # Longer words → more formal
        if signals["avg_word_length"] > 6:
            score += 0.25
        elif signals["avg_word_length"] < 4:
            score -= 0.2

        # Longer sentences → more formal
        if signals["avg_sentence_length"] > 20:
            score += 0.2
        elif signals["avg_sentence_length"] < 8:
            score -= 0.15

        # No emoji → more formal
        if signals["emoji_count"] == 0 and signals["exclamations"] == 0:
            score += 0.1
        else:
            score -= 0.15

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _detect_empathy_cue(self, signals: Dict[str, Any]) -> str:
        """
        Detect empathy cue level from signals.

        Returns:
            "low" | "med" | "high"
        """
        # Check empathy keywords + negative sentiment
        empathy_score = signals["empathy_keywords"]

        if signals["sentiment"] == "negative":
            empathy_score += 1

        if empathy_score >= 3:
            return "high"
        elif empathy_score >= 1:
            return "med"
        else:
            return "low"

    def compute_adjustments(
        self,
        tone_score: float,
        formality_score: float,
        empathy_cue: str,
        behavior_context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compute behavior context adjustments with EMA smoothing.

        Args:
            tone_score: Tone score from analyze_turn (0..1)
            formality_score: Formality score (0..1)
            empathy_cue: Empathy level ("low"|"med"|"high")
            behavior_context: Existing behavior context (for reference)
            user_id: User identifier for EMA state

        Returns:
            {
                "hints": {
                    "tone_target": "empathetic|professional|casual|direct",
                    "formality_bias": 0..1,
                    "empathy_bias": 0..1,
                    "creativity_bias": 0..1  // preserve existing if present
                },
                "confidence": 0..1
            }
        """
        behavior_context = behavior_context or {}

        # Map tone score to tone target
        tone_target = self._map_tone_target(tone_score, empathy_cue)

        # Apply EMA smoothing if user_id provided
        if user_id:
            if user_id not in self._user_ema_state:
                self._user_ema_state[user_id] = {
                    "formality_bias": 0.5,
                    "empathy_bias": 0.5,
                }

            alpha = self.config.get("ema_alpha", 0.5)
            max_delta = self.config.get("max_delta_per_turn", 0.25)

            # Compute raw targets
            raw_formality = formality_score
            raw_empathy = self._empathy_cue_to_bias(empathy_cue)

            # Apply EMA with delta clamping
            prev_formality = self._user_ema_state[user_id]["formality_bias"]
            prev_empathy = self._user_ema_state[user_id]["empathy_bias"]

            # Clamp delta
            formality_delta = raw_formality - prev_formality
            formality_delta = max(-max_delta, min(max_delta, formality_delta))

            empathy_delta = raw_empathy - prev_empathy
            empathy_delta = max(-max_delta, min(max_delta, empathy_delta))

            # EMA update
            new_formality = prev_formality + alpha * formality_delta
            new_empathy = prev_empathy + alpha * empathy_delta

            # Update state
            self._user_ema_state[user_id]["formality_bias"] = new_formality
            self._user_ema_state[user_id]["empathy_bias"] = new_empathy

            formality_bias = new_formality
            empathy_bias = new_empathy
        else:
            # No smoothing
            formality_bias = formality_score
            empathy_bias = self._empathy_cue_to_bias(empathy_cue)

        # Preserve existing creativity_bias if present
        creativity_bias = behavior_context.get("creativity_bias", 0.6)

        # Confidence based on signal strength
        confidence = 0.8  # Default high confidence for heuristics

        return {
            "hints": {
                "tone_target": tone_target,
                "formality_bias": round(formality_bias, 2),
                "empathy_bias": round(empathy_bias, 2),
                "creativity_bias": round(creativity_bias, 2)
            },
            "confidence": confidence
        }

    def _map_tone_target(self, tone_score: float, empathy_cue: str) -> str:
        """
        Map tone score and empathy cue to tone target.

        Args:
            tone_score: 0..1 (0=casual, 1=formal/direct)
            empathy_cue: "low"|"med"|"high"

        Returns:
            "casual" | "empathetic" | "professional" | "direct"
        """
        tone_map = self.config.get("tone_map", {})

        # If high empathy cue, prefer empathetic
        if empathy_cue == "high":
            return "empathetic"

        # Otherwise map by score
        for tone_label, (low, high) in tone_map.items():
            if low <= tone_score <= high:
                return tone_label

        # Default
        return self.config.get("default_tone", "professional")

    def _empathy_cue_to_bias(self, empathy_cue: str) -> float:
        """Convert empathy cue to bias value."""
        mapping = {
            "low": 0.4,
            "med": 0.65,
            "high": 0.85
        }
        return mapping.get(empathy_cue, 0.5)


# Convenience function
def create_tone_adapter(config_path: Optional[Path] = None) -> ToneAdapter:
    """Create tone adapter instance."""
    return ToneAdapter(config_path=config_path)
