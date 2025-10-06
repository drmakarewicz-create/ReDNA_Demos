"""
Contradiction Handler

Detects and manages contradictory evidence.

Key principle: DO NOT force immediate resolution. Instead:
1. Lower UCN
2. Raise Curiosity (via lower RR)
3. Hold contradictions "in tension"
4. Flag for Head Coach to decide timing of resolution
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import yaml

from .evidence_weighting import EvidenceSource, EvidenceWeighting


class ContradictionSeverity(Enum):
    """Contradiction severity levels."""
    TRIVIAL = "trivial"      # One source weight < 0.3
    MINOR = "minor"          # Sources differ slightly, both < 0.5 weight
    MODERATE = "moderate"    # Sources differ clearly, one > 0.5 weight
    SEVERE = "severe"        # Sources strongly contradict, both > 0.5 weight


@dataclass
class Contradiction:
    """Represents a detected contradiction between evidence sources."""
    severity: ContradictionSeverity
    conflicting_values: List[Any]
    conflicting_sources: List[str]  # source_ids
    ucn_penalty: float  # 0.0-0.5
    description: str
    timestamp_range: tuple  # (earliest, latest) timestamps


class ContradictionHandler:
    """Detects and manages contradictory evidence."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize contradiction handler with thresholds."""
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "thresholds.yaml"

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.severity_config = config.get('contradiction_severity', {})
        self.evidence_weighting = EvidenceWeighting()

    def detect_contradictions(
        self,
        evidence_list: List[EvidenceSource],
        trait_path: str,
        decay_half_life: float,
        current_time: Optional[datetime] = None
    ) -> List[Contradiction]:
        """
        Detect contradictions in evidence list.

        Contradictions are detected when:
        1. Two evidence sources assign different values to the same trait
        2. The source weights are both > 0.3 (not trivial)
        3. The time delta between sources is < 2 * decay_half_life

        Args:
            evidence_list: List of evidence sources
            trait_path: Full trait path
            decay_half_life: Decay half-life for the trait
            current_time: Current time (defaults to now)

        Returns:
            List of detected contradictions
        """
        if current_time is None:
            current_time = datetime.now()

        if len(evidence_list) < 2:
            # Need at least 2 sources to contradict
            return []

        contradictions = []

        # Group evidence by value
        value_groups: Dict[Any, List[EvidenceSource]] = {}
        for evidence in evidence_list:
            value = evidence.value
            if value not in value_groups:
                value_groups[value] = []
            value_groups[value].append(evidence)

        # Need at least 2 different values to have contradiction
        if len(value_groups) < 2:
            return []

        # Calculate weights for all evidence
        evidence_weights: Dict[str, float] = {}
        for evidence in evidence_list:
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
            evidence_weights[evidence.source_id] = weight

        # Compare each pair of value groups
        values = list(value_groups.keys())
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                value_a = values[i]
                value_b = values[j]

                group_a = value_groups[value_a]
                group_b = value_groups[value_b]

                # Check if this pair constitutes a contradiction
                contradiction = self._check_pair_contradiction(
                    group_a,
                    group_b,
                    evidence_weights,
                    decay_half_life,
                    current_time
                )

                if contradiction:
                    contradictions.append(contradiction)

        return contradictions

    def _check_pair_contradiction(
        self,
        group_a: List[EvidenceSource],
        group_b: List[EvidenceSource],
        evidence_weights: Dict[str, float],
        decay_half_life: float,
        current_time: datetime
    ) -> Optional[Contradiction]:
        """
        Check if two value groups constitute a contradiction.

        Args:
            group_a: Evidence sources with value A
            group_b: Evidence sources with value B
            evidence_weights: Pre-calculated weights for all evidence
            decay_half_life: Decay half-life
            current_time: Current time

        Returns:
            Contradiction object if detected, None otherwise
        """
        # Get max weight from each group
        max_weight_a = max(evidence_weights[e.source_id] for e in group_a)
        max_weight_b = max(evidence_weights[e.source_id] for e in group_b)

        # Get timestamps
        timestamps_a = [e.timestamp for e in group_a]
        timestamps_b = [e.timestamp for e in group_b]
        all_timestamps = timestamps_a + timestamps_b

        earliest = min(all_timestamps)
        latest = max(all_timestamps)
        time_delta_days = (latest - earliest).total_seconds() / 86400

        # Condition 1: Both weights > 0.3 (not trivial)
        if max_weight_a < 0.3 or max_weight_b < 0.3:
            return None

        # Condition 2: Time delta < 2 * decay_half_life (sources are contemporaneous)
        if decay_half_life != float('inf'):
            if time_delta_days > 2 * decay_half_life:
                # Sources too far apart - likely legitimate change, not contradiction
                return None

        # Determine severity
        severity = self._determine_severity(max_weight_a, max_weight_b)

        # Get penalty
        penalty = self._get_penalty(severity)

        # Build description
        value_a = group_a[0].value
        value_b = group_b[0].value
        description = f"Conflicting values: '{value_a}' (weight {max_weight_a:.2f}) vs '{value_b}' (weight {max_weight_b:.2f})"

        # Get source IDs
        source_ids = [e.source_id for e in group_a + group_b]

        return Contradiction(
            severity=severity,
            conflicting_values=[value_a, value_b],
            conflicting_sources=source_ids,
            ucn_penalty=penalty,
            description=description,
            timestamp_range=(earliest, latest)
        )

    def _determine_severity(self, weight_a: float, weight_b: float) -> ContradictionSeverity:
        """
        Determine contradiction severity based on evidence weights.

        Rules:
        - Trivial: One weight < 0.3
        - Minor: Both < 0.5
        - Moderate: One > 0.5
        - Severe: Both > 0.5
        """
        if weight_a < 0.3 or weight_b < 0.3:
            return ContradictionSeverity.TRIVIAL

        if weight_a < 0.5 and weight_b < 0.5:
            return ContradictionSeverity.MINOR

        if weight_a > 0.5 and weight_b > 0.5:
            return ContradictionSeverity.SEVERE

        # One > 0.5, other < 0.5
        return ContradictionSeverity.MODERATE

    def _get_penalty(self, severity: ContradictionSeverity) -> float:
        """Get UCN penalty for contradiction severity."""
        severity_data = self.severity_config.get(severity.value, {})
        return severity_data.get('ucn_penalty', 0.2)

    def hold_in_tension(
        self,
        trait_path: str,
        contradictions: List[Contradiction],
        consensus_value: Any,
        ucn: int
    ) -> Dict[str, Any]:
        """
        Create a "held in tension" representation of contradictory trait.

        Returns a structure that stores both the consensus value and contradictions,
        allowing Head Coach to decide when to resolve.

        Args:
            trait_path: Full trait path
            contradictions: Detected contradictions
            consensus_value: Consensus value (highest weight)
            ucn: Calculated UCN (already includes contradiction penalty)

        Returns:
            Dictionary representing trait held in tension
        """
        return {
            'trait_path': trait_path,
            'value': consensus_value,  # Most recent or highest-weight source
            'ucn': ucn,  # Already reduced due to contradiction
            'status': 'in_tension',
            'contradictions': [
                {
                    'severity': c.severity.value,
                    'conflicting_values': c.conflicting_values,
                    'conflicting_sources': c.conflicting_sources,
                    'ucn_penalty': c.ucn_penalty,
                    'description': c.description,
                    'timestamp_range': [
                        c.timestamp_range[0].isoformat(),
                        c.timestamp_range[1].isoformat()
                    ]
                }
                for c in contradictions
            ],
            'resolution_strategy': 'await_head_coach_decision',
            'flagged_for_head_coach': True,
            'head_coach_priority': self._calculate_priority(contradictions)
        }

    def _calculate_priority(self, contradictions: List[Contradiction]) -> str:
        """
        Calculate Head Coach priority for contradiction resolution.

        Priority levels:
        - critical: Severe contradictions
        - high: Moderate contradictions
        - medium: Minor contradictions
        - low: Trivial contradictions
        """
        if not contradictions:
            return 'low'

        # Use highest severity
        severities = [c.severity for c in contradictions]

        if ContradictionSeverity.SEVERE in severities:
            return 'critical'
        elif ContradictionSeverity.MODERATE in severities:
            return 'high'
        elif ContradictionSeverity.MINOR in severities:
            return 'medium'
        else:
            return 'low'
