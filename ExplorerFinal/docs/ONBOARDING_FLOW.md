# Head Coach Onboarding (Onboarding Tab)

The Onboarding tab now runs a guided, button-first flow driven by the Head Coach replica. It keeps the chat composer pinned and renders a panel beneath it with three phases:

1. **Phase 1 – Basics & WYR**
   - Collect age range, gender, orientation, preferred language, and relationship status with predefined buttons (Other exposes a short free-text input).
   - Introduce the Head Coach (defaults to “Alex Harmony”) with an optional rename field.
   - Present one “Would You Rather” question (with an optional “New Question” refresh). Answering records `PrefDNA.Bonding.Style` and advances the flow.

2. **Phase 2 – Coach Promos**
   - Highlight the next best coaches to try (Bucket List, Physical Attribute, Initial Couples, Initial Looks Rater).
   - Selecting a promo stores a short free-text note so downstream coaches know to prepare hand-offs.

3. **Phase 3 – Other Options**
   - Simple A–G buttons capture scripted follow-ups (how ReDNA works, share a thought, pick relationship type, etc.).

Every click posts to UCN/RR `/ingest_text` with provenance `{actor: "user", source: "onboarding", ui: "head_coach"}` and Core picks up the updates immediately. Create a new user from the sidebar to kick off onboarding automatically. A privacy consent line stays visible throughout, and you can end the flow early via the sidebar control if needed.

The phase machine lives in `ui/onboarding_state.py`, while the UI renderers are in `ui/onboarding.py`. Modify the YAML files under `ExplorerFinal/data/` (`onboarding_basics.yaml`, `onboarding_wyr.yaml`) to tweak options or question sets.
