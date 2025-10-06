"""
Curiosity Engine

Derives Curiosity score from Refinement Rank (RR).

Formula: Curiosity = 100 - RR

Key properties:
- Larger Curiosity number = more motivation to refine
- Normalizes across different DNA types
- System-facing only (users never see this)
- Drives Head Coach planning and prioritization
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass


@dataclass
class CuriositySignal:
    """Represents a curiosity signal for a trait or trait group."""
    trait_path: str
    ucn: int
    curiosity_score: float  # Derived from UCN
    priority: str  # 'critical', 'high', 'medium', 'low'
    reason: str
    suggested_action: str


class CuriosityEngine:
    """Derives and manages curiosity signals for profile refinement."""

    def __init__(self):
        """Initialize curiosity engine."""
        pass

    def calculate_overall_curiosity(self, rr: float) -> float:
        """
        Calculate overall curiosity from RR.

        Formula: Curiosity = 100 - RR

        Args:
            rr: Refinement Rank (0-100 percentile)

        Returns:
            Curiosity score (0-100, higher = more curious/motivated)
        """
        if rr is None:
            # No RR available (insufficient traits)
            return 100.0  # Maximum curiosity

        curiosity = 100.0 - rr
        return round(curiosity, 2)

    def get_curiosity_level(self, curiosity: float) -> str:
        """
        Determine curiosity level category.

        Levels:
        - urgent: 50-100 (RR 0-50)
        - high: 30-49 (RR 51-70)
        - moderate: 15-29 (RR 71-85)
        - low: 2-14 (RR 86-98)
        - minimal: 0-1 (RR 99-100)

        Args:
            curiosity: Curiosity score (0-100)

        Returns:
            Curiosity level category
        """
        if curiosity >= 50:
            return 'urgent'
        elif curiosity >= 30:
            return 'high'
        elif curiosity >= 15:
            return 'moderate'
        elif curiosity >= 2:
            return 'low'
        else:
            return 'minimal'

    def get_trait_curiosity_signals(
        self,
        user_traits: Dict[str, int],
        include_top_n: int = 20
    ) -> List[CuriositySignal]:
        """
        Generate curiosity signals for individual traits.

        Identifies high-curiosity traits (low UCN) that should be prioritized for refinement.

        Args:
            user_traits: Dictionary of {trait_path: ucn}
            include_top_n: Number of top curiosity traits to return

        Returns:
            List of CuriositySignal objects, sorted by priority
        """
        signals = []

        for trait_path, ucn in user_traits.items():
            # Calculate trait-level curiosity (inverse of UCN, scaled to 0-100)
            trait_curiosity = 100.0 - (ucn / 10.0)  # UCN 0-1000 → Curiosity 100-0

            # Determine priority
            priority = self._get_trait_priority(ucn, trait_curiosity)

            # Determine reason and suggested action
            reason, suggested_action = self._get_refinement_recommendation(
                trait_path,
                ucn,
                trait_curiosity
            )

            signals.append(CuriositySignal(
                trait_path=trait_path,
                ucn=ucn,
                curiosity_score=round(trait_curiosity, 2),
                priority=priority,
                reason=reason,
                suggested_action=suggested_action
            ))

        # Sort by curiosity score (highest first)
        signals.sort(key=lambda s: s.curiosity_score, reverse=True)

        # Return top N
        return signals[:include_top_n]

    def _get_trait_priority(self, ucn: int, curiosity: float) -> str:
        """Determine priority level for trait refinement."""
        if ucn < 200:
            return 'critical'  # Very low confidence
        elif ucn < 400:
            return 'high'  # Low confidence
        elif ucn < 600:
            return 'medium'  # Moderate confidence
        else:
            return 'low'  # High confidence, low priority

    def _get_refinement_recommendation(
        self,
        trait_path: str,
        ucn: int,
        curiosity: float
    ) -> Tuple[str, str]:
        """
        Generate refinement recommendation for a trait.

        Returns:
            (reason, suggested_action) tuple
        """
        # Extract DNA type from trait path
        dna_type = trait_path.split('.')[0] if '.' in trait_path else 'Unknown'

        # Determine reason and action based on UCN level
        if ucn < 200:
            reason = "Very low confidence - needs strong evidence"
            if dna_type == 'PaDNA':
                suggested_action = "Request photo upload or webcam capture"
            elif dna_type == 'PsyDNA':
                suggested_action = "Engage in conversation or structured assessment"
            elif dna_type == 'HealthDNA':
                suggested_action = "Request device sensor data or self-report"
            else:
                suggested_action = "Gather direct evidence from user"

        elif ucn < 400:
            reason = "Low confidence - needs corroboration"
            suggested_action = "Seek additional evidence source to corroborate"

        elif ucn < 600:
            reason = "Moderate confidence - could be stronger"
            suggested_action = "Opportunistically gather supporting evidence"

        elif ucn < 800:
            reason = "High confidence - maintenance mode"
            suggested_action = "Periodically refresh to prevent staleness"

        else:
            reason = "Very high confidence - well-established"
            suggested_action = "Maintain through passive observation"

        return reason, suggested_action

    def get_curiosity_budget_allocation(
        self,
        overall_curiosity: float,
        trait_signals: List[CuriositySignal]
    ) -> Dict[str, Any]:
        """
        Generate curiosity budget allocation for Head Coach.

        NOTE: There is NO fixed budget - this is dynamic guidance.
        Head Coach balances refinement actions based on:
        - Impact on RR (high-impact traits favored)
        - Ease of resolution (quick wins for momentum)
        - Contradiction severity (resolve severe contradictions first)
        - Staleness (refresh very old data)
        - User engagement (consider user's current focus)

        Args:
            overall_curiosity: Overall curiosity score (0-100)
            trait_signals: List of trait-level curiosity signals

        Returns:
            Dictionary with allocation guidance
        """
        # Categorize signals by priority
        critical_traits = [s for s in trait_signals if s.priority == 'critical']
        high_traits = [s for s in trait_signals if s.priority == 'high']
        medium_traits = [s for s in trait_signals if s.priority == 'medium']
        low_traits = [s for s in trait_signals if s.priority == 'low']

        # Determine overall strategy based on curiosity level
        curiosity_level = self.get_curiosity_level(overall_curiosity)

        if curiosity_level == 'urgent':
            strategy = "Aggressive refinement - profile significantly incomplete"
            focus = "Prioritize high-impact traits and quick wins"
            max_concurrent_actions = 5

        elif curiosity_level == 'high':
            strategy = "Active refinement - many opportunities"
            focus = "Balance high-impact and easy wins"
            max_concurrent_actions = 4

        elif curiosity_level == 'moderate':
            strategy = "Selective refinement - targeted improvements"
            focus = "Focus on contradictions and stale traits"
            max_concurrent_actions = 3

        elif curiosity_level == 'low':
            strategy = "Maintenance mode - minor gaps"
            focus = "Opportunistic refinement and refresh"
            max_concurrent_actions = 2

        else:  # minimal
            strategy = "Minimal refinement - profile exceptionally refined"
            focus = "Periodic refresh only"
            max_concurrent_actions = 1

        return {
            'overall_curiosity': overall_curiosity,
            'curiosity_level': curiosity_level,
            'strategy': strategy,
            'focus': focus,
            'max_concurrent_actions': max_concurrent_actions,
            'trait_breakdown': {
                'critical': len(critical_traits),
                'high': len(high_traits),
                'medium': len(medium_traits),
                'low': len(low_traits)
            },
            'top_priority_traits': [
                {
                    'trait_path': s.trait_path,
                    'ucn': s.ucn,
                    'priority': s.priority,
                    'suggested_action': s.suggested_action
                }
                for s in trait_signals[:10]  # Top 10
            ],
            'note': "Budget is dynamic - Head Coach balances user well-being with system improvement"
        }

    def get_curiosity_summary(
        self,
        rr: float,
        user_traits: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Get comprehensive curiosity summary for a user.

        Args:
            rr: Refinement Rank
            user_traits: Dictionary of {trait_path: ucn}

        Returns:
            Complete curiosity analysis
        """
        overall_curiosity = self.calculate_overall_curiosity(rr)
        trait_signals = self.get_trait_curiosity_signals(user_traits, include_top_n=20)
        budget_allocation = self.get_curiosity_budget_allocation(overall_curiosity, trait_signals)

        return {
            'overall_curiosity': overall_curiosity,
            'rr': rr,
            'curiosity_level': self.get_curiosity_level(overall_curiosity),
            'trait_count': len(user_traits),
            'avg_ucn': sum(user_traits.values()) / len(user_traits) if user_traits else 0,
            'trait_signals': [
                {
                    'trait_path': s.trait_path,
                    'ucn': s.ucn,
                    'curiosity_score': s.curiosity_score,
                    'priority': s.priority,
                    'reason': s.reason,
                    'suggested_action': s.suggested_action
                }
                for s in trait_signals
            ],
            'budget_allocation': budget_allocation
        }


def calculate_curiosity(rr: float) -> float:
    """
    Convenience function to calculate curiosity without instantiating engine.

    Formula: Curiosity = 100 - RR

    Args:
        rr: Refinement Rank (0-100 percentile)

    Returns:
        Curiosity score (0-100)
    """
    engine = CuriosityEngine()
    return engine.calculate_overall_curiosity(rr)
