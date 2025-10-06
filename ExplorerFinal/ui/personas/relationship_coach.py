"""Default registration helpers for the Relationship Coach persona."""

from __future__ import annotations

from typing import Any, Dict

from shared.persona_schema import PersonaHooks, PersonaValidationError, validate_persona_config

try:  # pragma: no cover - Streamlit-only import during UI runtime
    from ..persona_bus import PersonaDescriptor, register_persona as _register_bus_descriptor
    from ..persona_cards_registry import register_card as _register_persona_card
except Exception:  # pragma: no cover - tolerates missing UI deps during bootstrapping
    PersonaDescriptor = None  # type: ignore
    _register_bus_descriptor = None  # type: ignore
    _register_persona_card = None  # type: ignore

try:
    from ReDNACoreDemo.core import persona_registry
    from ReDNACoreDemo.ai.prompt_registry import ensure_persona_assets
except Exception as exc:  # pragma: no cover - runtime guard for optional deps
    persona_registry = None  # type: ignore
    ensure_persona_assets = None  # type: ignore
    _IMPORT_ERROR = exc
else:  # pragma: no cover - used at runtime only
    _IMPORT_ERROR = None

PERSONA_ID = "relationship_coach"

_REGISTERED = False
_BUS_WIRED = False

DEFAULT_RC_CONFIG: Dict[str, Any] = {
    "id": PERSONA_ID,
    "version": "0.1.0",
    "name": "Relationship Coach",
    "role": "Guides relationship reflection and micro-actions.",
    "description": "Balances empathy and clarity to improve connection readiness.",
    "accent_color": "#8FBFE0",
    "keywords": ["relationship", "partner", "communication", "intimacy", "synergy"],
    "vibe": {"keywords": ["empathetic", "adventurous", "wise"], "energy": "medium"},
    "honesty": {"mode": "balanced", "allowed_ranges": ["gentle", "balanced", "direct"]},
    "tone": {
        "baseline": "warm and measured",
        "escalations": {"motivation": "adventurous spark", "risk": "calm clarity"},
    },
    "honesty_contract": {
        "default": "consent_aligned",
        "overrides": {"crisis": "direct", "celebration": "upbeat"},
    },
    "data_dependencies": {
        "bundle": [
            "padna.traits.relationship_history",
            "padna.traits.communication_style",
            "social.traits.love_languages",
        ],
        "session": [
            "onboarding.orientation",
            "onboarding.relationship_status",
            "onboarding.vibe",
        ],
        "optional": ["resolved.partner_conflict_map"],
    },
    "prompt_assets": {
        "system": "prompts/relationship_coach/system.md",
        "dialogue_templates": [
            "prompts/relationship_coach/opening.md",
            "prompts/relationship_coach/microactions.md",
            "prompts/relationship_coach/response_templates.md",
            "prompts/relationship_coach/tone_filter.md",
        ],
        "micro_actions": [],
        "evaluations": [],
    },
    "ui_hooks": {"persona_card": "RelationshipCoachCard", "micro_action_stream": "rc_micro_feed"},
    "rr_contract": {"base_increment": 1.2, "contradiction_escalation": 0.6},
    "consent_requirements": {"needs_partner_opt_in": False, "share_scope": "self_only"},
    "lifecycle": {"beta": True, "requires_head_coach_supervision": True},
    "registration": {
        "id": PERSONA_ID,
        "version": "1.0.0",
        "display_name": "Relationship Coach",
        "greeting_template": "I'm here to help you two reconnect. Tell me what's on your mind.",
        "handoff_intents": [
            {"phrase": "relationship coach", "match_type": "contains", "reason": "explicit_call"},
            {"phrase": "relationship", "match_type": "contains", "reason": "keyword"},
            {"phrase": "partner", "match_type": "contains", "reason": "keyword"},
            {"phrase": "rc", "match_type": "contains", "reason": "alias"},
        ],
        "style_presets": [
            {
                "id": "gentle",
                "label": "Gentle Warmth",
                "description": "Softer tone, extra validation before suggesting actions.",
            },
            {
                "id": "direct",
                "label": "Direct Clarity",
                "description": "Crisp feedback with firm but caring boundaries.",
            },
            {
                "id": "cheerleader",
                "label": "Cheerleader",
                "description": "High-energy encouragement with playful metaphors.",
            },
        ],
        "style_defaults": {
            "tone": "Gentle",
            "formality": 45,
            "warmth": 72,
            "directness": 38,
            "micro": ["next_step", "summary"],
        },
        "metrics_keys": ["rr", "ucn", "connection_readiness"],
    },
}


def _ensure_bus_descriptor(accent_color: str, description: str) -> None:
    """Register bus metadata so persona activation never 404s."""

    global _BUS_WIRED
    if _BUS_WIRED or _register_bus_descriptor is None or PersonaDescriptor is None:
        return

    try:
        descriptor = PersonaDescriptor(
            id=PERSONA_ID,
            title="Relationship Coach",
            icon="💞",
            color=accent_color,
            description=description,
        )
        _register_bus_descriptor(descriptor, overwrite=True)
    except Exception:
        return

    if _register_persona_card is not None:
        try:
            _register_persona_card(
                {
                    "id": PERSONA_ID,
                    "title": "Relationship Coach",
                    "accent": accent_color,
                    "icon": "💞",
                    "tagline": "Guides relationship reflection and micro-actions.",
                    "description": description,
                    "keywords": ["relationship", "connection", "partner"],
                    "beta": True,
                }
            )
        except Exception:
            pass

    _BUS_WIRED = True


def _descriptor_factory(config):  # pragma: no cover - Streamlit dependent wiring
    accent = getattr(config, "accent_color", DEFAULT_RC_CONFIG.get("accent_color", "#8FBFE0"))
    description = getattr(config, "description", DEFAULT_RC_CONFIG.get("description", ""))
    _ensure_bus_descriptor(accent, description)


def _card_factory(config):  # pragma: no cover - Streamlit dependent wiring
    return {
        "id": PERSONA_ID,
        "title": "Relationship Coach",
        "accent": getattr(config, "accent_color", DEFAULT_RC_CONFIG.get("accent_color", "#8FBFE0")),
        "icon": "💞",
        "tagline": getattr(config, "role", "Guides relationship reflection and micro-actions."),
        "description": getattr(config, "description", DEFAULT_RC_CONFIG.get("description", "")),
        "keywords": getattr(config, "keywords", DEFAULT_RC_CONFIG.get("keywords", [])),
        "beta": True,
    }


def ensure_registered(*, auto_create_assets: bool = True) -> bool:
    """Ensure the Relationship Coach persona exists in the registry and UI bus."""

    global _REGISTERED

    if _REGISTERED:
        return True

    # Always wire the UI bus first so persona activation never fails, even if the
    # backing Core registry is offline (e.g. snapshots or minimal demos).
    _ensure_bus_descriptor(
        DEFAULT_RC_CONFIG.get("accent_color", "#8FBFE0"),
        DEFAULT_RC_CONFIG.get("description", ""),
    )

    if _IMPORT_ERROR is not None or persona_registry is None:
        return _BUS_WIRED

    if persona_registry.get_persona(PERSONA_ID):
        _REGISTERED = True
        return True

    payload = dict(DEFAULT_RC_CONFIG)
    try:
        validate_persona_config(payload)
    except PersonaValidationError:
        return False

    if auto_create_assets and ensure_persona_assets is not None:
        try:
            ensure_persona_assets(PERSONA_ID)
        except Exception:  # pragma: no cover - asset creation is best effort
            pass

    hooks = PersonaHooks(
        descriptor_factory=_descriptor_factory if _register_bus_descriptor else None,
        card_factory=_card_factory if _register_persona_card else None,
    )
    persona_registry.register_persona(payload, hooks=hooks)
    _REGISTERED = True
    return True


def register() -> bool:
    return ensure_registered()


ensure_registered(auto_create_assets=True)


__all__ = ["DEFAULT_RC_CONFIG", "ensure_registered", "PERSONA_ID", "register"]
