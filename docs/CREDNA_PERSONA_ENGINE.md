# CReDNA Persona Engine v0.2

**Per-User, Per-Coach Personality Synthesis**

## Overview

CReDNA (Coach Refinement DNA) is a personality engine that generates distinct, trainable style/persona envelopes for each (user_id, coach_id, intent) combination. This enables:

- **Granular personalization**: Dave's Career Coach feels different from Dave's PTC, AND different from Jackie's Career Coach
- **Natural evolution**: Coaches learn from user feedback over time
- **Manual fine-tuning**: Users can explicitly adjust personality dimensions via sliders/chips
- **Privacy-aware**: Respects consent gates for sensitive traits

## Architecture

### Layered Blending Model

```
final_style = blend(user_style, role_overlay, weights) ⊕ apply(user_coach_deltas) ⊕ apply(manual_prefs)
```

**Layer Order** (applied sequentially):

1. **role_overlay** - Global defaults per coach type (e.g., Career Coach is "encouraging, direct, formal")
2. **user_style** - Extracted from user's ReDNA profile (LanguageStyleDNA, PersonalityDNA)
3. **user_coach_deltas** - Learned adjustments from feedback (numeric shifts per dimension)
4. **manual_prefs** - Explicit user overrides (categorical targets, applied last)

### Lazy Materialization

Per-user-per-coach files are **only created when training happens**:

- Fresh user + default coach → Returns blend(role_overlay, user_style), **no files created**
- User gives first feedback → Creates `data/users/<user>/credna/<coach>/deltas.json`
- User saves manual prefs → Creates `data/users/<user>/credna/<coach>/prefs.json`

This keeps the file system clean and scales to thousands of users without bloat.

## Storage Layout

```
data/users/<user_id>/credna/<coach_id>/
  deltas.json              # Learned dimensional adjustments (lazy)
  prefs.json               # Manual overrides (lazy)
  envelope_cache.json      # Short-TTL cache (lazy, LRU-5, 10min)
  feedback_log.jsonl       # Append-only ratings/notes (lazy)

ReDNACoreDemo/core/credna/
  overlays/
    role_overlays.yaml     # Global coach defaults
    chips_map.yaml         # "more direct" → +directness mapping
```

## Envelope Contract

```json
{
  "tone": "warm|neutral|cool|encouraging|reflective|optimistic",
  "cadence": "slow|medium|medium-fast|fast",
  "formality": "casual|neutral|semi-formal|formal",
  "vocabulary": "low|medium|high",
  "hedging": "low|medium|high",
  "humor": "none|dry|witty|playful",
  "directness": "indirect|balanced|direct",
  "empathy": "low|moderate|high",
  "stance_hints": ["Care/Fairness", "Achievement"],
  "merge_weights": {
    "user_style": 0.6,
    "coach_role": 0.4,
    "user_delta": 0.2,
    "manual_prefs": 0.0
  },
  "sources": ["role_overlay", "user_style", "user_delta"],
  "materialized": false,
  "credna_version": "0.2",
  "policy": {
    "overlay_id": "career_coach/default",
    "consent_applied": true,
    "sensitive_suppressed": []
  }
}
```

## Training Modes

### Natural Evolution (Feedback Ratings)

User provides dimensional feedback after coach interactions:

```json
POST /api/credna/feedback
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "dimension": "directness",
  "rating": 4,
  "notes": "a bit more direct"
}
```

- **Rating scale**: 1-5 → maps to delta adjustments [-8, -4, 0, +4, +8]
- **Cooldowns**: 24h per dimension (prevents spam/gaming)
- **Bounded**: Dimensions clamped to valid categorical ranges

### Manual Fine-Tuning (Prefs)

User explicitly sets dimension targets via Workshop UI:

```json
POST /api/credna/save_prefs
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "prefs": {
    "directness": "high",
    "formality": "low",
    "tone": "optimistic"
  }
}
```

- **Override semantics**: Manual prefs applied **last**, superseding deltas
- **UI**: Sliders + chips in Coach Workshop "CReDNA Profile" tab

### Feedback Chips

Intuitive controls that map to dimensional shifts:

| Chip | Dimension | Delta | Description |
|------|-----------|-------|-------------|
| `more_direct` | directness | +1 | More straightforward |
| `less_formal` | formality | -1 | More casual |
| `warmer` | empathy | +1 | More supportive |
| `faster` | cadence | +1 | Get to the point |
| `wittier` | humor | +1 | Add playfulness |

See `overlays/chips_map.yaml` for full mapping.

## Cache Behavior

**Short-TTL envelope cache** per (user, coach, intent):

- **TTL**: 10 minutes
- **LRU**: Last 5 envelopes per pair
- **Bust on**:
  - New feedback accepted
  - Prefs saved
  - Core RR change > threshold for relevant containers
  - Role overlay file change (hash mismatch)

**Performance targets**:
- GET `/api/credna/style_envelope` < 10ms (warm, cached)
- Panel compose ≤ 200ms

## Privacy & Consent

**Consent gates** prevent sensitive traits from leaking into envelopes:

- Before extracting `stance_hints` from BeliefValueDNA, check user consent flags
- If gated, fall back to neutral defaults
- Policy log records which traits were suppressed

**Audit trail** (Dev Mode only):
- Overlay ID used
- Sources contributing to envelope
- Dimensions overridden
- Deltas applied
- Clamps enforced
- Consent decisions

**No raw content**: Policy logs never store user prompts/outputs, only metadata.

## API Endpoints

### GET /api/credna/style_envelope

Build envelope for (user, coach, intent).

**Query params**:
- `user_id` (required)
- `coach_id` (required)
- `intent` (optional, default="default")

**Response**: Full envelope JSON (see contract above)

### POST /api/credna/feedback

Submit dimensional feedback rating.

**Body**:
```json
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "dimension": "directness",
  "rating": 4,
  "notes": "optional"
}
```

**Returns**: Updated envelope + `rr_delta_summary` (optional)

**Alternative** (chip-based):
```json
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "chips": ["more_direct", "less_formal"]
}
```

### POST /api/credna/save_prefs

Save manual preference overrides.

**Body**:
```json
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "prefs": {
    "directness": "high",
    "tone": "optimistic"
  }
}
```

**Returns**: Updated envelope with `materialized=true`

### POST /api/credna/reset

Reset learned deltas and/or prefs.

**Body**:
```json
{
  "user_id": "TEST",
  "coach_id": "career_coach",
  "reset": "all|deltas|prefs"
}
```

**Returns**: Envelope from default blend

## Coach Workshop Integration

**CReDNA Profile Panel** for selected (user, coach):

**Features**:
- View current envelope (read-only summary + JSON toggle)
- Show materialized state and mode badge:
  - 🌱 **Natural** - defaults only, no training
  - 📈 **Trained** - has learned deltas
  - 🎛️ **Manual** - prefs override active
- Edit Personality: sliders/chips for key dimensions
- Reset buttons: deltas, prefs, or all
- Quick preview: type prompt → call coach render to hear effect

## Integration with Existing Coaches

### ChatDNA Coach (Special Case - User Self-Simulation)

ChatDNA Coach has a **unique use case**: it lets users have simulated conversations with **themselves** (not with a coach personality). Therefore:

**ChatDNA Coach does NOT use CReDNA** for coach personality. Instead, it uses the **user_style extraction logic** from CReDNA's `_compute_user_style()`:

```python
from core.credna.persona_synthesis import _compute_user_style

# Extract user's own conversational style
user_style = _compute_user_style(user_id)

# Generate response AS the user (not as a coach)
response = llm.generate(prompt, user_style, system_role=f"You are {user_id}")
```

**Key difference**:
- **ChatDNA Coach**: `user_style` only (simulates the user talking to themselves)
- **Other coaches**: Full CReDNA envelope (coach personality blended with user preferences)

ChatDNA Coach serves as a **reference implementation** showing that the same ReDNA extraction logic can power both:
1. **User self-simulation** (ChatDNA) - "What would I say?"
2. **Coach personality synthesis** (all other coaches) - "What would the coach say to me?"

**Why this matters**:
- ChatDNA lets Dave talk to "Virtual Dave" to rehearse conversations, test messaging, etc.
- Career Coach lets Dave talk to a career expert whose personality adapts to Dave's preferences
- Same underlying ReDNA → different use cases

### Other Coaches

Career Coach, PTC, BeliefDNA Coach, etc. can opt-in via manifest flag:

```yaml
coach_id: career_coach
credna_enabled: true
default_intent: supportive
```

When enabled, coach responses use CReDNA envelope instead of inline style logic.

## Acceptance Criteria

**Multi-user, multi-coach isolation**:

✅ Dave×Career ≠ Dave×PTC (different coaches, same user)
✅ Dave×Career ≠ Jackie×Career (same coach, different users)
✅ Feedback to Dave×Career doesn't affect Dave×PTC or Jackie×Career

**Lazy materialization**:

✅ Fresh user + default coach → No files created, `materialized=false`
✅ First feedback → Files created, `materialized=true`
✅ Reset all → Files deleted, `materialized=false`

**Training modes**:

✅ Natural: Rating 4 → +directness delta, envelope updates
✅ Manual: Save prefs → overrides deltas, envelope reflects immediately
✅ Chips: "more_direct" → same as rating 4

**Privacy & performance**:

✅ Sensitive trait suppressed when consent gated
✅ Policy log shows suppression decision
✅ GET envelope < 10ms (warm cache)
✅ Panel compose ≤ 200ms

## Versioning

- **credna_version**: "0.2" in all envelopes
- **Overlay hash**: Detect role overlay changes → bust cache
- **Migration**: If schema changes, version field enables safe upgrades

## Future Extensions

### Per-Intent Deltas

Support finer granularity within the same pair:

```json
deltas.json:
{
  "default": { "directness": +1 },
  "career_change": { "directness": +2, "empathy": +1 }
}
```

### Org-Level Overlays

Add tenant/team defaults between role and user:

```
org_overlays/<org_id>/<coach_id>.yaml
→ final = user_delta ⊕ org_overlay ⊕ role_overlay ⊕ user_style
```

### Multi-Attribute Feedback

Allow rating multiple dimensions at once:

```json
{
  "ratings": {
    "directness": 4,
    "empathy": 5,
    "formality": 2
  }
}
```

## Summary

CReDNA v0.2 enables **per-user, per-coach personality training** with:

- **Layered blending** (role → user → deltas → prefs)
- **Lazy materialization** (files only when needed)
- **Dual training** (natural feedback + manual fine-tuning)
- **Privacy-aware** (consent gates + policy logging)
- **Fast & scalable** (caching, bounded complexity)

ChatDNA Coach serves as the **prototype and first integration**, demonstrating that the same ReDNA-driven synthesis approach can power all coach personalities in the future.
