"""
Head Coach Delegation Router
=============================

Routes user interactions to appropriate specialist coaches based on intent classification.

Routing strategies:
- direct: Full delegation to specialist coach
- collaborative: Specialist coach with head coach oversight
- escalation: Escalate from specialist back to head coach
- retain: Keep with head coach

Tracks delegation history for learning and optimization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)


class DelegationRouter:
    """
    Routes user messages to appropriate coaches based on intent.

    Integrates with IntentClassifier for intent detection and applies
    routing policies for optimal delegation.
    """

    def __init__(self, intent_classifier: Optional[IntentClassifier] = None):
        """
        Initialize delegation router.

        Args:
            intent_classifier: Optional custom intent classifier (defaults to IntentClassifier())
        """
        self.classifier = intent_classifier or IntentClassifier()
        self.routing_history = []  # For future learning/optimization

    def route(
        self,
        message: str,
        user_id: str,
        current_coach: str = "head_coach",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route user message to appropriate coach.

        Args:
            message: User message text
            user_id: User ID
            current_coach: Currently active coach
            context: Optional context (awareness snapshot, user state, etc.)

        Returns:
            Routing decision with target coach and handoff details
        """
        # Classify intent
        intent_result = self.classifier.classify(message, context)

        # Build routing decision
        delegation_rec = intent_result["delegation_recommendation"]
        target_coach = intent_result["target_coach"]

        # Apply routing policy
        routing_decision = self._apply_routing_policy(
            current_coach=current_coach,
            target_coach=target_coach,
            intent_result=intent_result,
            context=context or {}
        )

        # Log routing decision for future optimization
        self._log_routing_decision(user_id, message, routing_decision)

        return routing_decision

    def _apply_routing_policy(
        self,
        current_coach: str,
        target_coach: Optional[str],
        intent_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply routing policy to determine final coach assignment.

        Handles edge cases:
        - Already at target coach -> retain
        - Switching between specialists -> collaborative handoff
        - Low confidence -> retain for clarification
        """
        delegation_rec = intent_result["delegation_recommendation"]
        routing_strategy = delegation_rec["routing_strategy"]
        primary_intent = intent_result["primary_intent"]
        confidence = intent_result["confidence"]

        # Case 1: Already at target coach
        if current_coach == target_coach:
            return {
                "action": "retain",
                "target_coach": current_coach,
                "reason": f"Already being handled by {current_coach}",
                "requires_handoff": False,
                "intent_analysis": intent_result,
                "routing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "routing_strategy": "retain",
                    "confidence": confidence
                }
            }

        # Case 2: Unclear intent or low confidence -> retain for clarification
        if routing_strategy == "retain" or intent_result["requires_clarification"]:
            return {
                "action": "retain",
                "target_coach": current_coach,
                "reason": delegation_rec["reason"],
                "requires_handoff": False,
                "clarification_needed": True,
                "clarification_prompts": intent_result["clarification_prompts"],
                "intent_analysis": intent_result,
                "routing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "routing_strategy": routing_strategy,
                    "confidence": confidence
                }
            }

        # Case 3: Direct delegation to specialist
        if routing_strategy == "direct":
            return {
                "action": "delegate",
                "target_coach": target_coach,
                "reason": delegation_rec["reason"],
                "requires_handoff": True,
                "handoff_type": "direct",
                "handoff_context": delegation_rec.get("handoff_context", {}),
                "intent_analysis": intent_result,
                "routing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "routing_strategy": routing_strategy,
                    "confidence": confidence,
                    "previous_coach": current_coach
                }
            }

        # Case 4: Collaborative delegation (moderate confidence)
        if routing_strategy == "collaborative":
            return {
                "action": "delegate",
                "target_coach": target_coach,
                "reason": delegation_rec["reason"],
                "requires_handoff": True,
                "handoff_type": "collaborative",
                "oversight_coach": "head_coach",
                "handoff_context": delegation_rec.get("handoff_context", {}),
                "intent_analysis": intent_result,
                "routing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "routing_strategy": routing_strategy,
                    "confidence": confidence,
                    "previous_coach": current_coach
                }
            }

        # Case 5: Escalation (specialist -> head coach)
        if routing_strategy == "escalation":
            return {
                "action": "escalate",
                "target_coach": "head_coach",
                "reason": "Escalating from specialist to head coach for broader perspective",
                "requires_handoff": True,
                "handoff_type": "escalation",
                "handoff_context": {
                    "escalation_reason": context.get("escalation_reason", "User request"),
                    "previous_coach": current_coach,
                    "conversation_summary": context.get("conversation_summary", "")
                },
                "intent_analysis": intent_result,
                "routing_metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "routing_strategy": routing_strategy,
                    "confidence": confidence,
                    "previous_coach": current_coach
                }
            }

        # Default: retain
        return {
            "action": "retain",
            "target_coach": current_coach,
            "reason": "No clear delegation path found",
            "requires_handoff": False,
            "intent_analysis": intent_result,
            "routing_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "routing_strategy": "retain",
                "confidence": confidence
            }
        }

    def _log_routing_decision(
        self,
        user_id: str,
        message: str,
        routing_decision: Dict[str, Any]
    ):
        """
        Log routing decision for future learning/optimization.

        Future: Store in database for ML-based routing optimization.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "message_preview": message[:100],  # Privacy: truncate
            "action": routing_decision["action"],
            "target_coach": routing_decision["target_coach"],
            "confidence": routing_decision["routing_metadata"]["confidence"],
            "primary_intent": routing_decision["intent_analysis"]["primary_intent"]
        }

        self.routing_history.append(log_entry)

        # Keep only last 1000 entries in memory
        if len(self.routing_history) > 1000:
            self.routing_history = self.routing_history[-1000:]

        logger.info(f"Routing decision: {log_entry['action']} -> {log_entry['target_coach']} (confidence: {log_entry['confidence']:.2f})")

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics for monitoring/optimization.

        Returns:
            Statistics on routing decisions, delegation rates, confidence distribution
        """
        if not self.routing_history:
            return {
                "total_decisions": 0,
                "delegation_rate": 0.0,
                "avg_confidence": 0.0,
                "coach_distribution": {},
                "intent_distribution": {}
            }

        total = len(self.routing_history)
        delegations = sum(1 for entry in self.routing_history if entry["action"] == "delegate")
        avg_confidence = sum(entry["confidence"] for entry in self.routing_history) / total

        # Coach distribution
        coach_dist = {}
        for entry in self.routing_history:
            coach = entry["target_coach"]
            coach_dist[coach] = coach_dist.get(coach, 0) + 1

        # Intent distribution
        intent_dist = {}
        for entry in self.routing_history:
            intent = entry["primary_intent"]
            intent_dist[intent] = intent_dist.get(intent, 0) + 1

        return {
            "total_decisions": total,
            "delegation_rate": round(delegations / total, 3),
            "avg_confidence": round(avg_confidence, 3),
            "coach_distribution": coach_dist,
            "intent_distribution": intent_dist
        }
