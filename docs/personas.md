# Persona Registry Quickstart

The persona registry lets you add modular coaches without editing the Head Coach UI. Each persona supplies a validated config and prompt bundle.

## 1. Create prompt assets

Place all prompt markdown files under `prompts/<persona_id>/`. The system prompt is required; dialogue templates, micro-actions, and evaluations are optional.

```
prompts/relationship_coach/system.md
prompts/relationship_coach/opening.md
prompts/relationship_coach/microactions.md
```

## 2. Draft the config

Author a JSON (or Python dict) that matches `shared.persona_schema.PersonaConfig`. Key fields:

- `id` (string): unique persona identifier.
- `prompt_assets`: relative or absolute paths for all prompt files.
- `data_dependencies`: bundle and session keys the persona needs.
- `ui_hooks.persona_card`: React/Streamlit component name or stub.
- `rr_contract`: base refinement increment and contradiction escalation.
- `consent_requirements`: opt-in and sharing envelope.

Example skeleton:

```json
{
  "id": "relationship_coach",
  "version": "0.1.0",
  "name": "Relationship Coach",
  "role": "Guides relationship reflection",
  "accent_color": "#8FBFE0",
  "keywords": ["relationship", "communication"],
  "vibe": {"keywords": ["empathetic", "wise"], "energy": "medium"},
  "honesty": {"mode": "balanced", "allowed_ranges": ["gentle", "balanced", "direct"]},
  "tone": {"baseline": "warm", "escalations": {"risk": "calm clarity"}},
  "honesty_contract": {"default": "consent_aligned", "overrides": {"crisis": "direct"}},
  "data_dependencies": {
    "bundle": ["padna.traits.relationship_history"],
    "session": ["onboarding.relationship_status"],
    "optional": []
  },
  "prompt_assets": {
    "system": "prompts/relationship_coach/system.md",
    "dialogue_templates": ["prompts/relationship_coach/opening.md"],
    "micro_actions": ["prompts/relationship_coach/microactions.md"],
    "evaluations": []
  },
  "ui_hooks": {"persona_card": "RelationshipCoachCard", "micro_action_stream": "rc_micro_feed"},
  "rr_contract": {"base_increment": 1.2, "contradiction_escalation": 0.6},
  "consent_requirements": {"needs_partner_opt_in": false, "share_scope": "self_only"},
  "lifecycle": {"beta": true, "requires_head_coach_supervision": true}
}
```

## 3. Register the persona

```python
from shared.persona_schema import PersonaHooks
from ReDNACoreDemo.core import persona_registry

payload = json.load(open("relationship_coach.json"))
persona_registry.register_persona(payload, hooks=PersonaHooks())
```

Registration steps:

1. Validate against `PersonaConfig` schema (raises `PersonaValidationError` on failure).
2. Load prompt files into `ReDNACoreDemo.ai.prompt_registry`.
3. Register a card via `ExplorerFinal.ui.persona_cards_registry`.
4. Register a `PersonaDescriptor` on the bus so the Head Coach switcher sees it.

## 4. Verify in the UI

- Enable dev tabs: `PERSONA_DEV_TABS=true streamlit run ExplorerFinal/app.py`.
- Visit **RC Dev** to inspect the prompt payload and run a dry-run check.
- Switch to **Head Coach** and pick the new persona from the persona chips.

## Troubleshooting

- **Missing asset**: ensure prompt paths point to readable files.
- **Duplicate id**: pass `overwrite=True` in a custom hook or remove the existing persona first.
- **No card in UI**: confirm `persona_cards_registry.get_card(<id>)` returns data.
