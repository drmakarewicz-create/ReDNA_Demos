"""
CReDNA Persona Synthesis Engine v0.2
====================================

Per-user, per-coach personality envelopes with:
- Layered blending: role_overlay → user_style → deltas → prefs
- Lazy materialization (files created only when training happens)
- Natural training (feedback ratings) + Manual fine-tuning (sliders/chips)
- Privacy-aware (consent gates on sensitive traits)
- Fast caching (TTL + bust logic)

Usage:
    from core.credna.persona_synthesis import build_envelope

    envelope = build_envelope(
        user_id="TEST",
        coach_id="career_coach",
        intent="supportive"
    )
"""

__version__ = "0.2.0"
