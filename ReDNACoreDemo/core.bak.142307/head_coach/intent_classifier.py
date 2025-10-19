"""
Head Coach Intent Classification Engine
========================================

Rule-based intent classification for user messages to route to specialist coaches.

Detects intents:
- career_guidance: Job, interview, promotion, career development
- relationship_advice: Dating, romance, social connections
- personality_assessment: Traits, personality tests, self-discovery
- photo_analysis: Appearance, photos, attractiveness
- belief_exploration: Values, beliefs, worldview
- general_coaching: General life advice, unclear domain
- meta_request: Questions about the system itself
- unclear: Ambiguous or insufficient information

Future: Upgrade to ML-based classification for better accuracy.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Intent classification rules (keyword-based for v1)
INTENT_RULES = {
    "career_guidance": {
        "keywords": [
            "job", "career", "work", "interview", "resume", "cv", "promotion",
            "salary", "raise", "boss", "manager", "colleague", "workplace",
            "employment", "hired", "fired", "quit", "profession", "occupation",
            "networking", "linkedin", "portfolio", "skills", "experience"
        ],
        "patterns": [
            r"\b(career|job|work)\s+(change|switch|transition)",
            r"\b(interview|resume)\s+(tips|advice|help)",
            r"\bhow\s+to\s+(get|find|land)\s+a\s+job",
            r"\bshould\s+i\s+(quit|stay|leave)\s+(my|this)\s+job"
        ]
    },
    "relationship_advice": {
        "keywords": [
            "relationship", "dating", "romance", "love", "partner", "girlfriend",
            "boyfriend", "spouse", "marriage", "date", "attraction", "flirt",
            "breakup", "ex", "crush", "compatibility", "soulmate", "chemistry",
            "intimacy", "commitment", "trust", "communication", "conflict"
        ],
        "patterns": [
            r"\b(dating|relationship)\s+(advice|tips|help)",
            r"\bhow\s+to\s+(attract|find|meet)\s+(women|men|someone)",
            r"\bshould\s+i\s+(break\s+up|stay|leave)\s+(with|my)",
            r"\b(my|his|her)\s+(boyfriend|girlfriend|partner)"
        ]
    },
    "personality_assessment": {
        "keywords": [
            "personality", "trait", "test", "assessment", "quiz", "character",
            "temperament", "type", "mbti", "big five", "strengths", "weaknesses",
            "introvert", "extrovert", "who am i", "self-discovery", "identity"
        ],
        "patterns": [
            r"\bpersonality\s+(test|assessment|quiz)",
            r"\bwhat\s+(kind|type)\s+of\s+person",
            r"\bam\s+i\s+an?\s+(introvert|extrovert)",
            r"\bmy\s+(strengths|weaknesses|traits)"
        ]
    },
    "photo_analysis": {
        "keywords": [
            "photo", "picture", "selfie", "appearance", "looks", "attractive",
            "rating", "rate me", "hotornot", "facial", "hair", "eyes", "smile",
            "clothing", "style", "outfit", "grooming", "image"
        ],
        "patterns": [
            r"\b(rate|analyze|review)\s+(my|this)\s+(photo|picture|selfie)",
            r"\bhow\s+(do\s+i|attractive|good)\s+look",
            r"\b(photo|picture)\s+(feedback|advice|tips)",
            r"\bimprove\s+(my|the)\s+(appearance|looks)"
        ]
    },
    "belief_exploration": {
        "keywords": [
            "belief", "value", "worldview", "philosophy", "meaning", "purpose",
            "religion", "spiritual", "faith", "ethics", "morals", "principles",
            "conviction", "ideology", "perspective", "mindset", "growth mindset"
        ],
        "patterns": [
            r"\bwhat\s+do\s+i\s+believe",
            r"\bmy\s+(values|beliefs|worldview)",
            r"\blife\s+(purpose|meaning)",
            r"\b(core|fundamental)\s+(beliefs|values)"
        ]
    },
    "meta_request": {
        "keywords": [
            "help", "how does this work", "what can you do", "capabilities",
            "features", "about you", "who are you", "explain", "guide", "tutorial"
        ],
        "patterns": [
            r"\bhow\s+does\s+(this|the\s+system)\s+work",
            r"\bwhat\s+can\s+you\s+(do|help)",
            r"\b(show|give)\s+me\s+(help|guide|tutorial)",
            r"\bwho\s+are\s+you"
        ]
    }
}

# Coach mapping
INTENT_TO_COACH = {
    "career_guidance": "career_coach",
    "relationship_advice": "relationship_coach",
    "personality_assessment": "personality_test_coach",
    "photo_analysis": "photo_coach",
    "belief_exploration": "beliefdna_coach",
    "general_coaching": "head_coach",
    "meta_request": "head_coach",
    "unclear": None
}


class IntentClassifier:
    """
    Rule-based intent classifier for user messages.

    V1: Keyword and pattern matching
    V2 (future): ML-based classification for better accuracy
    """

    def __init__(self):
        """Initialize intent classifier."""
        self.version = "v1.0-rule-based"
        self.method = "rule_based"

    def classify(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classify user message intent.

        Args:
            message: User message text
            context: Optional context (previous messages, user state, etc.)

        Returns:
            Intent classification result matching hc_intent.schema.json
        """
        start_time = time.time()

        # Normalize message
        message_lower = message.lower().strip()

        # Detect all intents with confidence scores
        intent_scores = self._score_all_intents(message_lower)

        # Get primary intent (highest confidence)
        if not intent_scores:
            primary_intent = "unclear"
            confidence = 0.0
            target_coach = None
            signals = {"keywords": [], "patterns": [], "context_clues": []}
        else:
            primary_intent, primary_score, primary_signals = intent_scores[0]
            confidence = primary_score
            target_coach = INTENT_TO_COACH.get(primary_intent)
            signals = primary_signals

        # Get secondary intents (if any)
        secondary_intents = [
            {"intent": intent, "confidence": score}
            for intent, score, _ in intent_scores[1:4]  # Top 3 secondary
            if score > 0.2  # Threshold for secondary intents
        ]

        # Extract metadata
        metadata = self._extract_metadata(message)

        # Determine if clarification is needed
        requires_clarification = confidence < 0.5 or primary_intent == "unclear"
        clarification_prompts = self._generate_clarification_prompts(
            primary_intent, intent_scores
        ) if requires_clarification else []

        # Build delegation recommendation
        delegation_rec = self._build_delegation_recommendation(
            primary_intent,
            confidence,
            target_coach,
            context or {}
        )

        # Build result
        result = {
            "primary_intent": primary_intent,
            "confidence": round(confidence, 3),
            "target_coach": target_coach,
            "secondary_intents": secondary_intents,
            "intent_signals": signals,
            "delegation_recommendation": delegation_rec,
            "requires_clarification": requires_clarification,
            "clarification_prompts": clarification_prompts,
            "metadata": metadata,
            "policy": {
                "classifier_version": self.version,
                "schema": "hc_intent.schema.json@v1",
                "classification_ms": round((time.time() - start_time) * 1000, 2),
                "method": self.method
            }
        }

        return result

    def _score_all_intents(
        self,
        message_lower: str
    ) -> List[Tuple[str, float, Dict[str, List[str]]]]:
        """
        Score all intents and return sorted by confidence.

        Returns:
            List of (intent, score, signals) tuples sorted by score descending
        """
        scores = []

        for intent, rules in INTENT_RULES.items():
            score, signals = self._score_intent(message_lower, rules)
            if score > 0:
                scores.append((intent, score, signals))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores

    def _score_intent(
        self,
        message_lower: str,
        rules: Dict[str, List[str]]
    ) -> Tuple[float, Dict[str, List[str]]]:
        """
        Score a single intent based on keyword and pattern matches.

        Returns:
            (score, signals) tuple
        """
        matched_keywords = []
        matched_patterns = []

        # Check keywords
        for keyword in rules.get("keywords", []):
            if keyword in message_lower:
                matched_keywords.append(keyword)

        # Check patterns
        for pattern in rules.get("patterns", []):
            if re.search(pattern, message_lower, re.IGNORECASE):
                matched_patterns.append(pattern)

        # Calculate score
        # Pattern matches are weighted higher (0.3 each) than keywords (0.1 each)
        keyword_score = min(len(matched_keywords) * 0.1, 0.6)
        pattern_score = min(len(matched_patterns) * 0.3, 0.9)
        total_score = min(keyword_score + pattern_score, 1.0)

        signals = {
            "keywords": matched_keywords[:10],  # Max 10
            "patterns": [p[:50] for p in matched_patterns[:5]],  # Max 5, truncate
            "context_clues": []
        }

        return total_score, signals

    def _extract_metadata(self, message: str) -> Dict[str, Any]:
        """Extract metadata from message."""
        question_count = message.count("?")

        # Simple sentiment detection (keyword-based)
        positive_words = ["great", "good", "happy", "love", "awesome", "excellent"]
        negative_words = ["bad", "terrible", "hate", "awful", "frustrated", "angry"]

        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)

        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        elif positive_count > 0 or negative_count > 0:
            sentiment = "mixed"
        else:
            sentiment = "neutral"

        # Urgency detection
        urgent_words = ["urgent", "asap", "immediately", "emergency", "critical", "now"]
        urgency_count = sum(1 for word in urgent_words if word in message_lower)

        if urgency_count >= 2:
            urgency_level = "critical"
        elif urgency_count == 1:
            urgency_level = "high"
        elif "?" in message or "help" in message_lower:
            urgency_level = "normal"
        else:
            urgency_level = "low"

        return {
            "message_length": len(message),
            "question_count": question_count,
            "sentiment": sentiment,
            "urgency_level": urgency_level
        }

    def _generate_clarification_prompts(
        self,
        primary_intent: str,
        intent_scores: List[Tuple[str, float, Dict[str, List[str]]]]
    ) -> List[str]:
        """Generate clarifying questions when intent is unclear."""
        if not intent_scores or intent_scores[0][1] < 0.3:
            # Very unclear - ask general clarification
            return [
                "Could you tell me more about what you're looking to work on?",
                "Are you interested in career guidance, relationship advice, or something else?",
                "What's the main area you'd like help with today?"
            ]

        # If we have multiple competing intents, ask to disambiguate
        if len(intent_scores) >= 2 and intent_scores[1][1] > 0.4:
            intent1, score1, _ = intent_scores[0]
            intent2, score2, _ = intent_scores[1]

            return [
                f"I'm detecting interest in both {intent1.replace('_', ' ')} and {intent2.replace('_', ' ')}. Which would you like to focus on?",
                "Could you clarify which area is most important to you right now?",
                "Would you like to explore both topics, or focus on one first?"
            ]

        # Low confidence on primary - ask for more details
        return [
            f"I think you might be interested in {primary_intent.replace('_', ' ')}. Is that correct?",
            "Could you provide a bit more detail about what you're looking for?",
            "What specific aspect would you like to explore?"
        ]

    def _build_delegation_recommendation(
        self,
        intent: str,
        confidence: float,
        target_coach: Optional[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build delegation routing recommendation."""
        # Delegation threshold: >0.7 confidence and specialist coach available
        should_delegate = confidence > 0.7 and target_coach and target_coach != "head_coach"

        if should_delegate:
            reason = f"High confidence ({confidence:.1%}) {intent.replace('_', ' ')} query with specialist coach available"
            routing_strategy = "direct"
        elif confidence > 0.5 and target_coach:
            reason = f"Moderate confidence ({confidence:.1%}) - collaborative approach recommended"
            routing_strategy = "collaborative"
            should_delegate = True  # Still delegate but with head coach oversight
        elif confidence < 0.3:
            reason = "Low confidence - retain for clarification by head coach"
            routing_strategy = "retain"
        else:
            reason = f"General coaching query or meta request - head coach appropriate"
            routing_strategy = "retain"

        rec = {
            "should_delegate": should_delegate,
            "reason": reason,
            "routing_strategy": routing_strategy
        }

        # Add handoff context if delegating
        if should_delegate and target_coach:
            rec["handoff_context"] = {
                "user_state_summary": context.get("user_state_summary", "Unknown state"),
                "key_concerns": context.get("key_concerns", []),
                "previous_coach": context.get("active_coach", "head_coach")
            }

        return rec
