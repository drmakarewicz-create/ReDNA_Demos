from __future__ import annotations

from typing import Dict, Optional

from ..persona_bus import PersonaDescriptor, register_persona
from ..persona_cards_registry import register_card

_REGISTERED = False


def _enter(_: str, metadata: Optional[Dict[str, str]]) -> None:
    # Placeholder hook for future analytics; intentionally empty for now.
    return


def register() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    descriptor = PersonaDescriptor(
        id="head_coach",
        title="Head Coach",
        icon="🧠",
        color="#1F2933",
        description="Primary orchestrator and default persona.",
        on_enter=_enter,
    )
    register_persona(descriptor, overwrite=_REGISTERED)
    register_card({
        "id": "head_coach",
        "title": "Head Coach",
        "accent": "#1F2933",
        "icon": "🧠",
        "tagline": "Primary orchestrator",
        "description": "Routes intent, blends suggestions, keeps plan coherence.",
    })
    _REGISTERED = True


register()

__all__ = ["register"]
