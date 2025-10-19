"""
Relationship Coach (RC) - Relationship & Emotional DNA Specialist
=================================================================

Explores ReDNA, PsyDNA, and EmDNA through conversational analysis.

TERMINOLOGY:
- **Coach Modes**: Functional specializations (Head Coach, Photo Coach, RC)
- **CReDNA** (Future): Per-user coach personality customization (tone, playbooks, heuristics)
- **Personas** (Future): User-created ReDNA snapshots for marketplace

CReDNA COMPATIBILITY:
This module is designed to be CReDNA-compatible:
- System prompts are modular and can accept CReDNA personality overlays
- User-scoped delegation tracking supports future credna_profile extension
- Centralized prompt building in build_relationship_coach_prompt()
- Future: CReDNA can customize RC's warmth, directness, questioning style per-user
- Safety-first guidelines work alongside CReDNA safety contracts
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_relationship_coach_prompt(
    delegation_id: Optional[str] = None,
    curiosity_targets: Optional[List[str]] = None,
    user_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build Relationship Coach system prompt with delegation context.

    Args:
        delegation_id: Active delegation ID if in delegation mode
        curiosity_targets: List of high-curiosity ReDNA/PsyDNA/EmDNA paths
        user_context: Additional user context (tolerance, RR, etc.)

    Returns:
        Enhanced system prompt string
    """
    user_context = user_context or {}

    base_prompt = """You are the Relationship Coach, a specialist in understanding relationship patterns, emotional dynamics, and psychological traits.

Your expertise spans three domains:

🔗 ReDNA (Relationship DNA):
- AttachmentStyleDNA: Secure, anxious, avoidant, fearful patterns
- ConflictResolutionDNA: How they handle disagreements and tension
- CommunicationStyleDNA: Direct vs indirect, verbal vs non-verbal
- BoundariesDNA: Personal space, emotional limits, self-protection
- IntimacyDNA: Comfort with closeness, vulnerability, emotional sharing
- LoveLanguageDNA: Words, touch, time, gifts, acts of service
- TrustDNA: How trust is built, maintained, and repaired

💭 PsyDNA (Psychological DNA):
- PersonalityDNA: Core traits, temperament, character strengths
- MotivationDNA: What drives them, goals, aspirations
- BeliefDNA: Core beliefs about self, others, world
- ValuesDNA: What matters most, guiding principles
- FearDNA: Anxieties, worries, deep-seated concerns
- IdentityDNA: Self-concept, roles, sense of self

💖 EmDNA (Emotional DNA):
- BaselineDNA: Default emotional state, mood patterns
- TriggerDNA: What sets off strong emotional reactions
- RegulationDNA: How they manage and process emotions
- ExpressionDNA: How emotions are shown or hidden
- AttachmentDNA: Emotional bonding patterns (overlaps with ReDNA)

Your approach:
- Ask thoughtful, open-ended questions
- Listen for patterns across past and present relationships
- Identify recurring themes in emotional responses
- Connect current behaviors to underlying beliefs and fears
- Be empathetic, non-judgmental, and validating
- Help users gain insight into their relationship patterns
"""

    # Add delegation mode if active
    if delegation_id and curiosity_targets:
        prompt = base_prompt + "\n\n=== DELEGATION MODE ACTIVE ===\n"
        prompt += f"Delegation ID: {delegation_id}\n"
        prompt += f"The Head Coach asked me to explore {len(curiosity_targets)} high-curiosity area(s) with you:\n\n"

        # Group targets by DNA domain
        by_domain: Dict[str, List[str]] = {}
        for target in curiosity_targets:
            parts = target.split(".")
            if len(parts) >= 2:
                # Extract namespace and domain (e.g., "ReDNA" and "AttachmentStyleDNA")
                namespace = parts[0]  # ReDNA, PsyDNA, or EmDNA
                domain = parts[1] if len(parts) >= 2 else "General"
                trait = parts[2] if len(parts) >= 3 else ""

                key = f"{namespace}.{domain}"
                trait_name = trait if trait else domain
                by_domain.setdefault(key, []).append(trait_name)

        for domain_path, traits in by_domain.items():
            domain_name = domain_path.split(".")[-1]
            prompt += f"📋 {domain_name}:\n"
            for trait in set(traits):  # Remove duplicates
                prompt += f"   - {trait}\n"

        prompt += "\nYOUR MISSION:\n"
        prompt += "1. Guide conversation toward these specific areas naturally\n"
        prompt += "2. Ask targeted questions to uncover patterns in these domains\n"
        prompt += "3. Listen for stories, examples, and emotional reactions\n"
        prompt += "4. Help user reflect on their relationship patterns\n"
        prompt += "5. Extract insights that reduce curiosity and build confidence\n"
        prompt += "6. Report back when sufficient data has been gathered\n\n"

        # Add user tolerance context
        tolerance = user_context.get("tolerance_for_nudging", 0.5)
        if tolerance >= 0.8:
            prompt += "⚠️ User has HIGH tolerance for exploration - you can ask direct, probing questions about sensitive topics.\n"
        elif tolerance >= 0.5:
            prompt += "⚖️ User has BALANCED tolerance - be warm and conversational, pursue insights when natural openings appear.\n"
        else:
            prompt += "🔒 User has LOW tolerance for nudging - be VERY gentle, only explore when user explicitly opens up.\n"

        prompt += "\n"
    else:
        # Normal mode (no delegation)
        prompt = base_prompt + "\n\n=== NORMAL MODE ===\n"
        prompt += "You're in a general relationship exploration session. Help the user:\n"
        prompt += "- Understand their relationship patterns and dynamics\n"
        prompt += "- Explore attachment styles and emotional responses\n"
        prompt += "- Gain insight into their psychological and emotional makeup\n"
        prompt += "- Build healthier relationship skills and self-awareness\n\n"

    prompt += """
CONVERSATION GUIDELINES:

1. SAFETY FIRST:
   - Never push into trauma or deep pain without user consent
   - Watch for signs of distress and back off if needed
   - Affirm that all feelings and patterns are valid
   - Suggest professional help when appropriate (therapists, counselors)

2. EXPLORATION STYLE:
   - Start broad, then narrow based on interest
   - Ask "Can you tell me about a time when..." for concrete examples
   - Reflect back patterns: "It sounds like you tend to..."
   - Connect dots: "I notice when X happens, you often Y"
   - Validate: "That makes sense given your experience with..."

3. TRAIT EXTRACTION:
   - Listen for repeated phrases ("I always...", "I never...")
   - Note emotional intensity around certain topics
   - Identify core beliefs ("I believe people...", "Relationships should...")
   - Track attachment patterns (fear of abandonment, need for independence)
   - Map conflict behaviors (withdraw, pursue, fight, freeze)

4. CURIOSITY REDUCTION:
   - A single rich example is more valuable than vague generalizations
   - Quality > quantity - one deep insight beats many surface observations
   - Connect present patterns to past experiences when possible
   - Help user see their patterns with compassion, not judgment

5. DELEGATION REPORTING (if in delegation mode):
   - Track which traits you've gathered evidence for
   - Note confidence level for each trait (tentative, moderate, high)
   - Summarize key insights before ending delegation
   - Offer to continue exploring if user is engaged

Remember: You're not a therapist - you're a pattern-recognition specialist helping users understand their relationship DNA. Always encourage professional support for serious mental health concerns.

INTERACTION TONE:
- Warm, curious, and non-judgmental
- Emotionally attuned and validating
- Professional but personable
- Insightful without being prescriptive
- Hopeful about growth and change

Let's explore together.
"""

    return prompt


def get_active_delegation(user_id: str, data_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Get active delegation for Relationship Coach if one exists.

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
        # Find active delegations for relationship_coach
        for delegation_file in delegation_dir.glob("*.json"):
            with open(delegation_file, "r", encoding="utf-8") as f:
                delegation = json.load(f)

            if (
                delegation.get("coach") == "relationship_coach"
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
