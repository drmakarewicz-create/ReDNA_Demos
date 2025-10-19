"""
Head Coach V2 Orchestrator
===========================

Main pipeline for Jarvis-class Head Coach interactions.

Flow:
1. Get awareness snapshot
2. Analyze intent
3. Decide routing
4. Execute (HC or delegate)
5. Log reflection data
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import json

from .situational_awareness import get_awareness_snapshot, build_awareness_context
from .intent_classifier import IntentClassifier
from .delegation_router import DelegationRouter

logger = logging.getLogger(__name__)


class HeadCoachOrchestrator:
    """
    Jarvis-class orchestrator for Head Coach v2.

    Coordinates awareness, intent, routing, and execution.
    """

    def __init__(self):
        """Initialize orchestrator."""
        self.intent_classifier = IntentClassifier()
        self.delegation_router = DelegationRouter(intent_classifier=self.intent_classifier)

    async def interact(
        self,
        user_id: str,
        message: str,
        current_coach: str = "head_coach"
    ) -> Dict[str, Any]:
        """
        Process user interaction through full v2 pipeline.

        Args:
            user_id: User identifier
            message: User message text
            current_coach: Currently active coach

        Returns:
            Response dict with content, metadata, routing info
        """
        start_time = time.time()

        # Step 1: Get awareness snapshot
        logger.info(f"HC v2: Building awareness for {user_id}")
        awareness = get_awareness_snapshot(user_id)

        # Step 2: Analyze intent
        logger.info(f"HC v2: Classifying intent")
        intent_result = self.intent_classifier.classify(message, awareness)

        # Step 3: Decide routing
        logger.info(f"HC v2: Routing decision")
        routing = self.delegation_router.route(
            message=message,
            user_id=user_id,
            current_coach=current_coach,
            context=awareness
        )

        # Step 4: Execute based on routing
        if routing["action"] == "delegate" and routing.get("requires_handoff"):
            # Delegate to specialist coach
            logger.info(f"HC v2: Delegating to {routing['target_coach']}")
            response_content = await self._delegate_to_coach(
                user_id=user_id,
                message=message,
                target_coach=routing["target_coach"],
                handoff_context=routing.get("handoff_context", {}),
                awareness=awareness
            )
        else:
            # HC handles directly
            logger.info(f"HC v2: HC handling directly")
            response_content = await self._handle_with_hc(
                user_id=user_id,
                message=message,
                awareness=awareness,
                intent_result=intent_result
            )

        # Step 5: Log interaction for reflection
        total_time_ms = (time.time() - start_time) * 1000
        self._log_interaction(
            user_id=user_id,
            message=message,
            intent_result=intent_result,
            routing=routing,
            response=response_content,
            awareness_summary=awareness.get("summary", {}),
            duration_ms=total_time_ms
        )

        # Build response
        return {
            "response": response_content,
            "metadata": {
                "intent": {
                    "primary_intent": intent_result.get("primary_intent"),
                    "confidence": intent_result.get("confidence"),
                    "requires_clarification": intent_result.get("requires_clarification", False)
                },
                "routing": {
                    "action": routing["action"],
                    "target_coach": routing["target_coach"],
                    "requires_handoff": routing.get("requires_handoff", False)
                },
                "awareness_summary": {
                    "emotional_tone": awareness["user_core_state"]["emotional_tone"],
                    "curiosity_hotspots": awareness["user_core_state"]["curiosity_hotspots"][:3],
                    "overall_rr": awareness["memory_layer"]["traits_summary"]["overall_rr"]
                },
                "performance": {
                    "total_time_ms": round(total_time_ms, 2),
                    "awareness_build_ms": awareness["policy"]["build_ms"]
                }
            }
        }

    async def _handle_with_hc(
        self,
        user_id: str,
        message: str,
        awareness: Dict[str, Any],
        intent_result: Dict[str, Any]
    ) -> str:
        """
        Handle interaction directly with Head Coach (with CReDNA personality).

        Args:
            user_id: User identifier
            message: User message
            awareness: Awareness snapshot
            intent_result: Intent classification

        Returns:
            HC response text
        """
        from ..hc_llm_agent import generate_reply

        # Build state snapshot for LLM
        state_snapshot = {
            "high_curiosity_traits": [
                {"trait": path, "curiosity": 75, "type": "trait"}
                for path in awareness["user_core_state"]["curiosity_hotspots"]
            ],
            "tolerance_for_nudging": 0.7,  # Default
            "overall_rr": awareness["memory_layer"]["traits_summary"]["overall_rr"],
            "emotional_tone": awareness["user_core_state"]["emotional_tone"]
        }

        # Get LLM configuration (from env or defaults)
        model_config = {
            "provider": "mock",  # Future: read from config
            "model": "gpt-4o-mini",
            "max_tokens": 300,
            "temperature": 0.7
        }

        # Load conversation history
        from ..hc_llm_agent import load_conversation_history
        conversation_history = load_conversation_history(user_id, limit=5)

        # Generate reply
        result = generate_reply(
            user_id=user_id,
            user_message=message,
            state_snapshot=state_snapshot,
            model_config=model_config,
            conversation_history=conversation_history
        )

        return result["content"]

    async def _delegate_to_coach(
        self,
        user_id: str,
        message: str,
        target_coach: str,
        handoff_context: Dict[str, Any],
        awareness: Dict[str, Any]
    ) -> str:
        """
        Delegate interaction to specialist coach.

        Args:
            user_id: User identifier
            message: User message
            target_coach: Target coach to delegate to
            handoff_context: Handoff context from routing decision
            awareness: Awareness snapshot

        Returns:
            Specialist coach response text
        """
        # Future: Actually delegate to specialist coach endpoints
        # For now, return placeholder acknowledging delegation

        return f"[Delegation to {target_coach}] I'm connecting you with our {target_coach.replace('_', ' ')} to help with this. They'll have access to your profile and conversation context."

    def _log_interaction(
        self,
        user_id: str,
        message: str,
        intent_result: Dict[str, Any],
        routing: Dict[str, Any],
        response: str,
        awareness_summary: Dict[str, Any],
        duration_ms: float
    ):
        """
        Log interaction for future reflection and learning.

        Args:
            user_id: User identifier
            message: User message (truncated for privacy)
            intent_result: Intent classification result
            routing: Routing decision
            response: Response text (truncated for privacy)
            awareness_summary: Awareness summary
            duration_ms: Total interaction duration
        """
        log_dir = Path(f"data/users/{user_id}/head_coach")
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "interactions.jsonl"

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_preview": message[:100],  # Privacy: truncate
            "intent": {
                "primary_intent": intent_result.get("primary_intent"),
                "confidence": intent_result.get("confidence")
            },
            "routing": {
                "action": routing["action"],
                "target_coach": routing["target_coach"]
            },
            "response_preview": response[:100],  # Privacy: truncate
            "awareness": awareness_summary,
            "performance_ms": duration_ms
        }

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log interaction for {user_id}: {e}")


# Global orchestrator instance
_orchestrator = None


async def process_interaction(
    user_id: str,
    message: str,
    current_coach: str = "head_coach"
) -> Dict[str, Any]:
    """
    Process user interaction through HC v2 pipeline (convenience function).

    Args:
        user_id: User identifier
        message: User message
        current_coach: Currently active coach

    Returns:
        Response dict with content and metadata
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = HeadCoachOrchestrator()

    return await _orchestrator.interact(user_id, message, current_coach)
