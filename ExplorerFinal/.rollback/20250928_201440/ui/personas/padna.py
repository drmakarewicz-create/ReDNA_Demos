"""PaDNA Outbound Coach persona registration via the shared registry."""

from __future__ import annotations

from typing import Any, Dict

from shared.persona_schema import PersonaHooks, PersonaValidationError, validate_persona_config

try:
    from ReDNACoreDemo.core import persona_registry
    from ReDNACoreDemo.ai.prompt_registry import ensure_persona_assets
except Exception as exc:  # pragma: no cover - optional dependency guard
    persona_registry = None  # type: ignore
    ensure_persona_assets = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

PERSONA_ID = "padna_coach"

_DEFAULT_STYLE_PRESETS = [
    {
        "id": "storyteller",
        "label": "Storyteller",
        "description": "Rich narrative copy with light sensory details for outbound decks.",
    },
    {
        "id": "brand_safe",
        "label": "Brand-safe",
        "description": "Polished tone with explicit consent reminders and caveats.",
    },
    {
        "id": "high_energy",
        "label": "High Energy",
        "description": "Upbeat, launch-ready flavour for social or campaign teasers.",
    },
]

_DEFAULT_HANDOFF_INTENTS = [
    {"phrase": "padna coach", "match_type": "contains", "reason": "explicit_call"},
    {"phrase": "outbound coach", "match_type": "contains", "reason": "keyword"},
    {"phrase": "avatar coach", "match_type": "contains", "reason": "keyword"},
]

DEFAULT_PADNA_CONFIG: Dict[str, Any] = {
    "id": PERSONA_ID,
    "version": "0.2.0",
    "name": "PaDNA Outbound Coach",
    "role": "Packages confirmed PaDNA descriptors into outbound-ready avatars.",
    "description": "Turns confirmed PaDNA into shareable personas while honouring consent rules.",
    "accent_color": "#7C3AED",
    "keywords": ["padna", "avatar", "outbound", "render"],
    "vibe": {"keywords": ["creative", "transparent", "playful"], "energy": "medium"},
    "honesty": {"mode": "balanced", "allowed_ranges": ["gentle", "balanced", "direct"]},
    "tone": {
        "baseline": "creative and transparent",
        "escalations": {"gap": "candid checklist", "launch": "energetic pitch"},
    },
    "honesty_contract": {
        "default": "consent_aligned",
        "overrides": {"missing_data": "direct", "branding": "balanced"},
    },
    "data_dependencies": {
        "bundle": ["padna.confirmed_descriptors"],
        "session": ["padna.outbound_preferences"],
        "optional": ["padna.visual_palette", "photo.pending_descriptors"],
    },
    "prompt_assets": {
        "system": "prompts/padna_coach_ai.md",
        "dialogue_templates": [],
        "micro_actions": [],
        "evaluations": [],
    },
    "ui_hooks": {"persona_card": "PadnaCoachCard", "micro_action_stream": None},
    "rr_contract": {"base_increment": 0.0, "contradiction_escalation": 0.0},
    "consent_requirements": {"needs_partner_opt_in": False, "share_scope": "self_only"},
    "lifecycle": {"beta": True, "requires_head_coach_supervision": True},
    "registration": {
        "id": PERSONA_ID,
        "version": "1.0.0",
        "display_name": "PaDNA Outbound Coach",
        "greeting_template": "Let’s turn confirmed traits into an outbound-ready avatar.",
        "handoff_intents": _DEFAULT_HANDOFF_INTENTS,
        "style_presets": _DEFAULT_STYLE_PRESETS,
        "style_defaults": {
            "tone": "Neutral",
            "formality": 52,
            "warmth": 60,
            "directness": 48,
            "micro": ["next_step"],
        },
        "metrics_keys": ["outbound_variations", "export_requests"],
    },
}


def _descriptor_factory(config):  # pragma: no cover - Streamlit dependent
    from ..coach_orchestrator import build_padna_body_renderer
    from ..persona_bus import PersonaDescriptor, register_persona as register_descriptor

    descriptor = PersonaDescriptor(
        id=config.id,
        title="PaDNA Coach",
        icon="🎨",
        color=config.accent_color,
        description=config.description,
        render_panel=build_padna_body_renderer("persona_padna"),
    )
    register_descriptor(descriptor, overwrite=True)


def _card_factory(config):  # pragma: no cover - Streamlit dependent
    return {
        "id": config.id,
        "title": "PaDNA Outbound Coach",
        "accent": "#F59E0B",
        "icon": "📦",
        "tagline": "Transforms confirmed PaDNA into outbound assets",
        "description": "Turns confirmed descriptors into outbound avatar packages with provenance.",
    }


_REGISTERED = False


def ensure_registered(*, auto_create_assets: bool = True) -> bool:
    """Ensure the PaDNA Outbound Coach persona is registered."""

    global _REGISTERED
    if _REGISTERED:
        return True
    if _IMPORT_ERROR is not None or persona_registry is None:
        return False

    payload = dict(DEFAULT_PADNA_CONFIG)
    try:
        validate_persona_config(payload)
    except PersonaValidationError:
        return False

    if auto_create_assets and ensure_persona_assets is not None:
        try:
            ensure_persona_assets(PERSONA_ID)
        except Exception:  # pragma: no cover - asset guard
            pass

    hooks = PersonaHooks(
        descriptor_factory=_descriptor_factory,
        card_factory=_card_factory,
    )
    persona_registry.register_persona(payload, hooks=hooks)
    _REGISTERED = True
    return True


def register() -> bool:  # backwards compatibility alias
    return ensure_registered()


ensure_registered()

__all__ = ["DEFAULT_PADNA_CONFIG", "ensure_registered", "register", "PERSONA_ID"]
