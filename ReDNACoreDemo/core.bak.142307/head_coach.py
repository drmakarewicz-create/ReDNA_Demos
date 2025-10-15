"""
Head Coach / Explorer Service

The Head Coach is the first-pass ingestion and shaping layer that:
1. Accepts ANY input format (structured JSON, plain text, unstructured media, novel future data)
2. Uses AI to normalize messy observations into consistent, structured format
3. Performs initial AI inference (e.g., "red hair → likely freckles")
4. Calculates curiosity and drives exploration requests
5. Never finalizes traits - only prepares and proposes data

This is the universal adapter layer that makes the system coach-agnostic.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Try to import LLM client
try:
    from llama3_client import chat as llama_chat
    LLM_AVAILABLE = True
except ImportError:
    llama_chat = None
    LLM_AVAILABLE = False

# Paths to trait registry
FILE_ROOT = Path(__file__).resolve().parents[1]
TRAITS_REGISTRY_FILE = FILE_ROOT / "data" / "config" / "traits_registry.yaml"


@dataclass
class TraitObservation:
    """
    Standardized observation format that Head Coach produces.
    All coaches submit data that gets normalized into this format.
    """
    trait_path: str              # Dot notation: "PaDNA.EyeDNA.Color"
    value: Any                   # Normalized value
    confidence: float            # 0.0 - 1.0
    source: str                  # "photo_analysis", "user_statement", etc.
    timestamp: str               # ISO 8601
    metadata: Dict[str, Any] = field(default_factory=dict)  # Optional context


@dataclass
class ProposedInference:
    """
    Trait that Head Coach infers from observations.
    This is a PROPOSAL - Core has final authority.
    """
    trait_path: str
    value: Any
    confidence: float  # 0.0 to 1.0
    reasoning: str
    source_observations: List[str] = field(default_factory=list)  # Paths of observations that led to this
    category: str = "physical"
    inferred_by: str = "head_coach_ai"


@dataclass
class HeadCoachResult:
    """Complete result from Head Coach processing"""
    direct_observations: List[TraitObservation] = field(default_factory=list)
    inferred_traits: List[ProposedInference] = field(default_factory=list)
    curiosity_signals: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    llm_available: bool = False
    model_used: Optional[str] = None


def load_trait_registry() -> Dict[str, Any]:
    """Load the PaDNA trait registry to understand available traits"""
    if not TRAITS_REGISTRY_FILE.exists():
        logger.warning(f"Trait registry not found at {TRAITS_REGISTRY_FILE}")
        return {}

    try:
        import yaml
        with TRAITS_REGISTRY_FILE.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error(f"Failed to load trait registry: {exc}")
        return {}


def extract_trait_paths(registry: Dict[str, Any], prefix: str = "") -> List[str]:
    """Extract all valid PaDNA trait paths from the registry"""
    paths: List[str] = []

    def walk(node: Any, current_prefix: str = "") -> None:
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type and current_prefix:
                paths.append(current_prefix)

            for key, value in node.items():
                if key in {"type", "choices", "description", "examples", "notes", "example", "display"}:
                    continue
                next_prefix = f"{current_prefix}.{key}" if current_prefix else str(key)
                walk(value, next_prefix)
        elif isinstance(node, list):
            for item in node:
                walk(item, current_prefix)

    walk(registry, prefix)
    return sorted(set(paths))


def shape_photo_import(
    imported_traits: Dict[str, Any],
    user_id: str,
    image_quality: Optional[float] = None
) -> HeadCoachResult:
    """
    Shape photo import data into standardized observations.

    This is the Photo Coach adapter - takes photo analysis results
    and converts them into TraitObservations.

    Args:
        imported_traits: Raw traits from photo analysis
        user_id: User ID for logging
        image_quality: Optional image quality score (0.0-1.0)

    Returns:
        HeadCoachResult with observations and inferences
    """
    result = HeadCoachResult(llm_available=LLM_AVAILABLE)

    if not imported_traits:
        result.warnings.append("No traits provided to shape")
        return result

    timestamp = datetime.now(timezone.utc).isoformat()

    # Extract direct observations from photo
    for path, data in imported_traits.items():
        if isinstance(data, dict):
            value = data.get("resolved_value")
            confidence = data.get("ucn", 0) / 1000.0  # Convert UCN to 0-1 scale
        else:
            value = data
            confidence = 0.8  # Default confidence for photo observations

        # Adjust confidence based on image quality
        if image_quality is not None:
            confidence = confidence * image_quality

        observation = TraitObservation(
            trait_path=path,
            value=value,
            confidence=min(1.0, max(0.0, confidence)),
            source="photo_analysis",
            timestamp=timestamp,
            metadata={
                "image_quality": image_quality,
                "coach": "photo"
            }
        )
        result.direct_observations.append(observation)

    # Now perform AI inference on the observations
    if LLM_AVAILABLE and llama_chat is not None:
        try:
            inferences = _infer_from_observations(
                result.direct_observations,
                user_id=user_id
            )
            result.inferred_traits.extend(inferences)
            result.model_used = "llama3"
        except Exception as exc:
            logger.error(f"[HeadCoach:{user_id}] Inference error: {exc}", exc_info=True)
            result.warnings.append(f"AI inference failed: {exc}")
    else:
        result.warnings.append("LLM not available - skipping inference")

    return result


def _infer_from_observations(
    observations: List[TraitObservation],
    user_id: str,
    min_confidence: float = 0.6
) -> List[ProposedInference]:
    """
    Use AI to infer additional traits from observations.

    This is where Head Coach does the heavy AI lifting:
    - Analyzes patterns in observations
    - Reasons about correlations (e.g., red hair → freckles)
    - Proposes additional traits with confidence and reasoning
    """
    if not observations or llama_chat is None:
        return []

    # Load trait registry
    registry = load_trait_registry()
    available_paths = extract_trait_paths(registry)

    # Build prompt
    prompt = _build_inference_prompt(observations, available_paths)

    # Call LLM
    try:
        logger.info(f"[HeadCoach:{user_id}] Calling LLM for trait inference...")

        llm_response = llama_chat(
            system="You are a trait inference expert analyzing physical characteristics. Return only valid JSON.",
            user=prompt
        )

        if not llm_response.get("ok"):
            error_msg = llm_response.get("error", "Unknown error")
            logger.error(f"[HeadCoach:{user_id}] LLM inference failed: {error_msg}")
            return []

        # Parse response
        response_text = llm_response.get("text", "[]")

        # Extract JSON if wrapped in markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        inferences_raw = json.loads(response_text)

        if not isinstance(inferences_raw, list):
            logger.warning(f"[HeadCoach:{user_id}] LLM returned invalid format")
            return []

        # Convert to ProposedInference objects
        inferences = []
        observed_paths = {obs.trait_path for obs in observations}

        for inf in inferences_raw:
            if not isinstance(inf, dict):
                continue

            trait_path = inf.get("trait_path", "").strip()
            value = inf.get("value")
            confidence = inf.get("confidence", 0.0)
            reasoning = inf.get("reasoning", "").strip()
            source_traits = inf.get("source_traits", [])
            category = inf.get("category", "physical")

            # Validation
            if not trait_path or not value or not reasoning:
                continue

            if confidence < min_confidence:
                continue

            if not trait_path.startswith("PaDNA."):
                continue

            # Don't infer what was directly observed
            if trait_path in observed_paths:
                continue

            proposed = ProposedInference(
                trait_path=trait_path,
                value=value,
                confidence=min(1.0, max(0.0, float(confidence))),
                reasoning=reasoning,
                source_observations=source_traits if isinstance(source_traits, list) else [],
                category=category,
                inferred_by="head_coach_ai"
            )

            inferences.append(proposed)

        logger.info(f"[HeadCoach:{user_id}] Generated {len(inferences)} inferences")
        return inferences

    except json.JSONDecodeError as exc:
        logger.error(f"[HeadCoach:{user_id}] JSON parse error: {exc}")
        return []
    except Exception as exc:
        logger.error(f"[HeadCoach:{user_id}] Unexpected error: {exc}", exc_info=True)
        return []


def _build_inference_prompt(
    observations: List[TraitObservation],
    available_paths: List[str]
) -> str:
    """Build AI prompt for inferring additional traits from observations"""

    # Format observations
    obs_summary = []
    for obs in observations:
        obs_summary.append(
            f"  - {obs.trait_path}: {obs.value} "
            f"(confidence: {obs.confidence:.2f}, source: {obs.source})"
        )
    obs_text = "\n".join(obs_summary)

    # Sample available paths by category
    path_categories = {}
    for path in available_paths:
        parts = path.split(".")
        if len(parts) >= 2:
            category = parts[1]
            path_categories.setdefault(category, []).append(path)

    paths_text = []
    for category, paths in sorted(path_categories.items())[:15]:
        paths_text.append(f"\n{category}:")
        for path in paths[:5]:
            paths_text.append(f"  - {path}")
        if len(paths) > 5:
            paths_text.append(f"  ... and {len(paths) - 5} more")

    available_traits_section = "".join(paths_text)

    prompt = f"""You are the Head Coach AI analyzing physical trait observations to infer related characteristics.

OBSERVED TRAITS:
{obs_text}

AVAILABLE PADNA TRAIT PATHS (sample):
{available_traits_section}

TASK:
Based on the observed traits, infer additional physical characteristics that are:
1. Scientifically/statistically correlated with observed traits
2. High confidence (>0.6) based on biological, genetic, or statistical correlations
3. Valuable for building a complete physical profile

INFERENCE GUIDELINES:
- Red hair + fair skin → High probability of freckles, sun sensitivity, MC1R gene variants
- Blue/green eyes + light hair → Often Nordic/Celtic ancestry markers
- Height + build → Can infer proportions, clothing fit preferences
- Facial features → Ancestry markers, ethnic characteristics
- Use scientific knowledge and population statistics

For each inference, provide:
- trait_path: Exact PaDNA path (must match available paths)
- value: The inferred value (be specific)
- confidence: Float 0.0-1.0 (only suggest if >0.6)
- reasoning: Clear 2-3 sentence explanation
- source_traits: List of observed trait paths that led to this
- category: One of [physical, coloring, structural, stylistic, behavioral]

OUTPUT FORMAT (JSON array):
[
  {{
    "trait_path": "PaDNA.SkinDNA.Freckles",
    "value": "Present",
    "confidence": 0.85,
    "reasoning": "Red hair and fair skin are strong indicators of MC1R gene variants, which cause both red pigmentation and freckling. Studies show 80-90% correlation.",
    "source_traits": ["PaDNA.HairDNA.Color", "PaDNA.SkinDNA.Tone"],
    "category": "physical"
  }}
]

Be conservative - only suggest traits you're genuinely confident about. Quality over quantity.
Return ONLY the JSON array, no other text.
"""

    return prompt


def calculate_curiosity_signals(
    current_profile: Dict[str, Any],
    new_observations: List[TraitObservation],
    new_inferences: List[ProposedInference]
) -> List[Dict[str, Any]]:
    """
    Calculate curiosity signals to drive exploration.

    This identifies gaps in knowledge and suggests what data to gather next.
    Note: Actual curiosity value is calculated by Core as (1000 - RR),
    but Head Coach identifies WHICH traits need more data.
    """
    signals = []

    # For each new inference with moderate confidence, suggest confirmation
    for inference in new_inferences:
        if 0.6 <= inference.confidence < 0.85:
            signals.append({
                "trait_path": inference.trait_path,
                "curiosity_reason": "moderate_confidence_inference",
                "suggested_action": f"Confirm {inference.trait_path} - currently inferred at {inference.confidence:.0%} confidence",
                "priority": "medium"
            })

    return signals


__all__ = [
    "TraitObservation",
    "ProposedInference",
    "HeadCoachResult",
    "shape_photo_import",
    "calculate_curiosity_signals"
]
