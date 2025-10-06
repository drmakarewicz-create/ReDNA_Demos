from __future__ import annotations

from pathlib import Path

import pytest

from shared.persona_schema import PersonaHooks

from ReDNACoreDemo.core import persona_registry
from ReDNACoreDemo.ai import prompt_registry as prompt_reg
from ExplorerFinal.ui import persona_cards_registry
from ExplorerFinal.ui import persona_router
from ExplorerFinal.ui import persona_bus


@pytest.fixture(autouse=True)
def _reset_persona_env():
    persona_registry.clear_registry()
    persona_cards_registry.clear_cards()
    persona_bus.reset(optional=True)
    persona_router.load_personas.cache_clear()  # type: ignore[attr-defined]
    yield
    persona_registry.clear_registry()
    persona_cards_registry.clear_cards()
    persona_bus.reset(optional=True)
    persona_router.load_personas.cache_clear()  # type: ignore[attr-defined]


def test_registers_relationship_persona(tmp_path: Path):
    system_file = tmp_path / "rc_system.md"
    system_file.write_text("You are the Relationship Coach.", encoding="utf-8")
    dialogue_file = tmp_path / "rc_opening.md"
    dialogue_file.write_text("Opening line", encoding="utf-8")
    micro_file = tmp_path / "rc_micro.md"
    micro_file.write_text("Ask for a 2-minute check-in.", encoding="utf-8")

    config = {
        "id": "test_relationship_coach",
        "version": "0.0.1",
        "name": "Relationship Coach",
        "role": "Supports partnership reflection.",
        "accent_color": "#8FBFE0",
        "keywords": ["relationship"],
        "description": "Test persona for relationship guidance.",
        "vibe": {"keywords": ["empathetic"], "energy": "medium"},
        "honesty": {"mode": "balanced", "allowed_ranges": ["gentle", "balanced"]},
        "tone": {"baseline": "warm", "escalations": {}},
        "honesty_contract": {"default": "consent_aligned", "overrides": {}},
        "data_dependencies": {
            "bundle": ["padna.traits.relationship_history"],
            "session": ["onboarding.relationship_status"],
            "optional": [],
        },
        "prompt_assets": {
            "system": str(system_file),
            "dialogue_templates": [str(dialogue_file)],
            "micro_actions": [str(micro_file)],
            "evaluations": [],
        },
        "ui_hooks": {"persona_card": "RelationshipCoachCard", "micro_action_stream": None},
        "rr_contract": {"base_increment": 1.0, "contradiction_escalation": 0.5},
        "consent_requirements": {"needs_partner_opt_in": False, "share_scope": "self_only"},
        "lifecycle": {"beta": True, "requires_head_coach_supervision": True},
    }

    persona_registry.register_persona(config, hooks=PersonaHooks())

    stored = persona_registry.get_persona("test_relationship_coach")
    assert stored is not None
    assert stored.name == "Relationship Coach"

    bundle = prompt_reg.get_persona_bundle("test_relationship_coach")
    assert bundle is not None
    assert "Relationship Coach" in bundle.system

    card = persona_cards_registry.get_card("test_relationship_coach")
    assert card is not None
    assert card.accent == "#8FBFE0"

    persona_router.load_personas.cache_clear()  # type: ignore[attr-defined]
    persona = persona_router.get_persona("test_relationship_coach")
    assert persona is not None
    assert persona["prompt"].startswith("You are the Relationship Coach")
    assert persona["rr_contract"]["base_increment"] == 1.0
