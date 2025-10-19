"""
Head Coach Intent Analyzer
===========================

Classifies user messages into intent categories for routing decisions.

Intent Schema:
- category: question|request|feedback|task|reflection
- domain: career|personality|relationship|belief|photo|system
- urgency: low|medium|high|critical
- confidence: 0.0-1.0
- ambiguity: 0.0-1.0
- user_emotion: positive|neutral|negative|frustrated|curious
"""

import logging
import re
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class IntentAnalyzer:
    """
    Rule-based intent classifier for Head Coach routing.

    Future: Replace with ML classifier for higher accuracy.
    """

    def __init__(self):
        """Initialize intent analyzer."""
        self._load_patterns()

    def _load_patterns(self):
        """Load keyword patterns for intent classification."""
        # Category patterns
        self.category_patterns = {
            "question": [
                r"\b(what|who|when|where|why|how|tell me|explain|can you)\b",
                r"\?$"
            ],
            "request": [
                r"\b(help|need|want|would like|could you|please|can i get)\b",
                r"\b(show me|give me|provide|assist)\b"
            ],
            "feedback": [
                r"\b(thanks|thank you|great|good|bad|wrong|not helpful)\b",
                r"\b(appreciate|perfect|awesome|terrible)\b"
            ],
            "task": [
                r"\b(do this|complete|finish|work on|start)\b",
                r"\b(create|build|make|design)\b"
            ],
            "reflection": [
                r"\b(i think|i feel|i believe|i wonder|it seems|maybe)\b",
                r"\b(realized|learned|understanding|insight)\b"
            ]
        }

        # Domain patterns
        self.domain_patterns = {
            "career": [
                r"\b(job|career|work|profession|interview|resume|salary)\b",
                r"\b(promotion|skills|employer|hire|transition)\b",
                r"\b(professional|leadership|team|manager)\b"
            ],
            "personality": [
                r"\b(personality|trait|test|assessment|behavior|strengths)\b",
                r"\b(weaknesses|character|identity|who i am)\b",
                r"\b(big five|myers-briggs|enneagram)\b"
            ],
            "relationship": [
                r"\b(relationship|partner|dating|marriage|friend|family)\b",
                r"\b(communication|conflict|social|connection)\b",
                r"\b(romantic|friendship|interpersonal)\b"
            ],
            "belief": [
                r"\b(belief|value|moral|ethics|principle|conviction)\b",
                r"\b(faith|religion|philosophy|worldview)\b",
                r"\b(meaning|purpose|virtue)\b"
            ],
            "photo": [
                r"\b(photo|picture|image|appearance|selfie|portrait)\b",
                r"\b(look|visual|style|presentation)\b"
            ],
            "system": [
                r"\b(help|settings|account|profile|data|privacy)\b",
                r"\b(how does|how do i|what is)\b"
            ]
        }

        # Urgency indicators
        self.urgency_indicators = {
            "critical": [
                r"\b(urgent|emergency|asap|immediately|critical|now)\b",
                r"\b(help!|please!)\b"
            ],
            "high": [
                r"\b(soon|quickly|important|priority|deadline)\b",
                r"\b(need to|have to|must)\b"
            ],
            "medium": [
                r"\b(should|would like|when you can|sometime)\b"
            ],
            "low": [
                r"\b(maybe|perhaps|whenever|no rush|curious)\b"
            ]
        }

    def analyze(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze message and return intent classification.

        Args:
            message: User message text
            context: Optional awareness context for boosting confidence

        Returns:
            Intent dict with category, domain, urgency, confidence, ambiguity
        """
        message_lower = message.lower()

        # Classify category
        category, cat_confidence = self._classify_category(message_lower)

        # Classify domain
        domain, dom_confidence = self._classify_domain(message_lower, context)

        # Classify urgency
        urgency = self._classify_urgency(message_lower)

        # Calculate ambiguity (inverse of confidence)
        avg_confidence = (cat_confidence + dom_confidence) / 2
        ambiguity = 1.0 - avg_confidence

        # Detect user emotion (basic heuristic)
        user_emotion = self._detect_emotion(message_lower)

        return {
            "category": category,
            "domain": domain,
            "urgency": urgency,
            "confidence": round(avg_confidence, 2),
            "ambiguity": round(ambiguity, 2),
            "user_emotion": user_emotion,
            "raw_scores": {
                "category_confidence": round(cat_confidence, 2),
                "domain_confidence": round(dom_confidence, 2)
            }
        }

    def _classify_category(self, message: str) -> Tuple[str, float]:
        """Classify message category with confidence."""
        scores = {}

        for category, patterns in self.category_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    score += 1
            scores[category] = score

        # Get max score
        max_score = max(scores.values()) if scores else 0

        if max_score == 0:
            return ("question", 0.5)  # Default to question with low confidence

        # Get category with max score
        category = max(scores, key=scores.get)

        # Calculate confidence (normalize to 0.5-0.95 range)
        confidence = min(0.95, 0.5 + (max_score * 0.15))

        return (category, confidence)

    def _classify_domain(self, message: str, context: Dict[str, Any] = None) -> Tuple[str, float]:
        """Classify message domain with confidence."""
        scores = {}

        for domain, patterns in self.domain_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    score += 1
            scores[domain] = score

        # Apply context boost if available
        if context:
            recent_intents = context.get("goal_task_layer", {}).get("recent_intent_distribution", {})
            for domain, intent_score in recent_intents.items():
                if domain in scores:
                    scores[domain] += intent_score * 0.5  # Boost based on recent activity

        # Get max score
        max_score = max(scores.values()) if scores else 0

        if max_score == 0:
            return ("system", 0.3)  # Default to system with low confidence

        # Get domain with max score
        domain = max(scores, key=scores.get)

        # Calculate confidence
        confidence = min(0.95, 0.5 + (max_score * 0.12))

        return (domain, confidence)

    def _classify_urgency(self, message: str) -> str:
        """Classify message urgency."""
        for urgency in ["critical", "high", "medium", "low"]:
            for pattern in self.urgency_indicators[urgency]:
                if re.search(pattern, message, re.IGNORECASE):
                    return urgency

        return "medium"  # Default

    def _detect_emotion(self, message: str) -> str:
        """Detect user emotion from message (basic heuristic)."""
        positive_words = ["great", "thanks", "awesome", "perfect", "yes", "good"]
        negative_words = ["wrong", "bad", "no", "not", "don't", "can't"]
        frustrated_words = ["frustrated", "annoying", "why", "again", "still"]
        curious_words = ["how", "why", "what", "tell me", "curious", "wonder"]

        # Count keyword matches
        positive_count = sum(1 for w in positive_words if w in message)
        negative_count = sum(1 for w in negative_words if w in message)
        frustrated_count = sum(1 for w in frustrated_words if w in message)
        curious_count = sum(1 for w in curious_words if w in message)

        scores = {
            "positive": positive_count,
            "negative": negative_count,
            "frustrated": frustrated_count,
            "curious": curious_count
        }

        max_score = max(scores.values())

        if max_score == 0:
            return "neutral"

        return max(scores, key=scores.get)


# Global analyzer instance
_analyzer = None


def analyze_intent(message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Analyze message intent (convenience function).

    Args:
        message: User message
        context: Optional awareness context

    Returns:
        Intent classification dict
    """
    global _analyzer
    if _analyzer is None:
        _analyzer = IntentAnalyzer()

    return _analyzer.analyze(message, context)
