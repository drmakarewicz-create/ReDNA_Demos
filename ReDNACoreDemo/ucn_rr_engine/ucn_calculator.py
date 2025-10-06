"""
UCN (User Confidence Number) Calculator

Calculates confidence scores (0-1000) for trait assignments.

Requires "supreme level of intelligence" to assess how confident we are that the
assigned trait matches the IRL (in real life) user.

UCN Formula:
    UCN = clamp(
        sum(evidence_weight * recency_factor * corroboration_factor * source_credibility)
        * (1 - contradiction_penalty)
        * quality_multiplier,
        0, 1000
    )
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from .evidence_weighting import EvidenceWeighting, EvidenceSource, SourceType
from .decay_engine import DecayEngine
from .contradiction_handler import ContradictionHandler, ContradictionSeverity


class UCNCalculator:
    """Calculates User Confidence Numbers (UCN) for traits."""

    def __init__(
        self,
        evidence_weighting: Optional[EvidenceWeighting] = None,
        decay_engine: Optional[DecayEngine] = None,
        contradiction_handler: Optional[ContradictionHandler] = None
    ):
        """Initialize UCN calculator with component systems."""
        self.evidence_weighting = evidence_weighting or EvidenceWeighting()
        self.decay_engine = decay_engine or DecayEngine()
        self.contradiction_handler = contradiction_handler or ContradictionHandler()

    def calculate(
        self,
        trait_path: str,
        evidence_list: List[EvidenceSource],
        user_metadata: Optional[Dict[str, Any]] = None,
        current_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate UCN for a trait given evidence sources.

        Args:
            trait_path: Full trait path (e.g., "PaDNA.HairDNA.Color")
            evidence_list: List of evidence sources
            user_metadata: User metadata for decay modifiers (optional)
            current_time: Current time (defaults to now)

        Returns:
            Dictionary with ucn, components breakdown, and metadata
        """
        if current_time is None:
            current_time = datetime.now()

        # Handle no evidence case
        if not evidence_list:
            return {
                'trait_path': trait_path,
                'ucn': 0,
                'confidence_level': 'none',
                'components': {
                    'raw_weight': 0.0,
                    'contradiction_penalty': 0.0,
                    'final_weight': 0.0
                },
                'evidence_count': 0,
                'contradictions': [],
                'most_recent_evidence': None
            }

        # Get adaptive decay half-life
        decay_half_life = self.decay_engine.get_adaptive_decay_half_life(
            trait_path,
            user_metadata
        )

        # Calculate aggregate evidence weight
        raw_weight = self.evidence_weighting.calculate_aggregate_weight(
            evidence_list,
            trait_path,
            decay_half_life,
            current_time
        )

        # Detect contradictions
        contradictions = self.contradiction_handler.detect_contradictions(
            evidence_list,
            trait_path,
            decay_half_life,
            current_time
        )

        # Calculate contradiction penalty
        contradiction_penalty = 0.0
        if contradictions:
            # Use worst (highest) penalty from all contradictions
            penalties = [c.ucn_penalty for c in contradictions]
            contradiction_penalty = max(penalties) if penalties else 0.0

        # Apply contradiction penalty
        final_weight = raw_weight * (1.0 - contradiction_penalty)

        # Scale to 0-1000 range
        # We scale the raw weight which typically ranges 0-3.0 (can be higher with many sources)
        # Use sigmoid-like scaling to handle outliers gracefully
        ucn = self._scale_to_ucn(final_weight)

        # Determine confidence level
        confidence_level = self._get_confidence_level(ucn)

        # Get most recent evidence timestamp
        most_recent = max(evidence_list, key=lambda e: e.timestamp)

        # Determine consensus value (most common value among high-weight sources)
        consensus_value = self._get_consensus_value(evidence_list, trait_path, decay_half_life, current_time)

        return {
            'trait_path': trait_path,
            'ucn': ucn,
            'confidence_level': confidence_level,
            'value': consensus_value,
            'components': {
                'raw_weight': round(raw_weight, 4),
                'contradiction_penalty': round(contradiction_penalty, 4),
                'final_weight': round(final_weight, 4)
            },
            'evidence_count': len(evidence_list),
            'contradictions': [
                {
                    'severity': c.severity.value,
                    'values': c.conflicting_values,
                    'penalty': c.ucn_penalty
                }
                for c in contradictions
            ],
            'most_recent_evidence': {
                'timestamp': most_recent.timestamp.isoformat(),
                'source_type': most_recent.source_type.value,
                'value': most_recent.value
            },
            'decay_half_life_days': decay_half_life if decay_half_life != float('inf') else 'permanent'
        }

    def _scale_to_ucn(self, weight: float) -> int:
        """
        Scale aggregate weight to UCN (0-1000).

        Uses sigmoid-like scaling to handle outliers:
        - weight = 0.3 → ~300 UCN (self-report only)
        - weight = 0.7 → ~600 UCN (good evidence)
        - weight = 1.5 → ~850 UCN (strong corroboration)
        - weight = 2.5+ → ~950+ UCN (exceptional evidence)

        Formula: UCN = 1000 / (1 + e^(-2*(weight - 1)))
        This centers the sigmoid around weight=1.0
        """
        import math

        # Simple linear scaling for very low weights
        if weight <= 0:
            return 0

        # Sigmoid scaling
        # Center around weight=1.0, steepness=2
        sigmoid = 1000 / (1 + math.exp(-2 * (weight - 1.0)))

        # Clamp to [0, 1000]
        ucn = int(max(0, min(1000, sigmoid)))

        return ucn

    def _get_confidence_level(self, ucn: int) -> str:
        """
        Determine confidence level category from UCN.

        Categories:
        - very_high: 800-1000
        - high: 600-799
        - moderate: 400-599
        - low: 200-399
        - very_low: 0-199
        """
        if ucn >= 800:
            return 'very_high'
        elif ucn >= 600:
            return 'high'
        elif ucn >= 400:
            return 'moderate'
        elif ucn >= 200:
            return 'low'
        else:
            return 'very_low'

    def _get_consensus_value(
        self,
        evidence_list: List[EvidenceSource],
        trait_path: str,
        decay_half_life: float,
        current_time: datetime
    ) -> Any:
        """
        Determine consensus value from evidence sources.

        Weighted voting: value with highest aggregate weight wins.
        """
        if not evidence_list:
            return None

        # Group evidence by value
        value_weights: Dict[Any, float] = {}

        for evidence in evidence_list:
            # Calculate weight for this evidence
            num_corroborating = sum(
                1 for other in evidence_list
                if other.source_id != evidence.source_id
                and other.value == evidence.value
            )

            weight = self.evidence_weighting.calculate_evidence_weight(
                evidence,
                trait_path,
                decay_half_life,
                num_corroborating,
                current_time
            )

            # Add to value's total weight
            value = evidence.value
            if value not in value_weights:
                value_weights[value] = 0.0
            value_weights[value] += weight

        # Return value with highest weight
        if not value_weights:
            return None

        consensus_value = max(value_weights.items(), key=lambda x: x[1])[0]
        return consensus_value


def calculate_ucn(
    trait_path: str,
    evidence_list: List[EvidenceSource],
    user_metadata: Optional[Dict[str, Any]] = None,
    current_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Convenience function to calculate UCN without instantiating calculator.

    Args:
        trait_path: Full trait path
        evidence_list: List of evidence sources
        user_metadata: User metadata (optional)
        current_time: Current time (defaults to now)

    Returns:
        UCN calculation result dictionary
    """
    calculator = UCNCalculator()
    return calculator.calculate(trait_path, evidence_list, user_metadata, current_time)
