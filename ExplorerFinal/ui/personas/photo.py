"""Photo Coach persona registration via the shared persona registry."""

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

PERSONA_ID = "photo_coach"

_DEFAULT_STYLE_PRESETS = [
    {
        "id": "evidence_first",
        "label": "Evidence-first",
        "description": "Lead with what the photo clearly shows before speculating.",
    },
    {
        "id": "supportive",
        "label": "Supportive",
        "description": "Blend observations with gentle encouragement and next-step tips.",
    },
    {
        "id": "minimal",
        "label": "Minimal",
        "description": "Only the essentials — rapid triage for analyst review.",
    },
]

_DEFAULT_HANDOFF_INTENTS = [
    {"phrase": "photo coach", "match_type": "contains", "reason": "explicit_call"},
    {"phrase": "photo", "match_type": "contains", "reason": "keyword"},
    {"phrase": "image", "match_type": "contains", "reason": "keyword"},
]

DEFAULT_PHOTO_CONFIG: Dict[str, Any] = {
    "id": PERSONA_ID,
    "version": "0.2.0",
    "name": "Photo Coach",
    "role": "Analyzes uploaded photos and drafts PaDNA descriptors for review.",
    "description": "Reads evidence from photos, flags uncertainties, and keeps writes read-only.",
    "accent_color": "#0F766E",
    "keywords": ["photo", "image", "visual", "avatar"],
    "vibe": {"keywords": ["observant", "methodical", "grounded"], "energy": "medium"},
    "honesty": {"mode": "gentle", "allowed_ranges": ["gentle", "balanced"]},
    "tone": {
        "baseline": "observant and methodical",
        "escalations": {"safety": "calm compliance", "validation": "warm clarity"},
    },
    "honesty_contract": {
        "default": "consent_aligned",
        "overrides": {"evidence_missing": "balanced", "privacy_risk": "direct"},
    },
    "data_dependencies": {
        "bundle": ["photo.pending_descriptors"],
        "session": ["photo.upload_metadata"],
        "optional": ["padna.traits.visual_palette"],
    },
    "prompt_assets": {
        "system": "prompts/photo_coach_ai.md",
        "dialogue_templates": [],
        "micro_actions": [],
        "evaluations": [],
    },
    "ui_hooks": {"persona_card": "PhotoCoachCard", "micro_action_stream": None},
    "rr_contract": {"base_increment": 0.0, "contradiction_escalation": 0.0},
    "consent_requirements": {"needs_partner_opt_in": False, "share_scope": "self_only"},
    "lifecycle": {"beta": True, "requires_head_coach_supervision": True},
    "registration": {
        "id": PERSONA_ID,
        "version": "1.0.0",
        "display_name": "Photo Coach",
        "greeting_template": "I’ll review the photos and call out descriptors worth checking.",
        "handoff_intents": _DEFAULT_HANDOFF_INTENTS,
        "style_presets": _DEFAULT_STYLE_PRESETS,
        "style_defaults": {
            "tone": "Neutral",
            "formality": 62,
            "warmth": 34,
            "directness": 58,
            "micro": ["example"],
        },
        "metrics_keys": ["photo_descriptors", "raw_candidates"],
    },
}


def _descriptor_factory(config):  # pragma: no cover - Streamlit dependent
    from ..coach_orchestrator import build_photo_body_renderer
    from ..persona_bus import PersonaDescriptor, register_persona as register_descriptor

    descriptor = PersonaDescriptor(
        id=config.id,
        title="Photo Coach",
        icon="📸",
        color=config.accent_color,
        description=config.description,
        render_panel=build_photo_body_renderer("persona_photo"),
    )
    register_descriptor(descriptor, overwrite=True)


def _card_factory(config):  # pragma: no cover - Streamlit dependent
    return {
        "id": config.id,
        "title": "Photo Coach",
        "accent": config.accent_color,
        "icon": "🖼️",
        "tagline": "Observes photos under consent guardrails",
        "description": "Extracts visual descriptors without writing directly to Core.",
    }


_REGISTERED = False


def ensure_registered(*, auto_create_assets: bool = True) -> bool:
    """Ensure the Photo Coach persona is registered with the shared registry."""

    global _REGISTERED
    if _REGISTERED:
        return True
    if _IMPORT_ERROR is not None or persona_registry is None:
        return False

    payload = dict(DEFAULT_PHOTO_CONFIG)
    try:
        validate_persona_config(payload)
    except PersonaValidationError:
        return False

    if auto_create_assets and ensure_persona_assets is not None:
        try:
            ensure_persona_assets(PERSONA_ID)
        except Exception:  # pragma: no cover - best effort asset check
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

__all__ = ["DEFAULT_PHOTO_CONFIG", "ensure_registered", "register", "PERSONA_ID"]
