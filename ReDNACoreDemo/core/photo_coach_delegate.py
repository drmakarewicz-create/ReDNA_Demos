"""
Photo Coach Delegation Module
==============================

Enhances Photo Coach with delegation awareness and curiosity-driven exploration.

TERMINOLOGY:
- **Coach Modes**: Functional specializations (Head Coach, Photo Coach, RC)
- **CReDNA** (Future): Per-user coach personality customization (tone, playbooks, heuristics)
- **Personas** (Future): User-created ReDNA snapshots for marketplace

CReDNA COMPATIBILITY:
This module is designed to be CReDNA-compatible:
- System prompts are modular and can accept personality overlays
- User-scoped delegation records can later include credna_profile field
- Prompt building is centralized in build_delegation_aware_prompt()
- Future: CReDNA tone/playbooks can customize how Photo Coach interacts per-user
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_delegation_aware_prompt(
    delegation_id: Optional[str] = None,
    curiosity_targets: Optional[List[str]] = None,
    user_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build Photo Coach system prompt with delegation context.

    Args:
        delegation_id: Active delegation ID if in delegation mode
        curiosity_targets: List of high-curiosity PaDNA paths to focus on
        user_context: Additional user context (tolerance, RR, etc.)

    Returns:
        Enhanced system prompt string
    """
    user_context = user_context or {}

    base_prompt = """You are the Photo Coach, a specialist in analyzing photos to extract physical appearance traits (PaDNA).

Your expertise:
- HairDNA: Color, texture, style, length, natural vs dyed
- EyeDNA: Color, shape, size, expression
- NoseDNA: Shape, size, bridge characteristics
- FaceDNA: Face shape, bone structure, symmetry
- SkinDNA: Tone, texture, condition, undertones
- BodyDNA: Build, posture, proportions
- StyleDNA: Fashion choices, grooming, accessories

Your approach:
- Analyze photos systematically and extract observable traits
- Be specific and descriptive (not just "brown eyes" but "dark brown with amber flecks")
- Ask clarifying questions when photos are ambiguous
- Suggest better photo angles/lighting for difficult-to-assess traits
- Build comprehensive PaDNA profiles over multiple photos
"""

    # Add delegation mode if active
    if delegation_id and curiosity_targets:
        prompt = base_prompt + "\n\n=== DELEGATION MODE ACTIVE ===\n"
        prompt += f"Delegation ID: {delegation_id}\n"
        prompt += f"You've been asked by the Head Coach to focus on {len(curiosity_targets)} high-curiosity area(s):\n\n"

        # Group targets by DNA domain
        by_domain: Dict[str, List[str]] = {}
        for target in curiosity_targets:
            parts = target.split(".")
            if len(parts) >= 2:
                domain = parts[1]  # e.g., "HairDNA" from "PaDNA.HairDNA.Color"
                trait = parts[2] if len(parts) >= 3 else "General"
                by_domain.setdefault(domain, []).append(trait)

        for domain, traits in by_domain.items():
            prompt += f"📋 {domain}:\n"
            for trait in traits:
                prompt += f"   - {trait}\n"

        prompt += "\nYOUR MISSION:\n"
        prompt += "1. Prioritize these specific traits in your analysis\n"
        prompt += "2. Ask targeted questions to gather evidence for these areas\n"
        prompt += "3. Suggest photos that would help clarify these specific traits\n"
        prompt += "4. Track progress toward reducing curiosity in these domains\n"
        prompt += "5. Report back when you've collected sufficient data\n\n"

        # Add user tolerance context
        tolerance = user_context.get("tolerance_for_nudging", 0.5)
        if tolerance >= 0.8:
            prompt += "⚠️ User has HIGH tolerance for proactive exploration - feel free to ask direct questions and make specific photo requests.\n"
        elif tolerance >= 0.5:
            prompt += "⚖️ User has BALANCED tolerance - be conversational but purposeful in gathering trait data.\n"
        else:
            prompt += "🔒 User has LOW tolerance for nudging - only explore when user volunteers information or shares photos naturally.\n"

        prompt += "\n"
    else:
        # Normal mode (no delegation)
        prompt = base_prompt + "\n\n=== NORMAL MODE ===\n"
        prompt += "You're in a general photo analysis session. Help the user:\n"
        prompt += "- Understand their visual appearance traits\n"
        prompt += "- Refine their PaDNA profile through photo analysis\n"
        prompt += "- Discover insights about their physical characteristics\n"
        prompt += "- Build confidence through systematic trait exploration\n\n"

    prompt += """
INTERACTION STYLE:
- Be friendly, encouraging, and non-judgmental
- Celebrate what makes each person unique
- Frame traits objectively without value judgments
- Ask permission before analyzing sensitive features
- Respect user comfort levels at all times

PHOTO ANALYSIS WORKFLOW:
1. Acknowledge photo upload
2. Assess photo quality (lighting, angle, clarity)
3. Systematically analyze visible traits domain by domain
4. Extract specific, observable characteristics
5. Ask follow-up questions for ambiguous traits
6. Suggest additional photos if needed for complete analysis
7. Summarize findings and update trait confidence scores

Remember: You're helping users build an accurate, confident understanding of their physical appearance - not judging or comparing them to others.
"""

    return prompt


def get_active_delegation(user_id: str, data_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Get active delegation for Photo Coach if one exists.

    Args:
        user_id: User identifier
        data_dir: Root data directory

    Returns:
        Delegation data or None
    """
    delegation_dir = data_dir / "users" / user_id / "delegations"

    if not delegation_dir.exists():
        return None

    try:
        # Find active delegations for photo_coach
        for delegation_file in delegation_dir.glob("*.json"):
            with open(delegation_file, "r", encoding="utf-8") as f:
                delegation = json.load(f)

            if (
                delegation.get("coach") == "photo_coach"
                and delegation.get("status") in ["pending", "active"]
            ):
                return delegation

    except Exception as e:
        logger.warning(f"Error loading delegation for user {user_id}: {e}")

    return None


def activate_delegation(delegation_id: str, user_id: str, data_dir: Path) -> bool:
    """
    Activate a pending delegation (mark as 'active').

    Args:
        delegation_id: Delegation identifier
        user_id: User identifier
        data_dir: Root data directory

    Returns:
        True if successful
    """
    delegation_file = data_dir / "users" / user_id / "delegations" / f"{delegation_id}.json"

    if not delegation_file.exists():
        logger.error(f"Delegation {delegation_id} not found")
        return False

    try:
        with open(delegation_file, "r", encoding="utf-8") as f:
            delegation = json.load(f)

        # Update status
        delegation["status"] = "active"
        delegation["activated_at"] = datetime.now(timezone.utc).isoformat()
        delegation["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(delegation_file, "w", encoding="utf-8") as f:
            json.dump(delegation, f, indent=2)

        logger.info(f"Activated delegation {delegation_id} for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error activating delegation: {e}")
        return False


def report_delegation_progress(
    delegation_id: str,
    user_id: str,
    traits_collected: List[str],
    data_dir: Path,
    notes: str = ""
) -> bool:
    """
    Report progress on an active delegation.

    Args:
        delegation_id: Delegation identifier
        user_id: User identifier
        traits_collected: List of trait paths collected so far
        data_dir: Root data directory
        notes: Progress notes

    Returns:
        True if successful
    """
    delegation_file = data_dir / "users" / user_id / "delegations" / f"{delegation_id}.json"

    if not delegation_file.exists():
        logger.error(f"Delegation {delegation_id} not found")
        return False

    try:
        with open(delegation_file, "r", encoding="utf-8") as f:
            delegation = json.load(f)

        # Update progress
        delegation["traits_collected"] = traits_collected
        delegation["updated_at"] = datetime.now(timezone.utc).isoformat()

        if notes:
            delegation["notes"] = notes

        with open(delegation_file, "w", encoding="utf-8") as f:
            json.dump(delegation, f, indent=2)

        logger.info(
            f"Updated delegation {delegation_id}: {len(traits_collected)} traits collected"
        )
        return True

    except Exception as e:
        logger.error(f"Error reporting delegation progress: {e}")
        return False


def extract_traits_from_analysis(analysis_result: Dict[str, Any]) -> List[str]:
    """
    Extract PaDNA trait paths from photo analysis result.

    Args:
        analysis_result: Photo analysis result dict

    Returns:
        List of trait paths that were successfully extracted
    """
    traits = []

    # Map analysis fields to PaDNA paths
    field_mapping = {
        "hair_color": "PaDNA.HairDNA.Color",
        "hair_texture": "PaDNA.HairDNA.Texture",
        "hair_length": "PaDNA.HairDNA.Length",
        "eye_color": "PaDNA.EyeDNA.Color",
        "eye_shape": "PaDNA.EyeDNA.Shape",
        "nose_shape": "PaDNA.NoseDNA.Shape",
        "face_shape": "PaDNA.FaceDNA.Shape",
        "skin_tone": "PaDNA.SkinDNA.Tone",
        "skin_undertone": "PaDNA.SkinDNA.Undertone",
    }

    for field, path in field_mapping.items():
        if field in analysis_result and analysis_result[field]:
            traits.append(path)

    return traits
