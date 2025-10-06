# Head Coach Personas

The Head Coach now acts as a single orchestrator that can adopt different personas. A persona is defined entirely by data so you can add or edit them without changing code.

## Registry location

Personas live in `ExplorerFinal/config/coach_personas.yaml`. Each persona entry contains:

- `title` and `description` for UI hints.
- `style` options (tone, bullet preference, max words) that are enforced on replies.
- `tools` the persona may call (e.g. `ingest_text`, `get_resolved`, `ingest_file`).
- `guardrails` describing topics to avoid or escalate.
- `prompt` text that seeds the model.

The file already includes examples for the head coach, nutrition, strength, data scientist, and ethics personas. Add new entries under `personas:` with a unique id. Restart the Explorer app to pick up changes.

## Routing and behaviour

The helper `ui/persona_router.py` loads the registry, routes intent for auto mode, and builds persona-specific system prompts. Personas that do not list a tool cannot exercise it (for example `ethics` only reads data while `nutrition` can ingest text). The Head Coach remains the default fallback.

When a persona suggests canonical Path=Value lines the chat UI offers an **Apply suggestions** button. Applied lines are sent to UCN/RR with provenance including `persona_id` so Core can track which persona contributed.

## Adding a new persona

1. Edit `ExplorerFinal/config/coach_personas.yaml` and add your persona under `personas:`.
2. Include at minimum `title`, `style`, `tools`, `guardrails`, and `prompt`.
3. Reload the Streamlit app. The new persona will appear in the Head Coach tab selector and can be used manually or by auto-routing.

Keep personas concise—short prompts and small style hints help responses stay fast and focused.
