"""
Evidence Weighting System

Weighs evidence sources based on credibility, recency, corroboration, and quality.
"""

import math
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import yaml


class SourceType(Enum):
    """Evidence source types with base credibility weights."""
    SELF_REPORT_TEXT = "self_report_text"
    SELF_REPORT_STRUCTURED = "self_report_structured"
    PHOTO_SINGLE = "photo_single"
    PHOTO_SERIES = "photo_series"
    THIRD_PARTY_ATTESTATION = "third_party_attestation"
    WEBCAM_VIDEO = "webcam_video"
    BEHAVIORAL_OBSERVATION = "behavioral_observation"
    DEVICE_SENSOR = "device_sensor"
    INFERENCE_SINGLE = "inference_single"
    INFERENCE_MULTIPLE = "inference_multiple"
    AI_ANALYSIS = "ai_analysis"
    FAILED_ATTEMPT = "failed_attempt"


class EvidenceSource:
    """Represents a single piece of evidence for a trait."""

    def __init__(
        self,
        source_type: SourceType,
        value: Any,
        timestamp: datetime,
        source_id: str,
        quality_metadata: Optional[Dict[str, Any]] = None,
        corroboration_sources: Optional[List[str]] = None,
    ):
        self.source_type = source_type
        self.value = value
        self.timestamp = timestamp
        self.source_id = source_id
        self.quality_metadata = quality_metadata or {}
        self.corroboration_sources = corroboration_sources or []


class EvidenceWeighting:
    """Calculates evidence weights based on source type, recency, corroboration, and quality."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize evidence weighting system with configuration."""
        if config_path is None:
            config_path = Path(__file__).parent / "config" / "evidence_weights.yaml"

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.evidence_sources = self.config['evidence_sources']
        self.quality_multipliers = self.config['quality_multipliers']
        self.source_credibility_config = self.config['source_credibility']

        # Source credibility learning (starts at default, adjusts over time)
        self.source_credibility: Dict[str, float] = {}

    def get_base_weight(self, source_type: SourceType, dna_type: Optional[str] = None) -> float:
        """Get base weight for evidence source type."""
        source_config = self.evidence_sources.get(source_type.value, {})
        base_weight = source_config.get('base_weight', 0.3)

        # Check for DNA-specific volatility adjustments
        volatility = source_config.get('volatility')
        if isinstance(volatility, dict) and dna_type:
            # Extract top-level DNA type (e.g., "PaDNA" from "PaDNA.HairDNA.Color")
            top_dna = dna_type.split('.')[0] if '.' in dna_type else dna_type
            # Volatility affects weight (but this is primarily for decay, so base weight stays)
            # Future: Could adjust base_weight based on DNA-specific volatility
            pass

        return base_weight

    def get_corroboration_boost(
        self,
        source_type: SourceType,
        num_corroborating_sources: int
    ) -> float:
        """Calculate boost from corroborating evidence sources."""
        source_config = self.evidence_sources.get(source_type.value, {})
        boost_per_source = source_config.get('corroboration_boost', 0.1)
        return boost_per_source * num_corroborating_sources

    def get_quality_multiplier(self, evidence: EvidenceSource) -> float:
        """Calculate quality multiplier based on evidence metadata."""
        multiplier = 1.0
        metadata = evidence.quality_metadata

        # Photo quality multipliers
        if evidence.source_type in [SourceType.PHOTO_SINGLE, SourceType.PHOTO_SERIES]:
            # Resolution
            resolution = metadata.get('resolution', 'medium')
            if 'photo_resolution' in self.quality_multipliers:
                multiplier *= self.quality_multipliers['photo_resolution'].get(resolution, 1.0)

            # Lighting
            lighting = metadata.get('lighting', 'fair')
            if 'photo_lighting' in self.quality_multipliers:
                multiplier *= self.quality_multipliers['photo_lighting'].get(lighting, 1.0)

            # Angle
            angle = metadata.get('angle', 'frontal')
            if 'photo_angle' in self.quality_multipliers:
                multiplier *= self.quality_multipliers['photo_angle'].get(angle, 1.0)

        # Form completeness
        if evidence.source_type == SourceType.SELF_REPORT_STRUCTURED:
            completeness = metadata.get('completeness', 'complete')
            if 'form_completeness' in self.quality_multipliers:
                multiplier *= self.quality_multipliers['form_completeness'].get(completeness, 1.0)

        # Third-party relationship
        if evidence.source_type == SourceType.THIRD_PARTY_ATTESTATION:
            relationship = metadata.get('relationship', 'friend')
            if 'third_party_relationship' in self.quality_multipliers:
                multiplier *= self.quality_multipliers['third_party_relationship'].get(relationship, 1.0)

        return multiplier

    def get_source_credibility(self, source_id: str) -> float:
        """Get credibility score for a specific source (learned over time)."""
        if source_id not in self.source_credibility:
            # Default credibility for new sources
            return self.source_credibility_config['default']

        # Return learned credibility (clamped to range)
        credibility = self.source_credibility[source_id]
        min_cred, max_cred = self.source_credibility_config['range']
        return max(min_cred, min(max_cred, credibility))

    def update_source_credibility(
        self,
        source_id: str,
        was_accurate: bool
    ) -> None:
        """Update source credibility based on accuracy feedback."""
        current_credibility = self.get_source_credibility(source_id)
        learning_rate = self.source_credibility_config['learning_rate']

        if was_accurate:
            # Boost credibility
            new_credibility = current_credibility + learning_rate * (1.5 - current_credibility)
        else:
            # Reduce credibility
            new_credibility = current_credibility - learning_rate * current_credibility

        # Clamp to range
        min_cred, max_cred = self.source_credibility_config['range']
        self.source_credibility[source_id] = max(min_cred, min(max_cred, new_credibility))

    def calculate_recency_factor(
        self,
        evidence: EvidenceSource,
        decay_half_life_days: float,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate recency factor using exponential decay.

        Formula: e^(-age_in_days / decay_half_life)

        Args:
            evidence: Evidence source
            decay_half_life_days: Half-life for confidence decay (in days)
            current_time: Current time (defaults to now)

        Returns:
            Recency factor (0.0-1.0)
        """
        if current_time is None:
            current_time = datetime.now()

        # Handle permanent traits (no decay)
        if decay_half_life_days == float('inf') or decay_half_life_days <= 0:
            return 1.0

        age_in_days = (current_time - evidence.timestamp).total_seconds() / 86400
        recency_factor = math.exp(-age_in_days / decay_half_life_days)

        return max(0.0, min(1.0, recency_factor))

    def calculate_evidence_weight(
        self,
        evidence: EvidenceSource,
        trait_path: str,
        decay_half_life_days: float,
        num_corroborating_sources: int = 0,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate total weight for a piece of evidence.

        Weight = base_weight * recency_factor * (1 + corroboration_boost) * quality_multiplier * source_credibility

        Args:
            evidence: Evidence source
            trait_path: Full path to trait (e.g., "PaDNA.HairDNA.Color")
            decay_half_life_days: Half-life for confidence decay
            num_corroborating_sources: Number of corroborating evidence sources
            current_time: Current time (defaults to now)

        Returns:
            Total evidence weight (can be negative for failed attempts)
        """
        # Extract DNA type from trait path
        dna_type = trait_path.split('.')[0] if '.' in trait_path else None

        # Base weight
        base_weight = self.get_base_weight(evidence.source_type, dna_type)

        # Recency factor (exponential decay)
        recency_factor = self.calculate_recency_factor(
            evidence,
            decay_half_life_days,
            current_time
        )

        # Corroboration boost
        corroboration_boost = self.get_corroboration_boost(
            evidence.source_type,
            num_corroborating_sources
        )
        corroboration_factor = 1.0 + corroboration_boost

        # Quality multiplier
        quality_multiplier = self.get_quality_multiplier(evidence)

        # Source credibility (learned)
        source_credibility = self.get_source_credibility(evidence.source_id)

        # Total weight
        total_weight = (
            base_weight
            * recency_factor
            * corroboration_factor
            * quality_multiplier
            * source_credibility
        )

        return total_weight

    def calculate_aggregate_weight(
        self,
        evidence_list: List[EvidenceSource],
        trait_path: str,
        decay_half_life_days: float,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate aggregate weight from multiple evidence sources.

        Automatically detects corroboration between sources.

        Args:
            evidence_list: List of evidence sources
            trait_path: Full path to trait
            decay_half_life_days: Half-life for confidence decay
            current_time: Current time (defaults to now)

        Returns:
            Aggregate weight (sum of all evidence weights)
        """
        if not evidence_list:
            return 0.0

        total_weight = 0.0

        for evidence in evidence_list:
            # Count corroborating sources (same value, different source)
            num_corroborating = sum(
                1 for other in evidence_list
                if other.source_id != evidence.source_id
                and other.value == evidence.value
            )

            weight = self.calculate_evidence_weight(
                evidence,
                trait_path,
                decay_half_life_days,
                num_corroborating,
                current_time
            )

            total_weight += weight

        return total_weight
