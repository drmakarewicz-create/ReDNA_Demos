"""
LLM-Powered Trait Inference Engine

This module uses AI to analyze imported PaDNA traits and infer related characteristics
with confidence scores and reasoning. Designed to improve as AI models advance.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
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
class InferredTrait:
    """Represents a single trait inference from the LLM"""
    trait_path: str
    value: Any
    confidence: float  # 0.0 to 1.0
    reasoning: str
    source_traits: List[str] = field(default_factory=list)  # Which imported traits led to this inference
    category: str = "physical"  # physical, behavioral, stylistic, etc.


@dataclass
class InferenceResult:
    """Complete result from trait inference analysis"""
    inferences: List[InferredTrait] = field(default_factory=list)
    source_trait_count: int = 0
    inference_count: int = 0
    skipped: List[str] = field(default_factory=list)  # Traits LLM couldn't confidently infer
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


def build_inference_prompt(
    imported_traits: Dict[str, Any],
    available_paths: List[str],
    user_context: Optional[str] = None
) -> str:
    """Build a sophisticated prompt for the LLM to infer related traits"""

    # Format imported traits for the prompt
    trait_summary = []
    for path, data in imported_traits.items():
        if isinstance(data, dict):
            value = data.get("resolved_value")
            ucn = data.get("ucn", "unknown")
            trait_summary.append(f"  - {path}: {value} (UCN: {ucn})")
        else:
            trait_summary.append(f"  - {path}: {data}")

    traits_text = "\n".join(trait_summary)

    # Sample of available paths (to keep prompt size manageable)
    # Group by category for better LLM understanding
    path_categories = {}
    for path in available_paths:
        parts = path.split(".")
        if len(parts) >= 2:
            category = parts[1]  # e.g., "HairDNA", "SkinDNA", "EyeDNA"
            path_categories.setdefault(category, []).append(path)

    # Build available paths section
    paths_text = []
    for category, paths in sorted(path_categories.items())[:15]:  # Limit to 15 categories
        paths_text.append(f"\n{category}:")
        for path in paths[:5]:  # Show first 5 paths per category
            paths_text.append(f"  - {path}")
        if len(paths) > 5:
            paths_text.append(f"  ... and {len(paths) - 5} more")

    available_traits_section = "".join(paths_text)

    prompt = f"""You are an expert in human physical characteristics, genetics, and phenotype correlations.
You are analyzing a person's PaDNA (Physical DNA) profile to infer additional traits based on known imported traits.

IMPORTED TRAITS:
{traits_text}

AVAILABLE PADNA TRAIT PATHS (sample):
{available_traits_section}

TASK:
Analyze the imported traits and infer additional physical, appearance-related, or stylistic traits that are:
1. Scientifically/statistically correlated with the given traits
2. High confidence (>0.6) based on biological, genetic, or strong statistical correlations
3. Valuable for building a complete physical profile

For each inference, provide:
- trait_path: The exact PaDNA path (must match available paths)
- value: The inferred value (be specific)
- confidence: Float between 0.0 and 1.0 (only suggest if >0.6)
- reasoning: Clear explanation of why this inference makes sense (2-3 sentences)
- source_traits: List of imported trait paths that led to this inference
- category: One of [physical, coloring, structural, stylistic, behavioral]

INFERENCE GUIDELINES:
- Red hair + fair skin → High probability of freckles, sun sensitivity, MC1R gene variants
- Blue/green eyes + light hair → Often Nordic/Celtic ancestry markers
- Height + build → Can infer proportions, clothing fit preferences
- Age + style → Professional context, life stage markers
- Facial features → Ancestry markers, ethnic characteristics
- Body measurements → Proportions, health markers

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

    if user_context:
        prompt += f"\n\nADDITIONAL CONTEXT:\n{user_context}"

    return prompt


def infer_traits_from_import(
    imported_traits: Dict[str, Any],
    user_id: str,
    min_confidence: float = 0.6,
    max_inferences: int = 10,
    user_context: Optional[str] = None
) -> InferenceResult:
    """
    Use LLM to infer additional traits from imported data.

    Args:
        imported_traits: Dict of PaDNA traits that were just imported
        user_id: User ID for logging
        min_confidence: Minimum confidence threshold (0.0-1.0)
        max_inferences: Maximum number of inferences to return
        user_context: Optional additional context about the user

    Returns:
        InferenceResult with inferred traits and metadata
    """

    result = InferenceResult(
        source_trait_count=len(imported_traits),
        llm_available=LLM_AVAILABLE
    )

    if not LLM_AVAILABLE or llama_chat is None:
        result.warnings.append("LLM client not available - trait inference disabled")
        return result

    if not imported_traits:
        result.warnings.append("No imported traits to analyze")
        return result

    # Load trait registry to know what traits are available
    registry = load_trait_registry()
    available_paths = extract_trait_paths(registry)

    if not available_paths:
        result.warnings.append("Trait registry unavailable - using imported paths only")
        available_paths = list(imported_traits.keys())

    # Build the inference prompt
    prompt = build_inference_prompt(imported_traits, available_paths, user_context)

    # Call LLM
    try:
        logger.info(f"[Inference:{user_id}] Calling LLM for trait inference...")

        llm_response = llama_chat(
            system="You are a trait inference expert. Return only valid JSON.",
            user=prompt
        )

        if not llm_response.get("ok"):
            error_msg = llm_response.get("error", "Unknown error")
            result.warnings.append(f"LLM inference failed: {error_msg}")
            return result

        result.model_used = llm_response.get("model", "unknown")

        # Parse LLM response
        response_text = llm_response.get("text", "[]")

        # Try to extract JSON if wrapped in markdown or other text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        inferences_raw = json.loads(response_text)

        if not isinstance(inferences_raw, list):
            result.warnings.append("LLM returned invalid format (expected JSON array)")
            return result

        # Process each inference
        imported_paths = set(imported_traits.keys())

        for idx, inf in enumerate(inferences_raw[:max_inferences]):
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
                result.warnings.append(f"Skipping incomplete inference #{idx+1}")
                continue

            if confidence < min_confidence:
                result.skipped.append(f"{trait_path} (confidence {confidence:.2f} below threshold)")
                continue

            # Check if trait path is valid (exists in registry or at least looks like PaDNA)
            if not trait_path.startswith("PaDNA."):
                result.warnings.append(f"Skipping invalid path: {trait_path}")
                continue

            # Don't infer traits that were already imported
            if trait_path in imported_paths:
                result.warnings.append(f"Skipping {trait_path} (already imported)")
                continue

            # Create inference object
            inferred = InferredTrait(
                trait_path=trait_path,
                value=value,
                confidence=min(1.0, max(0.0, float(confidence))),
                reasoning=reasoning,
                source_traits=source_traits if isinstance(source_traits, list) else [],
                category=category
            )

            result.inferences.append(inferred)

        result.inference_count = len(result.inferences)

        logger.info(
            f"[Inference:{user_id}] Generated {result.inference_count} inferences "
            f"from {result.source_trait_count} source traits"
        )

    except json.JSONDecodeError as exc:
        result.warnings.append(f"Failed to parse LLM response as JSON: {exc}")
        logger.error(f"[Inference:{user_id}] JSON parse error: {exc}")
    except Exception as exc:
        result.warnings.append(f"Inference error: {str(exc)}")
        logger.error(f"[Inference:{user_id}] Unexpected error: {exc}", exc_info=True)

    return result


def apply_inferences_to_user_state(
    resolved: Dict[str, Any],
    inferences: List[InferredTrait],
    approved_indices: Optional[Set[int]] = None
) -> Dict[str, Any]:
    """
    Apply approved inferences to user's resolved state.

    Args:
        resolved: Current user resolved state
        inferences: List of inferred traits
        approved_indices: Set of inference indices that were approved (None = all)

    Returns:
        Updated resolved dict
    """

    if approved_indices is None:
        approved_indices = set(range(len(inferences)))

    from .bundles import iso_now
    now = iso_now()

    for idx, inference in enumerate(inferences):
        if idx not in approved_indices:
            continue

        trait_path = inference.trait_path

        # Create or update trait entry
        entry = resolved.get(trait_path, {})
        if not isinstance(entry, dict):
            entry = {}

        entry["resolved_value"] = inference.value
        entry["ucn"] = inference.confidence * 1000  # Convert 0-1 to 0-1000 scale
        entry["inferred"] = True
        entry["inferred_by"] = "ai"
        entry["inferred_ts"] = now
        entry["reasons"] = [f"ai_inference:confidence_{inference.confidence:.2f}"]
        entry["notes"] = {
            "inference_reasoning": inference.reasoning,
            "source_traits": inference.source_traits,
            "category": inference.category
        }

        resolved[trait_path] = entry

    return resolved
