"""
Head Coach Decision Framework
==============================

Implements the behavioral modes and decision logic for the Head Coach.

The Head Coach acts as "Jarvis to Tony Stark" - a dedicated AI companion that:
- Receives recommendations from Core/UCN-RR
- Makes final decisions based on deep understanding of the user
- Prioritizes user well-being over system needs
- Operates in 5 behavioral modes: Mentor, Servant, Guardian, Strategist, Confidant

Chain of Authority:
1. Core/UCN-RR proposes (based on curiosity, patterns, system needs)
2. Head Coach disposes (based on user context, relationship, well-being)
3. User always has final say

Golden Rule: "UCN-RR proposes, Head Coach disposes"
Prime Directive: "Understand and improve the User's life experience while sustaining system health (User experience comes first)"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BehavioralMode(Enum):
    """
    Five behavioral modes for Head Coach.

    Each mode represents a different way of relating to the user:
    - MENTOR: Educational, patient, explaining "why"
    - SERVANT: Efficient executor, minimal friction
    - GUARDIAN: Protective, shielding user from system demands
    - STRATEGIST: Multi-step planner, long-term thinking
    - CONFIDANT: Empathetic supporter, building trust
    """
    MENTOR = "mentor"
    SERVANT = "servant"
    GUARDIAN = "guardian"
    STRATEGIST = "strategist"
    CONFIDANT = "confidant"


class InterventionStyle(Enum):
    """How Head Coach delivers recommendations"""
    DIRECT = "direct"           # Immediate action
    GENTLE = "gentle"           # Soft suggestion
    DEFERRED = "deferred"       # "Not now, maybe later"
    CONTEXTUAL = "contextual"   # Wait for the right moment
    SILENT = "silent"           # Don't mention it


@dataclass
class AffectState:
    """
    User's current emotional/cognitive state.

    This helps Head Coach choose the right mode and intervention style.
    """
    stress_level: int = 5        # 0-10 (0=zen, 10=overwhelmed)
    emotional_load: int = 5      # 0-10 (0=light, 10=heavy)
    mood: str = "neutral"        # neutral, happy, sad, frustrated, excited
    energy_level: int = 5        # 0-10 (0=exhausted, 10=energized)
    openness_to_change: int = 5  # 0-10 (0=resistant, 10=eager)
    receptivity_score: int = 5   # 0-10 (0=closed, 10=open)
    last_interaction: Optional[str] = None  # ISO timestamp
    interaction_frequency: str = "normal"   # rare, normal, frequent

    def overall_readiness(self) -> int:
        """Calculate overall readiness for new tasks (0-10)"""
        # Lower stress and higher energy = more ready
        readiness = (
            (10 - self.stress_level) * 0.3 +
            self.energy_level * 0.3 +
            self.openness_to_change * 0.2 +
            self.receptivity_score * 0.2
        )
        return int(max(0, min(10, readiness)))


@dataclass
class UserContext:
    """
    Everything Head Coach knows about the user.

    This is the deep understanding that allows HC to make better decisions
    than Core alone.
    """
    user_id: str
    affect_state: AffectState = field(default_factory=AffectState)

    # Relationship data
    preferred_name: Optional[str] = None
    tone_preference: str = "warm"  # warm, professional, casual
    communication_style: str = "balanced"  # minimal, balanced, detailed

    # User patterns
    typical_session_length_mins: int = 15
    preferred_time_of_day: Optional[str] = None  # morning, afternoon, evening
    response_to_nudges: str = "neutral"  # positive, neutral, negative
    task_completion_rate: float = 0.7  # 0.0-1.0

    # Goals and boundaries
    current_goals: List[str] = field(default_factory=list)
    topics_to_avoid: List[str] = field(default_factory=list)
    trusted_coaches: List[str] = field(default_factory=list)

    # Preferences
    explain_suggestions: bool = True
    proactive_nudges: bool = True
    celebrate_milestones: bool = True

    def is_vulnerable(self) -> bool:
        """Check if user is in a vulnerable state"""
        return (
            self.affect_state.stress_level > 7 or
            self.affect_state.emotional_load > 7 or
            self.affect_state.mood in ["sad", "frustrated", "anxious"]
        )

    def has_time_available(self) -> bool:
        """Estimate if user has time for tasks"""
        return self.affect_state.stress_level < 6 and self.affect_state.energy_level > 4


@dataclass
class CoreRecommendation:
    """
    Recommendation from Core/UCN-RR system.

    This is what the system WANTS to do based on curiosity, patterns, etc.
    Head Coach will decide whether to act on it.
    """
    rec_type: str  # "gather_evidence", "confirm_trait", "explore_gap", "celebrate_milestone"
    trait_path: Optional[str] = None
    priority: str = "medium"  # low, medium, high, urgent
    estimated_time_mins: int = 2
    curiosity_value: float = 0.0  # 0-1000
    ucn_value: float = 0.0  # 0-1000
    rr_value: float = 0.0  # 0-1000
    reasoning: str = ""
    suggested_action: str = ""
    data_quality_impact: str = "medium"  # low, medium, high
    system_benefit: str = ""  # Why the system wants this


@dataclass
class HeadCoachDecision:
    """
    Final decision from Head Coach after deliberation.

    This is what will actually happen.
    """
    accept: bool  # Accept Core's recommendation?
    mode: BehavioralMode  # Which mode was used
    intervention_style: InterventionStyle

    # Modified action (may differ from Core's suggestion)
    action_type: str
    action_description: str
    estimated_time_mins: int

    # Reasoning (for transparency and provenance)
    decision_reasoning: str
    user_benefit: str  # Why this helps the user
    overridden: bool = False  # Did HC override Core?
    override_reason: Optional[str] = None

    # Timing
    when_to_present: str = "now"  # now, later, never, contextual
    defer_until: Optional[str] = None  # ISO timestamp

    # Context for execution
    message_to_user: Optional[str] = None
    celebration: Optional[str] = None

    # Provenance
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    core_rec_id: Optional[str] = None


class HeadCoachDecisionEngine:
    """
    The decision engine that implements the 6-check deliberation framework.

    This is where "Jarvis to Tony Stark" intelligence lives.
    """

    def __init__(self):
        self.decision_history: List[HeadCoachDecision] = []

    def deliberate(
        self,
        recommendation: CoreRecommendation,
        user_context: UserContext
    ) -> HeadCoachDecision:
        """
        Run the 6-check deliberation framework.

        Questions:
        1. Does user need this? (benefit check)
        2. Is user ready? (readiness check)
        3. Is timing good? (timing check)
        4. Will this help relationship? (trust check)
        5. Will this make user happy? (happiness check)
        6. "Would Jarvis do this for Tony?" (final check)

        Returns:
            HeadCoachDecision with accept/reject and reasoning
        """

        # Check 1: Does user need this?
        user_needs_it = self._check_user_benefit(recommendation, user_context)

        # Check 2: Is user ready?
        user_ready = self._check_user_readiness(recommendation, user_context)

        # Check 3: Is timing good?
        timing_good = self._check_timing(recommendation, user_context)

        # Check 4: Will this help relationship?
        helps_relationship = self._check_relationship_impact(recommendation, user_context)

        # Check 5: Will this make user happy?
        makes_user_happy = self._check_happiness_impact(recommendation, user_context)

        # Check 6: "Would Jarvis do this?"
        jarvis_check = self._jarvis_check(
            user_needs_it,
            user_ready,
            timing_good,
            helps_relationship,
            makes_user_happy,
            recommendation,
            user_context
        )

        # Choose behavioral mode
        mode = self._select_mode(user_context, recommendation)

        # Make decision
        if jarvis_check:
            decision = self._create_acceptance_decision(
                recommendation,
                user_context,
                mode,
                user_needs_it,
                user_ready,
                timing_good,
                helps_relationship,
                makes_user_happy
            )
        else:
            decision = self._create_rejection_decision(
                recommendation,
                user_context,
                mode,
                user_needs_it,
                user_ready,
                timing_good,
                helps_relationship,
                makes_user_happy
            )

        # Log decision
        self.decision_history.append(decision)
        logger.info(
            f"[HC Decision] {decision.mode.value} mode: "
            f"{'ACCEPT' if decision.accept else 'REJECT'} - {decision.decision_reasoning}"
        )

        return decision

    def _check_user_benefit(
        self,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """Check 1: Does user actually benefit from this?"""

        # If it's a celebration, user benefits from positive feedback
        if rec.rec_type == "celebrate_milestone":
            return True

        # If user has explicitly set this as a goal
        if rec.trait_path and any(goal in rec.trait_path for goal in ctx.current_goals):
            return True

        # If curiosity is very high and user likes proactive nudges
        if rec.curiosity_value > 800 and ctx.proactive_nudges:
            return True

        # If this fills a major gap in their profile
        if rec.ucn_value < 300:  # Low confidence trait
            return True

        # Default: modest benefit
        return rec.priority in ["high", "urgent"]

    def _check_user_readiness(
        self,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """Check 2: Is user ready for this task?"""

        readiness = ctx.affect_state.overall_readiness()

        # Low-effort tasks: almost always ready
        if rec.estimated_time_mins <= 2:
            return readiness > 2

        # Medium tasks: need decent readiness
        if rec.estimated_time_mins <= 5:
            return readiness > 5

        # Long tasks: need high readiness
        return readiness > 7

    def _check_timing(
        self,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """Check 3: Is timing good?"""

        # Never interrupt a vulnerable user with system tasks
        if ctx.is_vulnerable():
            return rec.rec_type == "celebrate_milestone"  # Only celebrations

        # Check if user has time
        if not ctx.has_time_available():
            return False

        # Check interaction frequency
        if ctx.affect_state.interaction_frequency == "rare":
            # Don't overwhelm rare users
            return rec.priority == "urgent"

        return True

    def _check_relationship_impact(
        self,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """Check 4: Will this help or hurt the relationship?"""

        # If user has negative response to nudges, be very careful
        if ctx.response_to_nudges == "negative":
            return rec.priority == "urgent" or rec.rec_type == "celebrate_milestone"

        # If user likes detailed explanations, benefit from educational tasks
        if ctx.explain_suggestions and rec.reasoning:
            return True

        # If user has low task completion rate, don't pile on
        if ctx.task_completion_rate < 0.5:
            return rec.estimated_time_mins <= 2  # Only quick wins

        return True

    def _check_happiness_impact(
        self,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """Check 5: Will this make user happy?"""

        # Celebrations always make people happy
        if rec.rec_type == "celebrate_milestone":
            return True

        # Quick wins that show visible progress make people happy
        if rec.estimated_time_mins <= 2 and rec.data_quality_impact == "high":
            return True

        # Aligning with user goals makes people happy
        if rec.trait_path and any(goal in rec.trait_path for goal in ctx.current_goals):
            return True

        # High-effort low-reward tasks don't make people happy
        if rec.estimated_time_mins > 10 and rec.data_quality_impact == "low":
            return False

        # Default: neutral happiness impact
        return True

    def _jarvis_check(
        self,
        needs: bool,
        ready: bool,
        timing: bool,
        relationship: bool,
        happiness: bool,
        rec: CoreRecommendation,
        ctx: UserContext
    ) -> bool:
        """
        Check 6: "Would Jarvis do this for Tony?"

        This is the final wisdom check. Even if all other checks pass,
        would a truly dedicated AI companion actually do this?
        """

        # If user is vulnerable, Jarvis would only celebrate or comfort
        if ctx.is_vulnerable():
            return rec.rec_type == "celebrate_milestone"

        # If 4+ checks pass, probably yes
        passed_checks = sum([needs, ready, timing, relationship, happiness])
        if passed_checks >= 4:
            return True

        # If 3 checks pass and it's urgent, maybe
        if passed_checks >= 3 and rec.priority == "urgent":
            return True

        # If only 0-2 checks pass, probably no
        if passed_checks <= 2:
            return False

        # Edge case: 3 checks, not urgent
        # Jarvis would defer, not reject
        return False

    def _select_mode(
        self,
        ctx: UserContext,
        rec: CoreRecommendation
    ) -> BehavioralMode:
        """Select the appropriate behavioral mode"""

        # Vulnerable users get Confidant mode
        if ctx.is_vulnerable():
            return BehavioralMode.CONFIDANT

        # Celebrations trigger Servant mode (just do it efficiently)
        if rec.rec_type == "celebrate_milestone":
            return BehavioralMode.SERVANT

        # Users who like explanations get Mentor mode
        if ctx.explain_suggestions and ctx.affect_state.openness_to_change > 6:
            return BehavioralMode.MENTOR

        # High-priority system needs trigger Guardian mode (protect user from spam)
        if rec.priority == "urgent" and ctx.response_to_nudges == "negative":
            return BehavioralMode.GUARDIAN

        # Long-term goals trigger Strategist mode
        if rec.trait_path and any(goal in rec.trait_path for goal in ctx.current_goals):
            return BehavioralMode.STRATEGIST

        # Default: Servant mode (efficient execution)
        return BehavioralMode.SERVANT

    def _create_acceptance_decision(
        self,
        rec: CoreRecommendation,
        ctx: UserContext,
        mode: BehavioralMode,
        needs: bool,
        ready: bool,
        timing: bool,
        relationship: bool,
        happiness: bool
    ) -> HeadCoachDecision:
        """Create a decision accepting Core's recommendation"""

        # Choose intervention style based on mode and context
        if mode == BehavioralMode.MENTOR:
            style = InterventionStyle.GENTLE
            message = f"💡 {rec.suggested_action}\n\nWhy this helps: {rec.reasoning}"
        elif mode == BehavioralMode.SERVANT:
            style = InterventionStyle.DIRECT
            message = rec.suggested_action
        elif mode == BehavioralMode.GUARDIAN:
            style = InterventionStyle.CONTEXTUAL
            message = f"When you have a moment: {rec.suggested_action}"
        elif mode == BehavioralMode.STRATEGIST:
            style = InterventionStyle.CONTEXTUAL
            message = f"Next step toward your goal: {rec.suggested_action}"
        else:  # CONFIDANT
            style = InterventionStyle.GENTLE
            message = f"I'm here to help. {rec.suggested_action}"

        # Check if timing needs deferral
        when = "now" if timing else "later"

        decision = HeadCoachDecision(
            accept=True,
            mode=mode,
            intervention_style=style,
            action_type=rec.rec_type,
            action_description=rec.suggested_action,
            estimated_time_mins=rec.estimated_time_mins,
            decision_reasoning=self._build_reasoning(needs, ready, timing, relationship, happiness, mode),
            user_benefit=f"Improves {rec.trait_path or 'profile'} confidence",
            when_to_present=when,
            message_to_user=message
        )

        return decision

    def _create_rejection_decision(
        self,
        rec: CoreRecommendation,
        ctx: UserContext,
        mode: BehavioralMode,
        needs: bool,
        ready: bool,
        timing: bool,
        relationship: bool,
        happiness: bool
    ) -> HeadCoachDecision:
        """Create a decision rejecting Core's recommendation"""

        # Determine why we're rejecting
        reasons = []
        if not needs:
            reasons.append("user doesn't need this right now")
        if not ready:
            reasons.append("user not ready")
        if not timing:
            reasons.append("bad timing")
        if not relationship:
            reasons.append("could harm relationship")
        if not happiness:
            reasons.append("won't make user happy")

        override_reason = " AND ".join(reasons)

        decision = HeadCoachDecision(
            accept=False,
            mode=mode,
            intervention_style=InterventionStyle.SILENT,
            action_type="defer",
            action_description="Deferred by Head Coach",
            estimated_time_mins=0,
            decision_reasoning=f"Rejected: {override_reason}",
            user_benefit="Protecting user from system demands",
            overridden=True,
            override_reason=override_reason,
            when_to_present="never"
        )

        return decision

    def _build_reasoning(
        self,
        needs: bool,
        ready: bool,
        timing: bool,
        relationship: bool,
        happiness: bool,
        mode: BehavioralMode
    ) -> str:
        """Build human-readable reasoning for decision"""

        checks = []
        if needs:
            checks.append("user needs it")
        if ready:
            checks.append("user ready")
        if timing:
            checks.append("good timing")
        if relationship:
            checks.append("helps relationship")
        if happiness:
            checks.append("makes user happy")

        passed = len(checks)
        checks_str = ", ".join(checks)

        return f"{mode.value} mode: {passed}/5 checks passed ({checks_str})"


# Factory function
def create_decision_engine() -> HeadCoachDecisionEngine:
    """Create a new Head Coach decision engine"""
    return HeadCoachDecisionEngine()


__all__ = [
    "BehavioralMode",
    "InterventionStyle",
    "AffectState",
    "UserContext",
    "CoreRecommendation",
    "HeadCoachDecision",
    "HeadCoachDecisionEngine",
    "create_decision_engine"
]
