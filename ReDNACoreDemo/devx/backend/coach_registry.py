"""
Coach Registry — Single Source of Truth
========================================
Canonical list of all coach roles in ReDNA.
"""

from typing import TypedDict


class CoachRole(TypedDict):
    """Metadata for a single coach role."""
    id: str
    label: str
    filename: str


# All recognized coach roles (even if prompts don't exist yet)
COACH_ROLES: list[CoachRole] = [
    {"id": "head_coach", "label": "Head Coach", "filename": "head_coach_ai.md"},
    {"id": "career_coach", "label": "Career Coach", "filename": "career_coach_ai.md"},
    {"id": "photo_coach", "label": "Photo Coach", "filename": "photo_coach_ai.md"},
    {"id": "padna_coach", "label": "PaDNA Coach", "filename": "padna_coach_ai.md"},
    {"id": "relationship_coach", "label": "Relationship Coach", "filename": "relationship_coach_ai.md"},
    {"id": "permission_coach", "label": "Permission Coach", "filename": "permission_coach_ai.md"},
    {"id": "personality_test_coach", "label": "Personality Test Coach", "filename": "personality_test_coach_ai.md"},
    {"id": "beliefdna_coach", "label": "BeliefDNA Coach", "filename": "beliefdna_coach_ai.md"},
    {"id": "chatdna_coach", "label": "ChatDNA Coach", "filename": "chatdna_coach_ai.md"},
]

# System agents (excluded from Coach Workshop; managed separately)
SYSTEM_AGENTS = {
    "core_ai.md",
    "ucn_rr_ai.md",
}


def get_coach_by_id(coach_id: str) -> CoachRole | None:
    """Look up a coach role by ID."""
    for coach in COACH_ROLES:
        if coach["id"] == coach_id:
            return coach
    return None


def get_default_scaffold(label: str) -> str:
    """Generate a default prompt scaffold for a coach role."""
    return f"""<!-- {label} Prompt Scaffold -->
# {label}

**Purpose:**
Describe the primary purpose of this coach. What domain or user need does it address?

**Boundaries:**
What is explicitly in-scope and out-of-scope for this coach?

**Data Dependencies:**
Which DNA containers, traits, or user data does this coach require?

**Dialogue Tone:**
What personality, voice, and interaction style should this coach use?

**Hand-off Rules:**
When should this coach delegate to another coach (e.g., Head Coach, Photo Coach)?

**Key Responsibilities:**
- Responsibility 1
- Responsibility 2
- Responsibility 3

---

*This is a scaffold template. Replace this content with the actual coach prompt.*
"""
