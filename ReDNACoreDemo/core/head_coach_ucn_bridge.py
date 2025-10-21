"""
Head Coach <-> UCN/RR Bridge
=============================

This module connects the UCN/RR curiosity signals to the Head Coach decision framework.

Flow:
1. UCN/RR engine calculates curiosity signals based on trait confidence
2. This bridge converts curiosity signals into CoreRecommendations
3. Head Coach deliberates on each recommendation
4. Decisions are returned for execution

This implements the "Core proposes, Head Coach disposes" architecture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .head_coach_decision import (
    BehavioralMode,
    CoreRecommendation,
    HeadCoachDecision,
    HeadCoachDecisionEngine,
    UserContext,
    AffectState
)

logger = logging.getLogger(__name__)

# Try to import UCN/RR engine
try:
    import sys
    ucn_rr_path = Path(__file__).resolve().parents[1] / "ucn_rr_engine"
    if str(ucn_rr_path) not in sys.path:
        sys.path.insert(0, str(ucn_rr_path))

    from curiosity import CuriosityEngine, CuriositySignal
    UCN_RR_AVAILABLE = True
except ImportError:
    CuriosityEngine = None
    CuriositySignal = None
    UCN_RR_AVAILABLE = False


@dataclass
class ActionPlan:
    """
    Complete action plan from Head Coach after processing curiosity signals.

    This is what gets presented to the user.
    """
    user_id: str
    timestamp: str

    # Accepted actions
    accepted_actions: List[HeadCoachDecision]

    # Deferred/rejected actions
    deferred_actions: List[HeadCoachDecision]

    # Summary stats
    total_signals_processed: int
    acceptance_rate: float
    dominant_mode: BehavioralMode

    # User-facing message
    greeting: str
    priority_message: Optional[str] = None
    celebration_message: Optional[str] = None

    # Provenance
    curiosity_signals_count: int = 0
    core_recommendations_count: int = 0


class HeadCoachUCNBridge:
    """
    Bridge between UCN/RR curiosity signals and Head Coach decisions.

    This is where "Core proposes, Head Coach disposes" happens.
    """

    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.decision_engine = HeadCoachDecisionEngine()

        # Initialize curiosity engine if available
        if UCN_RR_AVAILABLE and CuriosityEngine is not None:
            self.curiosity_engine = CuriosityEngine()
        else:
            self.curiosity_engine = None
            logger.warning("UCN/RR engine not available - running in degraded mode")

    def process_curiosity_signals(
        self,
        user_id: str,
        user_traits: Dict[str, int],
        user_context: Optional[UserContext] = None,
        max_actions: int = 5
    ) -> ActionPlan:
        """
        Main entry point: Convert curiosity signals into an action plan.

        Flow:
        1. Get curiosity signals from UCN/RR engine
        2. Convert to Core recommendations
        3. Head Coach deliberates on each
        4. Build action plan with accepted decisions

        Args:
            user_id: User identifier
            user_traits: Dict of {trait_path: ucn_value}
            user_context: Optional user context (defaults created if None)
            max_actions: Maximum number of actions to return

        Returns:
            ActionPlan with accepted/deferred actions
        """

        # Load or create user context
        if user_context is None:
            user_context = self._load_user_context(user_id)

        # Get curiosity signals from UCN/RR
        curiosity_signals = self._get_curiosity_signals(user_id, user_traits)

        # Convert to Core recommendations
        core_recommendations = self._convert_signals_to_recommendations(
            curiosity_signals,
            user_traits
        )

        # Head Coach deliberates on each recommendation
        decisions = []
        for rec in core_recommendations:
            decision = self.decision_engine.deliberate(rec, user_context)
            decisions.append(decision)

        # Separate accepted and deferred
        accepted = [d for d in decisions if d.accept]
        deferred = [d for d in decisions if not d.accept]

        # Limit to max_actions
        accepted = accepted[:max_actions]

        # Build action plan
        plan = self._build_action_plan(
            user_id,
            user_context,
            accepted,
            deferred,
            len(curiosity_signals),
            len(core_recommendations)
        )

        logger.info(
            f"[HC Bridge:{user_id}] Processed {len(curiosity_signals)} signals → "
            f"{len(accepted)} accepted, {len(deferred)} deferred"
        )

        return plan

    def _get_curiosity_signals(
        self,
        user_id: str,
        user_traits: Dict[str, int]
    ) -> List[Any]:
        """Get curiosity signals from UCN/RR engine"""

        if not UCN_RR_AVAILABLE or self.curiosity_engine is None:
            logger.warning(f"[HC Bridge:{user_id}] UCN/RR not available - returning empty signals")
            return []

        try:
            # Calculate RR first
            from rr_calculator import RRCalculator
            rr_calc = RRCalculator()

            # Calculate user's RR (min_traits defaults to 10)
            rr_percentile = rr_calc.calculate_rr(user_id, user_traits, min_traits=10)

            if rr_percentile is None:
                logger.warning(f"[HC Bridge:{user_id}] RR calculation failed")
                return []

            # Get curiosity signals
            signals = self.curiosity_engine.get_trait_curiosity_signals(
                user_traits,
                include_top_n=20
            )

            return signals

        except Exception as e:
            logger.error(f"[HC Bridge:{user_id}] Error getting curiosity signals: {e}", exc_info=True)
            return []

    def _convert_signals_to_recommendations(
        self,
        signals: List[Any],
        user_traits: Dict[str, int]
    ) -> List[CoreRecommendation]:
        """Convert curiosity signals to Core recommendations"""

        recommendations = []

        for signal in signals:
            # Extract signal data
            if hasattr(signal, 'trait_path'):
                trait_path = signal.trait_path
                curiosity = signal.curiosity_score
                priority_level = signal.priority
                reason = signal.reason
            elif isinstance(signal, dict):
                trait_path = signal.get('trait_path')
                curiosity = signal.get('curiosity_score', signal.get('curiosity', 0))
                priority_level = signal.get('priority', 'medium')
                reason = signal.get('reason', 'unknown')
            else:
                continue

            # Get UCN and RR for this trait
            ucn = user_traits.get(trait_path, 0)
            rr = 100 - curiosity  # RR = 100 - curiosity (RR is 0-100 percentile)

            # Determine recommendation type based on curiosity and UCN
            if ucn < 300:
                rec_type = "gather_evidence"
                action = f"Add evidence for {self._trait_display_name(trait_path)}"
                time_estimate = 2
            elif curiosity > 500:
                rec_type = "confirm_trait"
                action = f"Confirm {self._trait_display_name(trait_path)} value"
                time_estimate = 3
            else:
                rec_type = "explore_gap"
                action = f"Explore {self._trait_display_name(trait_path)}"
                time_estimate = 5

            # Map curiosity levels to priority
            if curiosity > 700:
                priority = "urgent"
            elif curiosity > 500:
                priority = "high"
            elif curiosity > 300:
                priority = "medium"
            else:
                priority = "low"

            # Create recommendation
            rec = CoreRecommendation(
                rec_type=rec_type,
                trait_path=trait_path,
                priority=priority,
                estimated_time_mins=time_estimate,
                curiosity_value=curiosity,
                ucn_value=ucn,
                rr_value=rr,
                reasoning=f"Curiosity level {curiosity:.0f} indicates {reason}",
                suggested_action=action,
                data_quality_impact="high" if ucn < 500 else "medium",
                system_benefit=f"Reduces curiosity from {curiosity:.0f} to ~{max(0, curiosity - 200):.0f}"
            )

            recommendations.append(rec)

        # Sort by priority and curiosity
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(
            key=lambda r: (priority_order.get(r.priority, 99), -r.curiosity_value)
        )

        return recommendations

    def _trait_display_name(self, trait_path: str) -> str:
        """Convert trait path to user-friendly name"""
        if not trait_path:
            return "trait"

        parts = trait_path.split('.')
        if len(parts) >= 2:
            # Return last part (e.g., "PaDNA.EyeDNA.Color" → "Color")
            return parts[-1].replace('_', ' ')

        return trait_path.replace('_', ' ')

    def _load_user_context(self, user_id: str) -> UserContext:
        """Load user context from storage or create default"""

        # Try to load from storage
        context_file = self.data_root / "users" / user_id / "hc" / "context.json"

        if context_file.exists():
            try:
                import json
                with open(context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Reconstruct UserContext from saved data
                affect_data = data.get('affect_state', {})
                affect_state = AffectState(
                    stress_level=affect_data.get('stress_level', 5),
                    emotional_load=affect_data.get('emotional_load', 5),
                    mood=affect_data.get('mood', 'neutral'),
                    energy_level=affect_data.get('energy_level', 5),
                    openness_to_change=affect_data.get('openness_to_change', 5),
                    receptivity_score=affect_data.get('receptivity_score', 5)
                )

                context = UserContext(
                    user_id=user_id,
                    affect_state=affect_state,
                    preferred_name=data.get('preferred_name'),
                    tone_preference=data.get('tone_preference', 'warm'),
                    current_goals=data.get('current_goals', []),
                    proactive_nudges=data.get('proactive_nudges', True)
                )

                return context

            except Exception as e:
                logger.warning(f"[HC Bridge:{user_id}] Error loading context: {e}")

        # Create default context
        return UserContext(user_id=user_id)

    def _build_action_plan(
        self,
        user_id: str,
        context: UserContext,
        accepted: List[HeadCoachDecision],
        deferred: List[HeadCoachDecision],
        signals_count: int,
        recs_count: int
    ) -> ActionPlan:
        """Build final action plan for user"""

        # Calculate acceptance rate
        total = len(accepted) + len(deferred)
        acceptance_rate = len(accepted) / total if total > 0 else 0.0

        # Determine dominant mode
        if accepted:
            mode_counts = {}
            for decision in accepted:
                mode = decision.mode
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            dominant_mode = max(mode_counts, key=mode_counts.get)
        else:
            dominant_mode = BehavioralMode.SERVANT

        # Build greeting based on mode and context
        greeting = self._build_greeting(context, dominant_mode, len(accepted))

        # Build priority message if there's an urgent action
        priority_message = None
        urgent_actions = [a for a in accepted if a.action_type in ["gather_evidence", "confirm_trait"]]
        if urgent_actions:
            priority_message = f"Quick win: {urgent_actions[0].action_description} (takes ~{urgent_actions[0].estimated_time_mins} min)"

        plan = ActionPlan(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            accepted_actions=accepted,
            deferred_actions=deferred,
            total_signals_processed=signals_count,
            acceptance_rate=acceptance_rate,
            dominant_mode=dominant_mode,
            greeting=greeting,
            priority_message=priority_message,
            curiosity_signals_count=signals_count,
            core_recommendations_count=recs_count
        )

        return plan

    def _build_greeting(
        self,
        context: UserContext,
        mode: BehavioralMode,
        action_count: int
    ) -> str:
        """Build personalized greeting"""

        name = context.preferred_name or "there"

        if mode == BehavioralMode.MENTOR:
            if action_count > 0:
                return f"Hi {name}! I've identified {action_count} opportunity/ies to improve your profile. Let me walk you through them."
            else:
                return f"Hi {name}! Your profile looks great right now. No immediate actions needed."

        elif mode == BehavioralMode.SERVANT:
            if action_count > 0:
                return f"Hey {name}, {action_count} quick task(s) ready for you."
            else:
                return f"All set, {name}. Nothing pressing right now."

        elif mode == BehavioralMode.GUARDIAN:
            if action_count > 0:
                return f"Hi {name}. I'm keeping things light today – just {action_count} optional task(s) when you're ready."
            else:
                return f"Hi {name}. Taking a break from tasks today – you've got this covered."

        elif mode == BehavioralMode.STRATEGIST:
            if action_count > 0:
                return f"Hi {name}! Here's the next step toward your goals ({action_count} action(s))."
            else:
                return f"Hi {name}. You're on track with your goals. Keep it up!"

        else:  # CONFIDANT
            if context.is_vulnerable():
                return f"Hi {name}. I'm here if you need me. No pressure on tasks today."
            else:
                return f"Hi {name}. Hope you're doing well. I've got {action_count} suggestion(s) if you're interested."


# Factory function
def create_ucn_bridge(data_root: str = "data") -> HeadCoachUCNBridge:
    """Create a new Head Coach UCN/RR bridge"""
    return HeadCoachUCNBridge(data_root)


__all__ = [
    "ActionPlan",
    "HeadCoachUCNBridge",
    "create_ucn_bridge"
]
