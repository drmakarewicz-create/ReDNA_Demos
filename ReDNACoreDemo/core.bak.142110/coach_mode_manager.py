"""
Coach Mode Manager
==================

Manages user's active coach mode and handles mode transitions.

TERMINOLOGY:
- **Coach Modes**: Functional specializations (head_coach, photo, relationship)
- **Mode Switching**: Transitioning between coach modes with context handoff
- **CReDNA** (Future): Per-user coach personality customization

CReDNA COMPATIBILITY:
- Mode state stored per-user (future: load user's CReDNA profile for each mode)
- Mode metadata extensible (can add credna_profile_id later)
- Transition hooks allow CReDNA personality loading
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid coach modes
VALID_MODES = {"head_coach", "photo", "relationship", "photo_coach", "relationship_coach", "career_coach", "personality_test_coach", "padna", "padna_coach", "chatdna_coach", "beliefdna_coach", "permission_coach"}

# Display names for modes
MODE_DISPLAY_NAMES = {
    "head_coach": "Head Coach",
    "photo": "Photo Coach",
    "photo_coach": "Photo Coach",
    "relationship": "Relationship Coach",
    "relationship_coach": "Relationship Coach",
    "career_coach": "Career Coach",
    "personality_test_coach": "Personality Test Coach",
    "padna": "PaDNA Coach",
    "padna_coach": "PaDNA Coach",
    "chatdna_coach": "ChatDNA Coach",
    "beliefdna_coach": "BeliefDNA Coach",
    "permission_coach": "Permission Coach",
}

# Mode capabilities
MODE_CAPABILITIES = {
    "head_coach": {
        "namespaces": ["CogDNA", "GenDNA", "*"],
        "description": "Strategic guidance across all DNA domains",
        "emoji": "🧠",
    },
    "photo": {
        "namespaces": ["PaDNA"],
        "description": "Visual trait analysis and PaDNA refinement",
        "emoji": "📸",
    },
    "photo_coach": {
        "namespaces": ["PaDNA"],
        "description": "Visual trait analysis and PaDNA refinement",
        "emoji": "📸",
    },
    "relationship": {
        "namespaces": ["ReDNA", "PsyDNA", "EmDNA"],
        "description": "Relationship patterns and emotional dynamics",
        "emoji": "💝",
    },
    "relationship_coach": {
        "namespaces": ["ReDNA", "PsyDNA", "EmDNA"],
        "description": "Relationship patterns and emotional dynamics",
        "emoji": "💞",
    },
    "career_coach": {
        "namespaces": ["SkillDNA", "ProfDNA", "BehDNA"],
        "description": "Career development, skill optimization, and professional growth",
        "emoji": "💼",
    },
    "personality_test_coach": {
        "namespaces": ["PsyDNA", "BehDNA"],
        "description": "Personality assessment and psychological profiling",
        "emoji": "🧠",
    },
    "padna": {
        "namespaces": ["PaDNA"],
        "description": "Physical appearance DNA and aesthetic profiling",
        "emoji": "🧬",
    },
    "padna_coach": {
        "namespaces": ["PaDNA"],
        "description": "Physical appearance DNA and aesthetic profiling",
        "emoji": "🧬",
    },
    "chatdna_coach": {
        "namespaces": ["LanguageStyleDNA", "PsyDNA", "SocDNA"],
        "description": "Conversational style simulation and ChatDNA analysis",
        "emoji": "💬",
    },
    "beliefdna_coach": {
        "namespaces": ["BeliefValueDNA", "MotivationDNA", "CogDNA", "PsyDNA", "EmDNA"],
        "description": "Philosophical reasoning and belief simulation",
        "emoji": "🤔",
    },
    "permission_coach": {
        "namespaces": [],  # Special: Has system access but does not own namespaces
        "description": "Consent mediation and privacy protection",
        "emoji": "🔐",
    },
}


class CoachModeManager:
    """Manages user's active coach mode."""

    def __init__(self, data_dir: Path):
        """
        Initialize coach mode manager.

        Args:
            data_dir: Root data directory
        """
        self.data_dir = data_dir

    def get_active_mode(self, user_id: str) -> str:
        """
        Get user's current active coach mode.

        Args:
            user_id: User identifier

        Returns:
            Active mode (defaults to "head_coach" if not set)
        """
        mode_file = self._get_mode_file(user_id)

        if not mode_file.exists():
            return "head_coach"  # Default mode

        try:
            with open(mode_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("active_mode", "head_coach")
        except Exception as e:
            logger.warning(f"Error reading mode file for {user_id}: {e}")
            return "head_coach"

    def set_active_mode(
        self,
        user_id: str,
        mode: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Set user's active coach mode.

        Args:
            user_id: User identifier
            mode: New mode to activate
            context: Optional context (delegation_id, reason, etc.)

        Returns:
            True if successful
        """
        if mode not in VALID_MODES:
            logger.error(f"Invalid mode: {mode}")
            return False

        mode_file = self._get_mode_file(user_id)
        mode_file.parent.mkdir(parents=True, exist_ok=True)

        context = context or {}

        try:
            # Load existing data or create new
            if mode_file.exists():
                with open(mode_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}

            # Track mode history
            previous_mode = data.get("active_mode", "head_coach")
            if "mode_history" not in data:
                data["mode_history"] = []

            # Add transition record
            data["mode_history"].append({
                "from_mode": previous_mode,
                "to_mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": context,
            })

            # Keep last 100 transitions
            data["mode_history"] = data["mode_history"][-100:]

            # Update active mode
            data["active_mode"] = mode
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Save
            with open(mode_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(f"User {user_id} switched: {previous_mode} → {mode}")
            return True

        except Exception as e:
            logger.error(f"Error setting mode for {user_id}: {e}")
            return False

    def get_mode_info(self, mode: str) -> Dict[str, Any]:
        """
        Get information about a coach mode.

        Args:
            mode: Mode identifier

        Returns:
            Dict with display_name, capabilities, emoji, etc.
        """
        if mode not in VALID_MODES:
            return {
                "mode": mode,
                "display_name": mode,
                "valid": False,
            }

        capabilities = MODE_CAPABILITIES.get(mode, {})

        return {
            "mode": mode,
            "display_name": MODE_DISPLAY_NAMES.get(mode, mode),
            "emoji": capabilities.get("emoji", "🤖"),
            "description": capabilities.get("description", ""),
            "namespaces": capabilities.get("namespaces", []),
            "valid": True,
        }

    def get_mode_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get user's mode switching history.

        Args:
            user_id: User identifier
            limit: Maximum number of transitions to return

        Returns:
            List of mode transition records
        """
        mode_file = self._get_mode_file(user_id)

        if not mode_file.exists():
            return []

        try:
            with open(mode_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            history = data.get("mode_history", [])
            return history[-limit:]

        except Exception as e:
            logger.warning(f"Error reading mode history for {user_id}: {e}")
            return []

    def get_mode_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get statistics about user's mode usage.

        Args:
            user_id: User identifier

        Returns:
            Dict with mode usage stats
        """
        history = self.get_mode_history(user_id, limit=1000)

        if not history:
            return {
                "total_transitions": 0,
                "mode_counts": {},
                "current_mode": "head_coach",
            }

        # Count transitions per mode
        mode_counts = {}
        for transition in history:
            to_mode = transition.get("to_mode", "head_coach")
            mode_counts[to_mode] = mode_counts.get(to_mode, 0) + 1

        return {
            "total_transitions": len(history),
            "mode_counts": mode_counts,
            "current_mode": self.get_active_mode(user_id),
            "most_used_mode": max(mode_counts.items(), key=lambda x: x[1])[0] if mode_counts else "head_coach",
        }

    def _get_mode_file(self, user_id: str) -> Path:
        """Get path to user's mode state file."""
        return self.data_dir / "users" / user_id / "coach_mode.json"


def switch_mode_with_handoff(
    user_id: str,
    target_mode: str,
    data_dir: Path,
    delegation_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Switch coach mode with conversation context handoff.

    Args:
        user_id: User identifier
        target_mode: Mode to switch to
        data_dir: Root data directory
        delegation_id: Optional delegation ID triggering this switch
        context: Additional context

    Returns:
        Dict with success, previous_mode, new_mode, message
    """
    manager = CoachModeManager(data_dir)

    previous_mode = manager.get_active_mode(user_id)

    if previous_mode == target_mode:
        return {
            "success": True,
            "previous_mode": previous_mode,
            "new_mode": target_mode,
            "message": f"Already in {MODE_DISPLAY_NAMES.get(target_mode, target_mode)} mode",
            "no_change": True,
        }

    # Prepare context
    switch_context = context or {}
    if delegation_id:
        switch_context["delegation_id"] = delegation_id
        switch_context["reason"] = "delegation"
    else:
        switch_context["reason"] = "manual_switch"

    # Perform mode switch
    success = manager.set_active_mode(user_id, target_mode, switch_context)

    if not success:
        return {
            "success": False,
            "error": "Failed to switch modes",
            "previous_mode": previous_mode,
            "new_mode": target_mode,
        }

    # Get mode info
    new_mode_info = manager.get_mode_info(target_mode)

    return {
        "success": True,
        "previous_mode": previous_mode,
        "new_mode": target_mode,
        "mode_info": new_mode_info,
        "message": f"Switched from {MODE_DISPLAY_NAMES.get(previous_mode, previous_mode)} to {new_mode_info['display_name']}",
        "no_change": False,
    }


def build_behavior_context(user_id: str, coach_id: str) -> Dict[str, Any]:
    """
    Build behavior context from per-user feature state for a coach.

    Reads feature_state/<coach_id>.json and maps UI values to
    behavior hints for prompt injection.

    PHASE 3B ENHANCEMENT: Merges learning state from hc_learning module
    to adaptively adjust tone, creativity, and focus based on Life OS analytics.

    Mapping rules:
    - tone (select): lowercase for prompt keywords
    - creativity (slider 0-100): normalize to creativity_bias (0-1)
    - insights_enabled (switch): boolean pass-through
    - Unknown keys: copy to features only (no hints)

    Learning state (if available) overrides or augments hints:
    - tone_bias → adjusts empathy level
    - creativity_bias → exploration encouragement
    - focus_weights → priority area hints
    - nudge_frequency_multiplier → suggestion cadence

    Returns:
        {
            "features": { ...raw values... },
            "hints": {
                "tone": "empathetic",
                "creativity_bias": 0.7,
                "insights_enabled": true
            },
            "learning": { ...learning state context... }  # Phase 3b
        }
    """
    from .storage import USERS_DIR

    state_file = USERS_DIR / user_id / "feature_state" / f"{coach_id}.json"

    # Default empty context
    if not state_file.exists():
        context = {
            "features": {},
            "hints": {}
        }
    else:
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)

            values = state.get("values", {})

            # Build hints with heuristic mapping
            hints = {}

            for key, value in values.items():
                # Tone: lowercase for prompt keywords
                if key == "tone" and isinstance(value, str):
                    hints["tone"] = value.lower()

                # Creativity: normalize 0-100 to 0-1
                elif key == "creativity" and isinstance(value, (int, float)):
                    hints["creativity_bias"] = round(value / 100.0, 2)

                # Boolean toggles: pass through
                elif key.endswith("_enabled") and isinstance(value, bool):
                    hints[key] = value

                # Unknown: skip hints (will be in features only)

            context = {
                "features": values,
                "hints": hints
            }

        except Exception as e:
            logger.error(f"Error building behavior context for {coach_id}, user {user_id}: {e}")
            context = {
                "features": {},
                "hints": {}
            }

    # Phase 3b: Merge learning state for head_coach
    if coach_id == "head_coach":
        try:
            from . import hc_learning
            learning_context = hc_learning.get_behavior_context(user_id)

            if learning_context:
                context["learning"] = learning_context

                # Override/augment hints with learning adaptations
                if "tone" in learning_context:
                    # Learning takes precedence over manual settings
                    context["hints"]["tone"] = learning_context["tone"]

                if "creativity" in learning_context:
                    # Blend learning creativity with manual settings
                    manual_creativity = context["hints"].get("creativity_bias", 0.5)
                    learning_creativity = learning_context["raw_state"]["creativity_bias"]
                    # 70% learning, 30% manual
                    context["hints"]["creativity_bias"] = round(
                        learning_creativity * 0.7 + manual_creativity * 0.3, 2
                    )

                # Add nudge frequency hint
                if "nudge_frequency_multiplier" in learning_context:
                    context["hints"]["nudge_frequency"] = learning_context["nudge_frequency_multiplier"]

        except ImportError:
            # hc_learning not available (e.g., in tests)
            pass
        except Exception as e:
            logger.warning(f"Could not load learning context for {user_id}: {e}")

    return context


def inject_behavior_context_into_prompt(prompt: str, behavior_context: Dict[str, Any]) -> str:
    """
    Appends a human-readable runtime context summary to a system prompt.

    Args:
        prompt: Base system prompt text
        behavior_context: Dict with 'features' and 'hints' keys

    Returns:
        Modified prompt with RUNTIME BEHAVIOR CONTEXT section appended
    """
    hints = behavior_context.get("hints", {})

    # Only inject if there are hints
    if not hints:
        return prompt

    context_section = "\n\n=== RUNTIME BEHAVIOR CONTEXT ===\n"

    for key, value in hints.items():
        if isinstance(value, bool):
            context_section += f"{key}: {str(value).lower()}\n"
        elif isinstance(value, (int, float)):
            context_section += f"{key}: {value}\n"
        else:
            context_section += f"{key}: {value}\n"

    context_section += "================================\n"

    return prompt + context_section



def get_curiosity_agenda(user_id: str, limit: int = 8) -> dict:
    """
    Get a prioritized curiosity agenda for the user.

    This is a convenience helper for Head Coach to request "what should we ask/collect next?"
    based on gap analysis, coach performance, and exploration strategy.

    Args:
        user_id: User identifier
        limit: Maximum number of items in the agenda

    Returns:
        Agenda dict with ranked items (target, priority, reason, suggested_coach, etc.)
    """
    try:
        from .curiosity.curiosity_engine_v2 import CuriosityEngine
        from .storage import CORE_DATA_ROOT
        from datetime import datetime, timezone

        engine = CuriosityEngine(data_root=CORE_DATA_ROOT)
        agenda = engine.generate_agenda(user_id=user_id, limit=limit)

        logger.info(f"Generated curiosity agenda for {user_id}: {len(agenda.get('items', []))} items")
        return agenda

    except Exception as e:
        logger.error(f"Failed to generate curiosity agenda for {user_id}: {e}", exc_info=True)
        # Return empty agenda on error
        return {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": [],
            "error": str(e),
        }


def is_what_next_query(text: str) -> bool:
    """
    Detect if user message is asking "what next?" for proactive nudging.

    Args:
        text: User's message text

    Returns:
        True if message indicates user wants suggestions
    """
    text_lower = text.lower().strip()

    # Direct "what next" patterns
    what_next_patterns = [
        "what next",
        "what should we do",
        "what should i do",
        "what now",
        "any ideas",
        "what else",
        "suggest something",
        "what do you suggest",
        "what would you suggest",
        "where should we start",
        "what should we explore",
        "what should we work on",
    ]

    for pattern in what_next_patterns:
        if pattern in text_lower:
            return True

    # Short ambiguous queries (< 10 chars often indicate uncertainty)
    if len(text_lower) < 10 and text_lower in ["?", "what?", "next?", "now?", "ideas?", "help?"]:
        return True

    return False

