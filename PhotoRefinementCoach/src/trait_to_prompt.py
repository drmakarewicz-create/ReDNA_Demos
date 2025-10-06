"""
Trait-to-Prompt Converter

Converts structured PaDNA trait data into optimized prompts for image generation.
Supports multiple rendering engines (Stable Diffusion, FLUX, Midjourney, etc.)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TraitCategory:
    """Represents a category of traits with rendering priority."""

    def __init__(
        self,
        name: str,
        priority: int,
        prefix: str,
        weight: float = 1.0
    ):
        self.name = name
        self.priority = priority  # Lower = higher priority
        self.prefix = prefix
        self.weight = weight  # Emphasis weight in prompt


# Trait category configuration
TRAIT_CATEGORIES = {
    "face": TraitCategory("Face", 1, "PaDNA.FacialDNA", 1.2),
    "eyes": TraitCategory("Eyes", 2, "PaDNA.EyeDNA", 1.1),
    "hair": TraitCategory("Hair", 3, "PaDNA.HairDNA", 1.1),
    "skin": TraitCategory("Skin", 4, "PaDNA.SkinDNA", 1.0),
    "smile": TraitCategory("Smile", 5, "PaDNA.SmileDNA", 0.9),
    "body": TraitCategory("Body", 6, "PaDNA.BodyDNA", 0.8),
    "expression": TraitCategory("Expression", 7, "PaDNA.ExpressionDNA", 0.7),
    "fitness": TraitCategory("Fitness", 8, "PaDNA.FitnessDNA", 0.6),
    "apparel": TraitCategory("Apparel", 9, "PaDNA.ApparelDNA", 0.5),
}


class PromptBuilder:
    """Builds optimized prompts from PaDNA traits."""

    def __init__(self, style: str = "photorealistic"):
        """
        Initialize prompt builder.

        Args:
            style: Rendering style (photorealistic, portrait, cinematic, artistic)
        """
        self.style = style
        self.trait_order = self._build_trait_order()

    def _build_trait_order(self) -> List[str]:
        """Define the order traits should appear in prompts (most important first)."""
        return [
            # Core appearance (highest priority)
            "PaDNA.EyeDNA.Color",
            "PaDNA.EyeDNA.Shape",
            "PaDNA.HairDNA.Color",
            "PaDNA.HairDNA.Length",
            "PaDNA.HairDNA.Texture",
            "PaDNA.SkinDNA.Tone",
            "PaDNA.SkinDNA.Freckles",

            # Facial features
            "PaDNA.SmileDNA.SmileShape",
            "PaDNA.SmileDNA.Teeth",
            "PaDNA.EyeDNA.Lashes",
            "PaDNA.FacialDNA.FaceShape",
            "PaDNA.HairDNA.Parting",
            "PaDNA.HairDNA.Volume",

            # Expression
            "PaDNA.ExpressionDNA.TypicalExpression",
            "PaDNA.ExpressionDNA.EyeContact",

            # Body (secondary)
            "PaDNA.BodyDNA.Build",
            "PaDNA.BodyDNA.HeightEstimateCM",
            "PaDNA.BodyDNA.WaistHipRatio",
            "PaDNA.BodyDNA.Legs",
            "PaDNA.BodyDNA.Arms",
            "PaDNA.BodyDNA.Bust",
            "PaDNA.BodyDNA.Shoulders",
            "PaDNA.FitnessDNA.Indicators",

            # Details
            "PaDNA.BodyDNA.Navel",
            "PaDNA.ApparelDNA.Jewelry.Necklace",
            "PaDNA.ApparelDNA.Jewelry.Earrings",
            "PaDNA.ApparelDNA.StyleThemes",
        ]

    def build_prompt(
        self,
        traits: Dict[str, Dict[str, Any]],
        emphasis_threshold: float = 800.0,
        include_style_prefix: bool = True,
        max_tokens: int = 200
    ) -> str:
        """
        Build a natural language prompt from traits.

        Args:
            traits: Dictionary of trait paths to trait data
            emphasis_threshold: UCN threshold for emphasized traits
            include_style_prefix: Include style description at start
            max_tokens: Approximate max tokens (words) in prompt

        Returns:
            Optimized prompt string
        """
        segments = []

        # Style prefix
        if include_style_prefix:
            style_prefixes = {
                "photorealistic": "Professional high-quality portrait photograph, photorealistic, 8k, detailed,",
                "portrait": "Studio portrait, professional lighting, detailed features,",
                "cinematic": "Cinematic portrait, film quality, dramatic lighting, detailed,",
                "artistic": "Artistic portrait, elegant composition, refined details,",
            }
            segments.append(style_prefixes.get(self.style, style_prefixes["photorealistic"]))

        # Build descriptions by category priority
        descriptions = self._extract_descriptions(traits, emphasis_threshold)

        # Add high-priority features first
        face_parts = []

        # Eyes
        eye_desc = descriptions.get("eyes", [])
        if eye_desc:
            face_parts.extend(eye_desc)

        # Hair
        hair_desc = descriptions.get("hair", [])
        if hair_desc:
            face_parts.extend(hair_desc)

        # Skin
        skin_desc = descriptions.get("skin", [])
        if skin_desc:
            face_parts.extend(skin_desc)

        # Face features
        face_desc = descriptions.get("face", [])
        smile_desc = descriptions.get("smile", [])
        if smile_desc:
            face_parts.extend(smile_desc)
        if face_desc:
            face_parts.extend(face_desc)

        # Core subject with face features
        if face_parts:
            segments.append("a woman with " + ", ".join(face_parts) + ".")
        else:
            segments.append("a woman.")

        # Expression
        expression_desc = descriptions.get("expression", [])
        if expression_desc:
            segments.append("Expression: " + ", ".join(expression_desc[:2]) + ".")

        # Body and fitness
        body_parts = []
        body_desc = descriptions.get("body", [])
        fitness_desc = descriptions.get("fitness", [])

        if body_desc:
            body_parts.extend(body_desc[:4])  # Limit body details
        if fitness_desc:
            body_parts.extend(fitness_desc[:2])  # Limit fitness details

        if body_parts:
            segments.append("Body: " + ", ".join(body_parts) + ".")

        # Details (jewelry, piercings)
        apparel_desc = descriptions.get("apparel", [])
        if apparel_desc:
            details = apparel_desc[:3]  # Limit to key details
            if details:
                segments.append("Wearing: " + ", ".join(details) + ".")

        # Join segments
        prompt = " ".join(segments)

        # Add quality keywords
        prompt += ", sharp focus, high detail, natural lighting"

        # Truncate if too long (approximate)
        words = prompt.split()
        if len(words) > max_tokens:
            prompt = " ".join(words[:max_tokens]) + "..."

        return prompt

    def _extract_descriptions(
        self,
        traits: Dict[str, Dict[str, Any]],
        emphasis_threshold: float
    ) -> Dict[str, List[str]]:
        """
        Extract natural language descriptions organized by category.

        Args:
            traits: Trait dictionary
            emphasis_threshold: UCN threshold for emphasis

        Returns:
            Dictionary of category -> list of descriptions
        """
        descriptions: Dict[str, List[str]] = {}

        for trait_path, trait_data in traits.items():
            if not isinstance(trait_data, dict):
                continue

            value = trait_data.get("resolved_value")
            ucn = trait_data.get("ucn", 0)

            if value is None:
                continue

            # Determine category
            category = self._categorize_trait(trait_path)
            if category not in descriptions:
                descriptions[category] = []

            # Convert trait to description
            desc = self._trait_to_description(trait_path, value, ucn, emphasis_threshold)
            if desc:
                descriptions[category].append(desc)

        return descriptions

    def _categorize_trait(self, path: str) -> str:
        """Determine category for a trait path."""
        for cat_key, category in TRAIT_CATEGORIES.items():
            if path.startswith(category.prefix):
                return cat_key
        return "other"

    def _trait_to_description(
        self,
        path: str,
        value: Any,
        ucn: float,
        emphasis_threshold: float
    ) -> Optional[str]:
        """
        Convert a single trait to a natural language description.

        Args:
            path: Trait path
            value: Trait value
            ucn: Confidence score
            emphasis_threshold: UCN threshold for emphasis

        Returns:
            Natural language description or None
        """
        # Handle list values
        if isinstance(value, list):
            if not value:
                return None
            # Join list items
            if len(value) == 1:
                value = str(value[0])
            else:
                value = ", ".join(str(v) for v in value[:3])  # Limit to 3 items

        # Convert to string for processing
        if isinstance(value, str):
            value_display = value
            value_str = value.lower()
        else:
            value_display = str(value)
            value_str = str(value).lower()

        # Skip certain values
        skip_values = ["absent", "none", "n/a", "unknown"]
        if value_str in skip_values:
            return None

        # Map trait paths to natural descriptions
        descriptions = {
            # Eyes
            "PaDNA.EyeDNA.Color": f"{value_display} eyes",
            "PaDNA.EyeDNA.Shape": f"{value_str}-shaped eyes",
            "PaDNA.EyeDNA.Lashes": f"{value_str} eyelashes",
            "PaDNA.EyeDNA.EyeSpacing": f"{value_str} eye spacing",

            # Hair
            "PaDNA.HairDNA.Color": f"{value_str} hair",
            "PaDNA.HairDNA.Length": f"{value_str} hair",
            "PaDNA.HairDNA.Texture": f"{value_str} hair",
            "PaDNA.HairDNA.Volume": f"{value_str} voluminous hair",
            "PaDNA.HairDNA.Parting": f"hair with {value_str}",

            # Skin
            "PaDNA.SkinDNA.Tone": f"{value_str} skin",
            "PaDNA.SkinDNA.Freckles": f"{value_str} freckles" if "present" in value_str else None,

            # Face/Smile
            "PaDNA.SmileDNA.SmileShape": f"{value_str}",
            "PaDNA.SmileDNA.Teeth": f"{value_str} teeth",
            "PaDNA.SmileDNA.Dimples": f"dimples" if "present" in value_str else None,

            # Expression
            "PaDNA.ExpressionDNA.TypicalExpression": f"{value_str}",
            "PaDNA.ExpressionDNA.EyeContact": f"{value_str}",

            # Body
            "PaDNA.BodyDNA.Build": f"{value_str} build",
            "PaDNA.BodyDNA.WaistHipRatio": f"{value_str} figure",
            "PaDNA.BodyDNA.Legs": f"{value_str} legs",
            "PaDNA.BodyDNA.Arms": f"{value_str} arms",
            "PaDNA.BodyDNA.Bust": f"{value_str} bust",
            "PaDNA.BodyDNA.Navel": "navel piercing" if "pierced" in value_str else None,

            # Fitness
            "PaDNA.FitnessDNA.Indicators": f"{value_str}",

            # Apparel/Jewelry
            "PaDNA.ApparelDNA.Jewelry.Necklace": f"wearing {value_str}",
            "PaDNA.ApparelDNA.Jewelry.Earrings": f"wearing {value_str}",
        }

        desc = descriptions.get(path)

        # Fallback: extract last part of path and use value
        if desc is None and value:
            trait_name = path.split(".")[-1].lower()
            desc = f"{value_str}"

        # Add emphasis for high-confidence traits
        if desc and ucn >= emphasis_threshold:
            # Could add parentheses or other emphasis markers here
            pass

        return desc


class ImageGenerationRequest:
    """Represents a request for image generation."""

    def __init__(
        self,
        prompt: str,
        negative_prompt: str = "",
        style: str = "photorealistic",
        width: int = 768,
        height: int = 1024,
        steps: int = 30,
        cfg_scale: float = 7.0,
        seed: Optional[int] = None,
    ):
        self.prompt = prompt
        self.negative_prompt = negative_prompt or self._default_negative_prompt()
        self.style = style
        self.width = width
        self.height = height
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.seed = seed

    def _default_negative_prompt(self) -> str:
        """Default negative prompt to avoid common issues."""
        return (
            "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
            "bad proportions, extra limbs, mutated, disfigured, "
            "watermark, text, signature, logo, multiple heads, duplicate, "
            "cartoon, anime, painting, illustration"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "seed": self.seed,
        }


def generate_prompt_from_resolved(
    resolved_path: Path,
    style: str = "photorealistic",
    emphasis_threshold: float = 800.0
) -> Tuple[str, ImageGenerationRequest]:
    """
    Generate an image prompt from a resolved.json file.

    Args:
        resolved_path: Path to resolved.json
        style: Rendering style
        emphasis_threshold: UCN threshold for emphasis

    Returns:
        Tuple of (prompt text, ImageGenerationRequest)
    """
    with resolved_path.open("r") as f:
        traits = json.load(f)

    builder = PromptBuilder(style=style)
    prompt = builder.build_prompt(traits, emphasis_threshold=emphasis_threshold)

    request = ImageGenerationRequest(
        prompt=prompt,
        style=style,
        width=768,
        height=1024,
        steps=40,
        cfg_scale=7.5,
    )

    return prompt, request


def generate_prompt_from_traits(
    traits: Dict[str, Dict[str, Any]],
    style: str = "photorealistic",
    emphasis_threshold: float = 800.0
) -> str:
    """
    Generate an image prompt from trait dictionary.

    Args:
        traits: Dictionary of trait paths to trait data
        style: Rendering style
        emphasis_threshold: UCN threshold for emphasis

    Returns:
        Optimized prompt string
    """
    builder = PromptBuilder(style=style)
    return builder.build_prompt(traits, emphasis_threshold=emphasis_threshold)
