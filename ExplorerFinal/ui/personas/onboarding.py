from __future__ import annotations

from typing import Any, Dict, Optional

from .. import onboarding as onboarding_ui
from ..onboarding_state import ensure_state, onboarding_active, start_onboarding
from ..persona_bus import PersonaDescriptor, register_persona
from ..persona_cards_registry import register_card

_REGISTERED = False


def _render_panel(user_id: str) -> None:
    onboarding_ui.render_onboarding_panel(user_id)


def _render_sidebar(user_id: str) -> None:
    onboarding_ui.render_sidebar_controls(user_id)


def _ensure_started(user_id: Optional[str]) -> None:
    if not user_id:
        return
    ensure_state(user_id)
    if not onboarding_active(user_id):
        start_onboarding(user_id)


def _on_enter(_: str, metadata: Optional[Dict[str, Any]]) -> None:
    user_id = (metadata or {}).get("user_id") if metadata else None
    _ensure_started(user_id)


def register() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    descriptor = PersonaDescriptor(
        id="onboarding",
        title="Onboarding Coach",
        icon="🛫",
        color="#2563EB",
        description="Guides first-time setup with quick picks and consent reminders.",
        render_panel=_render_panel,
        render_sidebar=_render_sidebar,
        on_enter=_on_enter,
    )
    register_persona(descriptor, overwrite=_REGISTERED)
    register_card({
        "id": "onboarding",
        "title": "Onboarding Coach",
        "accent": "#2563EB",
        "icon": "🛫",
        "tagline": "Guides first-time setup",
        "description": "Quick picks, consent reminders, and setup nudges.",
        "dev_only": False,
    })
    _REGISTERED = True


register()

__all__ = ["register"]
