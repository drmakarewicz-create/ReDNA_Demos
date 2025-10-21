"""
UCN/RR Service - AI-Driven Statistical Validation Layer

The UCN/RR layer is the statistical analysis engine that:
1. Receives proposals from Head Coach (observations + inferences)
2. Assigns UCN (confidence) based on evidence quality and consistency
3. Assigns RR (rarity) based on population-wide distributions
4. Detects correlations between traits across the dataset
5. Uses AI-driven statistical learning (not just dumb math)
6. Bootstraps with synthetic population data at startup
7. Evolves over time as real population data accumulates
8. NOT the final authority - provides statistical truth and insights

This layer validates "how confident should we be?" not "what should we infer?"

---
Phase 10: ReDNA Hierarchy (Replicated Digital Neural Approximation)
---

ReDNA (root) = The complete digital organism
├── RelDNA (tier-1) = Relational DNA - Social patterns
├── PaDNA (tier-1) = Physical Attributes DNA - Physical traits
├── BehDNA (tier-1) = Behavioral DNA - Behavior patterns
├── CogDNA (tier-1) = Cognitive DNA - Thinking patterns
└── EmoDNA (tier-1) = Emotional DNA - Emotional patterns

IMPORTANT: ReDNA is the organism-level entity. RelDNA is ONE of several top-tier subsystems.

---
Phase 9: AI-First Hierarchical UCN Propagation Guidance
---

When assigning or updating a parent DNA's UCN, the AI reasoning layer should:

1. READ child trait UCNs as strong priors:
   - If all child traits have high UCN (e.g., >750), consider the parent DNA highly confident.
   - If child traits have mixed UCN, consider what that means for the parent category.
   - If no child traits exist yet, start with a low parent UCN until evidence emerges.

2. WEIGH parent-level evidence separately:
   - Direct observations about the parent category should be considered.
   - Recency of child evidence matters (older child data = lower parent confidence).
   - Contradictions between children should lower parent UCN.

3. USE DISCRETION over formulas:
   - Do NOT compute parent UCN as mean(child UCNs).
   - Instead, reason about what the child UCNs imply about the parent.
   - Example: If PaDNA.HairDNA.Color has UCN=850 and PaDNA.HairDNA.Texture has UCN=800,
     then PaDNA.HairDNA might have UCN=820-850 (high confidence in hair traits overall).

4. EXPLAIN divergences via Why-Cards:
   - If parent UCN diverges significantly from child consensus, create a Why-Card explaining:
     * What child UCNs were considered?
     * What parent-level signals were weighed?
     * Why does the parent UCN differ from simple averaging?
     * What new data would increase/decrease confidence?

5. NEVER expose UCN as RR:
   - UCN is 0-1000, internal only.
   - RR is 0-100, user-facing percentile.
   - Always use rr_to_percentile() adapter at egress.

Soft scaffolding (not hard constraints):
- Parent UCN should generally be within ±200 points of child avg (0-1000 scale).
- Large divergence (>200 points) triggers Why-Card generation.
- No parent UCN assigned if no child data and no direct parent evidence.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from . import rr_engine

logger = logging.getLogger(__name__)

# Try to import LLM client for AI-driven correlation detection
try:
    from llama3_client import chat as llama_chat
    LLM_AVAILABLE = True
except ImportError:
    llama_chat = None
    LLM_AVAILABLE = False


@dataclass
class UCNRRAssessment:
    """
    Statistical assessment from UCN/RR layer.
    This is validation/confidence scoring, not inference.
    """
    trait_path: str
    value: Any
    ucn: float  # 0-1000 Universal Confidence Number
    rr: float   # 0-1000 Rarity score (LEGACY - Phase 9: Should be 0-100 percentile)
    curiosity: float  # 100 - rr for 0-100 scale (LEGACY: was 1000 - rr)
    correlations: List[Dict[str, Any]] = field(default_factory=list)
    confidence_reasoning: str = ""
    rarity_reasoning: str = ""
    population_percentile: Optional[float] = None


@dataclass
class UCNRRResult:
    """Complete result from UCN/RR processing"""
    assessments: List[UCNRRAssessment] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    llm_available: bool = False
    synthetic_population_used: bool = False


# Synthetic population data for bootstrapping
# This allows AI-driven correlation detection from day one
SYNTHETIC_POPULATION_CONFIG = {
    "total_profiles": 10000,  # Synthetic population size
    "correlation_rules": {
        # These are scientifically-grounded priors that AI can learn from
        ("PaDNA.HairDNA.Color", "Red"): {
            "implies": [
                ("PaDNA.SkinDNA.Tone", "Fair", 0.88),
                ("PaDNA.SkinDNA.Freckles", "Present", 0.82),
                ("PaDNA.SkinDNA.SunSensitivity", "High", 0.85),
            ],
            "population_frequency": 0.02  # 2% of population
        },
        ("PaDNA.EyeDNA.Color", "Blue"): {
            "implies": [
                ("PaDNA.SkinDNA.Tone", "Fair", 0.65),
                ("PaDNA.HairDNA.Color", "Blonde", 0.45),
            ],
            "population_frequency": 0.17  # 17% of population
        },
        ("PaDNA.EyeDNA.Color", "Green"): {
            "implies": [
                ("PaDNA.HairDNA.Color", "Red", 0.15),
                ("PaDNA.SkinDNA.Tone", "Fair", 0.60),
            ],
            "population_frequency": 0.02  # 2% of population (rare)
        },
        ("PaDNA.HairDNA.Color", "Black"): {
            "implies": [
                ("PaDNA.EyeDNA.Color", "Brown", 0.85),
                ("PaDNA.SkinDNA.Tone", "Medium", 0.60),
            ],
            "population_frequency": 0.75  # 75% of population globally
        },
    }
}


def assess_observations_and_inferences(
    direct_observations: List[Any],  # TraitObservation from head_coach
    proposed_inferences: List[Any],  # ProposedInference from head_coach
    current_profile: Optional[Dict[str, Any]] = None,
    user_id: str = "unknown",
    baselines: Optional[Dict[str, Any]] = None
) -> UCNRRResult:
    """
    Assess confidence (UCN) and rarity (RR) for all proposed traits.

    This is the main UCN/RR entry point. It receives proposals from Head Coach
    and validates them statistically.

    Args:
        direct_observations: Observations from coaches (e.g., photo analysis)
        proposed_inferences: Inferences from Head Coach AI
        current_profile: User's existing profile
        user_id: User ID for logging
        baselines: Population baselines for RR calculation

    Returns:
        UCNRRResult with statistical assessments
    """
    result = UCNRRResult(
        llm_available=LLM_AVAILABLE,
        synthetic_population_used=baselines is None
    )

    if baselines is None:
        baselines = _generate_synthetic_baselines()
        result.synthetic_population_used = True

    # Process direct observations first (high confidence)
    for obs in direct_observations:
        assessment = _assess_observation(obs, baselines)
        result.assessments.append(assessment)

    # Process proposed inferences (validate confidence)
    for inference in proposed_inferences:
        assessment = _assess_inference(inference, direct_observations, baselines, current_profile)
        result.assessments.append(assessment)

    # AI-driven correlation detection (if enabled)
    if LLM_AVAILABLE and len(result.assessments) > 1:
        try:
            _enhance_with_ai_correlations(result.assessments, user_id)
        except Exception as exc:
            logger.error(f"[UCNRR:{user_id}] AI correlation detection failed: {exc}")
            result.warnings.append(f"AI correlation detection failed: {exc}")

    return result


def _assess_observation(obs: Any, baselines: Dict[str, Any]) -> UCNRRAssessment:
    """
    Assess UCN/RR for a direct observation (e.g., from photo).

    Direct observations get high confidence because they're measured, not inferred.
    """
    # Extract observation data
    trait_path = obs.trait_path
    value = obs.value
    confidence = obs.confidence  # 0.0-1.0 from Head Coach

    # Calculate UCN based on source quality
    source = obs.source
    ucn = _calculate_ucn_from_source(source, confidence)

    # Calculate RR from population baselines (returns 0-1000 legacy scale)
    rr = rr_engine.compute_rr(trait_path, value, ucn, baselines)

    # LEGACY curiosity formula: 1000 - RR (Phase 9 TODO: Migrate to 100 - RR percentile)
    # This service stores rr_score (0-1000) which gets normalized at egress to rr (0-100)
    curiosity = 1000.0 - rr

    assessment = UCNRRAssessment(
        trait_path=trait_path,
        value=value,
        ucn=ucn,
        rr=rr,
        curiosity=curiosity,
        confidence_reasoning=f"Direct observation from {source} with {confidence:.0%} confidence",
        rarity_reasoning=f"Population frequency determines RR={rr:.0f}"
    )

    return assessment


def _assess_inference(
    inference: Any,
    observations: List[Any],
    baselines: Dict[str, Any],
    current_profile: Optional[Dict[str, Any]]
) -> UCNRRAssessment:
    """
    Assess UCN/RR for a proposed inference from Head Coach.

    Inferred traits get validated against:
    1. Head Coach's confidence
    2. Quality of source observations
    3. Known correlations in population data
    4. Consistency with existing profile
    """
    trait_path = inference.trait_path
    value = inference.value
    head_coach_confidence = inference.confidence  # 0.0-1.0

    # Start with Head Coach's confidence
    ucn = head_coach_confidence * 1000.0

    # Adjust based on source observation quality
    source_paths = set(inference.source_observations)
    source_confidences = [
        obs.confidence for obs in observations
        if obs.trait_path in source_paths
    ]

    if source_confidences:
        avg_source_confidence = sum(source_confidences) / len(source_confidences)
        # Weight: 60% Head Coach confidence, 40% source quality
        ucn = (0.6 * head_coach_confidence + 0.4 * avg_source_confidence) * 1000.0
    else:
        # No source observations found - reduce confidence
        ucn = ucn * 0.8

    # Check against known correlations in synthetic population
    correlation_boost = _check_correlations(trait_path, value, observations, baselines)
    ucn = min(1000.0, ucn + correlation_boost)

    # Calculate RR (returns 0-1000 legacy scale)
    rr = rr_engine.compute_rr(trait_path, value, ucn, baselines)

    # LEGACY curiosity: 1000 - RR (Phase 9 TODO: Migrate to 100 - RR percentile)
    # This service stores rr_score (0-1000) which gets normalized at egress to rr (0-100)
    curiosity = 1000.0 - rr

    assessment = UCNRRAssessment(
        trait_path=trait_path,
        value=value,
        ucn=ucn,
        rr=rr,
        curiosity=curiosity,
        confidence_reasoning=f"Inferred by Head Coach ({head_coach_confidence:.0%}), validated against source observations",
        rarity_reasoning=f"Population frequency analysis: RR={rr:.0f}"
    )

    return assessment


def _calculate_ucn_from_source(source: str, base_confidence: float) -> float:
    """
    Calculate UCN based on source type and base confidence.

    Different sources have different reliability:
    - Photo analysis: High (but depends on image quality)
    - User statement: Very high (user knows themselves)
    - Questionnaire: High
    - Third-party data: Variable
    """
    source_multipliers = {
        "photo_analysis": 0.90,
        "user_statement": 0.95,
        "questionnaire": 0.90,
        "manual_entry": 0.95,
        "third_party": 0.75,
        "canonical": 1.0
    }

    multiplier = source_multipliers.get(source, 0.80)
    ucn = base_confidence * multiplier * 1000.0

    return min(1000.0, max(0.0, ucn))


def _check_correlations(
    trait_path: str,
    value: Any,
    observations: List[Any],
    baselines: Dict[str, Any]
) -> float:
    """
    Check if this inference aligns with known correlations.

    Returns UCN boost (0-100) if correlation is strong.
    """
    boost = 0.0

    # Check synthetic population correlations
    for obs in observations:
        correlation_key = (obs.trait_path, obs.value)
        if correlation_key in SYNTHETIC_POPULATION_CONFIG["correlation_rules"]:
            implications = SYNTHETIC_POPULATION_CONFIG["correlation_rules"][correlation_key]["implies"]

            for implied_path, implied_value, correlation_strength in implications:
                if implied_path == trait_path and implied_value == value:
                    # Found a known correlation!
                    boost += correlation_strength * 100.0  # Convert to 0-100 UCN boost
                    logger.debug(f"Correlation boost: {obs.trait_path}={obs.value} → {trait_path}={value} (+{boost:.0f} UCN)")

    return min(100.0, boost)


def _generate_synthetic_baselines() -> Dict[str, Any]:
    """
    Generate synthetic population baselines for RR calculation.

    This bootstraps the system with scientifically-grounded population frequencies
    so UCN/RR can be AI-driven from day one without real user data.

    In production, this would be replaced by learned baselines from real population data.
    """
    baselines = {
        "version": "synthetic_v1",
        "population_size": SYNTHETIC_POPULATION_CONFIG["total_profiles"],
        "trait_frequencies": {}
    }

    for (trait_path, value), config in SYNTHETIC_POPULATION_CONFIG["correlation_rules"].items():
        freq = config["population_frequency"]

        if trait_path not in baselines["trait_frequencies"]:
            baselines["trait_frequencies"][trait_path] = {}

        baselines["trait_frequencies"][trait_path][value] = {
            "count": int(freq * SYNTHETIC_POPULATION_CONFIG["total_profiles"]),
            "frequency": freq,
            "percentile": 1.0 - freq  # Rare = high percentile
        }

    return baselines


def _enhance_with_ai_correlations(
    assessments: List[UCNRRAssessment],
    user_id: str
) -> None:
    """
    Use AI to detect non-obvious correlations between traits.

    This is future enhancement - currently a placeholder.
    When real population data accumulates, this would use ML to learn patterns.
    """
    # TODO: Implement ML-based correlation detection
    # For now, rely on synthetic correlation rules
    pass


def convert_to_core_format(assessment: UCNRRAssessment, timestamp: str) -> Dict[str, Any]:
    """
    Convert UCNRRAssessment to format expected by Core.

    This prepares data for Core's holistic synthesis.
    """
    return {
        "value": assessment.value,
        "value_type": _infer_value_type(assessment.value),
        "ucn": assessment.ucn,
        "rr": assessment.rr,
        "curiosity": assessment.curiosity,
        "reasons": [
            f"ucn:{assessment.confidence_reasoning}",
            f"rr:{assessment.rarity_reasoning}"
        ],
        "provenance": {
            "source": "ucnrr",
            "step": "ucnrr-validation",
            "timestamp": timestamp
        },
        "notes": {
            "summary": "Validated by UCN/RR statistical engine",
            "correlations": assessment.correlations
        },
        "updated_ts": timestamp
    }


def _infer_value_type(value: Any) -> str:
    """Infer value type for Core storage"""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    return "string"


__all__ = [
    "UCNRRAssessment",
    "UCNRRResult",
    "assess_observations_and_inferences",
    "convert_to_core_format"
]
