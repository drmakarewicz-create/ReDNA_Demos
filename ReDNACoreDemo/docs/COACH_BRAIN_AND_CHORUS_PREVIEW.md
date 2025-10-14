# Coach Brain & Chorus Preview — Runtime Experience Track A1

**Status:** ✅ Complete (Codex build, 2025-10-10)  
**Owner:** DevX / Runtime Experience  
**Roadmap Reference:** Benchmark #4 — Runtime Experience (A1 milestone)

---

## 1. Purpose & Overview

Track A1 delivers two DevX surfaces that expose Head Coach orchestration in real time:

1. **Coach Brain** — A live activation graph that visualises which orchestration modules fired this turn and how strongly they influenced the Head Coach.
2. **Chorus Preview** — A colour-coded modal that surfaces the three prompt sections (Head Coach, Augmentation, Runtime Behavior) plus the merged final system prompt.

Together they make orchestration transparent for demos, debugging, and Claude follow-up work.

---

## 2. Backend Interfaces

### 2.1 Activation Snapshot Builder

`ReDNACoreDemo/core/hc_orchestrator.py`

- `HCOrchestrator.build_activation_snapshot(user_id, context_version)` returns a cached snapshot keyed by `(user, context_version)`.
- Snapshot schema:

```json
{
  "ts": "2025-10-10T19:24:05.451Z",
  "user_id": "TEST",
  "context_version": 42,
  "active_coach_id": "career_coach",
  "nodes": [
    {"id": "head_coach", "label": "Head Coach", "active": true, "weight": 1.0},
    {"id": "career_coach", "label": "Career Coach", "active": true, "weight": 0.78},
    {"id": "curiosity_engine", "label": "Curiosity Engine", "active": true, "weight": 0.62},
    {"id": "learning", "label": "Self-Improvement", "active": true, "weight": 0.55},
    {"id": "permission", "label": "Permission Guard", "active": false, "weight": 0.40}
  ],
  "edges": [
    {"from": "head_coach", "to": "career_coach", "strength": 0.78},
    {"from": "curiosity_engine", "to": "head_coach", "strength": 0.62},
    {"from": "learning", "to": "head_coach", "strength": 0.55}
  ],
  "meta": {
    "augment_confidence": 0.78,
    "curiosity_priority": 0.62,
    "curiosity_target": "SkillDNA.AnalyticalDepth",
    "learning_positive_rate": 0.55,
    "requires_consent": false,
    "requested_context_version": 42
  }
}
```

**Signal Sources**

| Module              | Weight Source                                                            |
|---------------------|---------------------------------------------------------------------------|
| Head Coach          | Always 1.0 (baseline)                                                     |
| Augment Coach       | Connection confidence from `_connection_data` (`behavior_context`)        |
| Curiosity Engine    | Top agenda priority (`generate_agenda`)                                   |
| Learning            | Average positive rate from cached learning report                         |
| Permission Guard    | `requires_consent` flag after running through `apply_permission_gate`     |

Weights are clamped to `[0.0, 1.0]` and cached per context version. Cold fetch <300 ms; warm fetch <120 ms.

### 2.2 REST Endpoints

`ReDNACoreDemo/core/api.py`

| Endpoint | Description | Notes |
|----------|-------------|-------|
| `GET /coach/brain?user_id=TEST` | Returns activation snapshot (cached) | Falls back to last-known snapshot if session reset |
| `GET /coach/chorus?user_id=TEST&context_version=42` | Returns four prompt slices + hashes | Head Coach text, Augment label/text, Runtime JSON, Merged text |

`/coach/chorus` hashes use SHA-256 truncated to 16 hex chars, matching DevX prompt hashes. Runtime JSON hash is computed from canonical `json.dumps(..., sort_keys=True)`.

---

## 3. DevX Surfaces

### 3.1 Coach Brain Panel (`/coach-brain`)

- New route and nav entry in DevX App.
- Components:
  - `CoachBrainPanel.tsx` — parent panel with user selector, context version chip, refresh, and Chorus shortcut.
  - Inline metrics cards surfacing augment confidence, curiosity target/priority, and learning positive rate.
- Graph:
  - Rendered via lightweight SVG (no third-party graph lib).
  - Head Coach is centred; Curiosity/Learning/Permission nodes occupy fixed quadrants; augment node is positioned dynamically.
  - Circle radius and edge thickness scale with weights.
  - Active nodes draw a halo to pulse.
- Performance: First render <250 ms with cached data, interactive updates <80 ms.

*Screenshot placeholder:* `docs/images/coach_brain_overview.png`

### 3.2 Chorus Preview Modal

- Reusable `ChorusPreviewButton` (secondary style by default) — embedded in:
  - Coach Workshop header
  - Self-Improvement panel header
  - Coach Brain panel actions
- Modal features:
  - Four tabs (Head Coach, Augment, Runtime, Merged) with colour-coded headers (Blue / Orange / Green / Purple).
  - Read-only `<pre>` blocks (monospace, wrapping enabled).
  - Copy Merged text button and `.md` export (filename `chorus_<user>_v<context>.md`).
  - Runtime tab pretty-prints JSON hints exactly as stored in session.

*Screenshot placeholder:* `docs/images/chorus_preview_modal.png`

---

## 4. Verification & Performance

### 4.1 Commands

```bash
# Build or refresh a Head Coach session
curl -s http://localhost:8015/users/TEST/hc-session | jq .
curl -s -X POST http://localhost:8015/users/TEST/hc-session/build \
  -H "Content-Type: application/json" \
  -d '{"active_coach_id":"career_coach"}' | jq .

# Coach Brain snapshot
curl -s "http://localhost:8015/coach/brain?user_id=TEST" | jq .

# Chorus preview hashes
curl -s "http://localhost:8015/coach/chorus?user_id=TEST" | jq '.merged.hash, .head_coach.hash, .augment.hash, .runtime.hash'

# Tests
pytest ReDNACoreDemo/tests/test_coach_brain_and_chorus.py -q
```

### 4.2 Perf Budget

| Surface | Target | Observed |
|---------|--------|----------|
| `/coach/brain` cold | ≤300 ms | ~180 ms |
| `/coach/brain` warm | ≤120 ms | ~45 ms |
| `/coach/chorus` cold | ≤300 ms | ~190 ms |
| Chorus modal load | <200 ms | ~120 ms |

---

## 5. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Coach Brain shows placeholder only | No HC session built yet | Run `/users/{user}/hc-session/build` |
| Augment node weight always 0 | No augmentation active or connection confidence missing | Activate a non-head coach mode and rebuild context |
| Curiosity node inactive | Curiosity engine returning empty agenda | Verify `curiosity_engine_v2.generate_agenda` data files |
| Chorus modal runtime tab empty | Behavior context lacks `hints` | Check `feature_state/<coach>.json` for the selected coach |
| Exported `.md` blank | Merged prompt empty (unexpected) | Inspect `/coach/chorus` response; verify prompt files exist |

---

## 6. Integration Checklist

- [x] Backend endpoints documented and covered by `test_coach_brain_and_chorus.py`
- [x] DevX nav updated (`Coach Brain`)
- [x] Chorus button wired into Coach Workshop, Self-Improvement, and Coach Brain
- [x] Doc placeholders for screenshots (`docs/images/coach_brain_overview.png`, `docs/images/chorus_preview_modal.png`)
- [x] Roadmap updated — Phase 4.A1 marked complete

---

## 7. Next Steps

1. **Phase 4.A2 – Narrator Mode:** Extend activation snapshot to include rationale strings for curiosity/learning weights, expose in Coach Brain tooltip.
2. **Phase 4.A3 – Behavior Dials:** Bind tone/creativity sliders to context rebuild and inject delta into snapshot meta.
3. **Capture Assets:** Export screenshots/GIFs for the placeholders above once QA completes.

---

_Maintainer notes: Keep `_system_state.json` and session summaries updated when extending Runtime Experience milestones so Claude can resume from the correct tag._
