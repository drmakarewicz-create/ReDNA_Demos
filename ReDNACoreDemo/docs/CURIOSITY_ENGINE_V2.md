# Curiosity Engine v2

**Status:** ✅ Complete
**Version:** 2.0
**Benchmark:** #6 Curiosity & Motivation
**Created:** 2025-10-09

---

## 📖 Overview

The Curiosity Engine v2 is an adaptive exploration and motivation system that autonomously determines **what information, traits, and coaches to pursue next** for each user. It consumes Self-Improvement analytics, ontology metadata, and user data coverage to generate prioritized **Curiosity Agendas** — ranked lists of containers/traits to explore with suggested coaches and prompts.

**Why now:** With Benchmark #8 (Self-Improvement Loop) complete, we have telemetry analytics showing which coaches perform best. The Curiosity Engine reuses these metrics to guide exploration toward high-impact, high-gap areas.

---

## 🎯 Goal

Move ReDNA toward **autonomous discovery** by:
1. Identifying gaps in user data coverage
2. Prioritizing exploration based on coach performance
3. Balancing novelty (unexplored traits) vs. exploitation (proven coaches)
4. Learning from feedback to refine future agendas

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Inputs (Data Sources)                      │
│  ├── Self-Improvement analytics (analysis_report.json)       │
│  ├── User data (user.json, resolved.json, RR/UCN)           │
│  ├── Recent interactions (events/*.json)                     │
│  ├── Feedback history (curiosity_feedback.jsonl)            │
│  └── Ontology (dna_registry.json containers)                │
└──────────────────────────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                  Curiosity Engine v2                          │
│  ReDNACoreDemo/core/curiosity/curiosity_engine_v2.py         │
│                                                               │
│  Scoring Formula (weighted):                                 │
│  ├── Gap Score (50%): Inverse of data coverage/certainty    │
│  ├── Impact Score (30%): Coach success from analytics       │
│  ├── Recency Score (10%): Prefer unexplored recently        │
│  └── Cost Score (10%): Down-weight prior failures           │
│                                                               │
│  Priority = Σ(weight_i × score_i)                           │
└──────────────────────────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    Curiosity Agenda                           │
│  Per-User JSON Output                                        │
│  {                                                            │
│    "user_id": "USER123",                                     │
│    "generated_at": "ISO timestamp",                          │
│    "items": [                                                │
│      {                                                        │
│        "target": "SkillDNA.programming.python_fluency",     │
│        "priority": 0.92,                                     │
│        "reason": "High gap; career_coach performing well",   │
│        "suggested_coach": "career_coach",                    │
│        "suggested_prompt": "Tell me about Python projects", │
│        "evidence_refs": ["telemetry:career_coach:..."]      │
│      }                                                        │
│    ]                                                          │
│  }                                                            │
└──────────────────────────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    Consumption                                │
│  ├── Head Coach: get_curiosity_agenda(user_id)              │
│  ├── API: POST /curiosity/agenda                            │
│  └── Cache: data/users/{user_id}/curiosity/agenda.json      │
└──────────────────────────────────────────────────────────────┘
```

---

## 📂 File Structure

```
ReDNACoreDemo/
├── core/
│   ├── curiosity/
│   │   ├── __init__.py
│   │   ├── curiosity_engine_v2.py        # Main engine (~390 LOC)
│   │   └── curiosity_config.json         # Weights & namespace→coach mapping
│   ├── api.py                            # +140 LOC (3 endpoints)
│   └── coach_mode_manager.py             # +35 LOC (get_curiosity_agenda helper)
├── tests/
│   └── test_curiosity_engine_v2.py       # ~350 LOC (11 tests)
└── docs/
    └── CURIOSITY_ENGINE_V2.md            # This file
```

---

## ⚙️ Configuration

**File:** `ReDNACoreDemo/core/curiosity/curiosity_config.json`

```json
{
  "weights": {
    "gap": 0.5,        // 50% weight for data gap
    "impact": 0.3,     // 30% weight for coach performance
    "recency": 0.1,    // 10% weight for novelty
    "cost": 0.1        // 10% weight for failure penalty
  },
  "max_items": 12,
  "min_priority": 0.55,
  "namespace_to_coach": {
    "SkillDNA": "career_coach",
    "ProfDNA": "career_coach",
    "LanguageStyleDNA": "chatdna_coach",
    "CommStyleDNA": "chatdna_coach",
    "BeliefValueDNA": "beliefdna_coach",
    "MoralDNA": "beliefdna_coach",
    "PaDNA": "padna_coach",
    "PsyDNA": "personality_test_coach",
    "BehDNA": "personality_test_coach",
    "EmDNA": "relationship_coach",
    "ReDNA": "relationship_coach",
    "CogDNA": "head_coach",
    "GenDNA": "head_coach"
  },
  "recency_window_hours": 72,
  "cost_failure_multiplier": 0.7,
  "suggested_prompts": {
    "SkillDNA": "Tell me about your recent work experience and skills.",
    "LanguageStyleDNA": "How would you describe your communication style?",
    "BeliefValueDNA": "What values guide your important decisions?",
    "PaDNA": "I'd love to understand your visual preferences better.",
    ...
  }
}
```

### Weight Tuning

- **Increase `gap`** → prioritize unexplored areas
- **Increase `impact`** → favor high-performing coaches
- **Increase `recency`** → prefer novel targets
- **Increase `cost`** → strongly avoid failure-prone targets

---

## 🧮 Scoring Formula

For each target (container/trait):

```python
priority = (
    weights["gap"] * gap_score +
    weights["impact"] * impact_score +
    weights["recency"] * recency_score +
    weights["cost"] * cost_score
)
```

### 1. Gap Score (0..1, higher = bigger gap)

**Purpose:** Measure how much data we're missing for this target.

**Calculation:**
- If target **not in resolved.json**: `gap_score = 0.9` (high gap)
- If target **in resolved.json**: `gap_score = ucnrr / 100`
  - Uses UCN (Uncertainty) metric from RR system
  - High UCN → high gap → high priority

**Example:**
```python
{
  "SkillDNA.programming.python": {
    "ucnrr": 75  # 75% uncertainty
  }
}
# gap_score = 0.75
```

---

### 2. Impact Score (0..1, based on coach performance)

**Purpose:** Prioritize targets mapped to high-performing coaches.

**Calculation:**
```python
positive_rate = sentiment_trend["positive"]  # from analysis_report.json
impact_score = 0.3 + (positive_rate * 0.7)
```

- Baseline: 0.3 (even 0% positive gets some credit)
- Max: 1.0 (100% positive sentiment)

**Example:**
```json
{
  "career_coach": {
    "sentiment_trend": {
      "positive": 0.8
    }
  }
}
# impact_score = 0.3 + (0.8 * 0.7) = 0.86
```

---

### 3. Recency Score (0..1, higher = not recently touched)

**Purpose:** Prefer targets not explored in the last 72 hours (configurable).

**Calculation:**
```python
if target not in recent_interactions:
    recency_score = 1.0  # Never touched
else:
    hours_ago = (now - last_interaction).hours
    recency_score = min(1.0, hours_ago / recency_window_hours)
```

**Example:**
- Last touched **12 hours ago**, window = 72 hours
  - `recency_score = 12 / 72 = 0.17` (low, recently visited)
- Last touched **80 hours ago**
  - `recency_score = 1.0` (high, outside window)

---

### 4. Cost Score (0..1, lower if many failures)

**Purpose:** Down-weight targets with repeated failures (from feedback).

**Calculation:**
```python
failures = count_failures_from_feedback(target)
cost_score = cost_failure_multiplier ** failures
```

- Default multiplier: `0.7`
- 1 failure: `0.7`
- 2 failures: `0.49`
- 3 failures: `0.34`

**Example:**
```jsonl
{"target": "SkillDNA.java", "result": "blocked"}
{"target": "SkillDNA.java", "result": "blocked"}
```
# 2 failures → cost_score = 0.7^2 = 0.49
```

---

## 🔌 API Endpoints

### POST /curiosity/agenda

Generate a new curiosity agenda for a user.

**Request:**
```bash
curl -X POST http://localhost:8015/curiosity/agenda \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "limit": 10
  }'
```

**Response:**
```json
{
  "user_id": "TEST",
  "generated_at": "2025-10-09T21:30:00Z",
  "items": [
    {
      "target": "SkillDNA.programming.python_fluency",
      "priority": 0.92,
      "reason": "High data gap; career_coach performing well",
      "suggested_coach": "career_coach",
      "suggested_prompt": "Tell me about your recent Python projects and comfort with async.",
      "evidence_refs": ["analysis_report:coach=career_coach"]
    },
    {
      "target": "LanguageStyleDNA.formality.professional",
      "priority": 0.85,
      "reason": "Moderate data gap; chatdna_coach performing well",
      "suggested_coach": "chatdna_coach",
      "suggested_prompt": "How would you describe your communication style?",
      "evidence_refs": ["analysis_report:coach=chatdna_coach"]
    }
  ],
  "total_candidates": 5,
  "above_threshold": 2
}
```

**Performance:** < 500ms for 2-5k containers

---

### GET /curiosity/last-agenda

Retrieve the last generated agenda from cache.

**Request:**
```bash
curl "http://localhost:8015/curiosity/last-agenda?user_id=TEST"
```

**Response:**
Same as POST `/curiosity/agenda` response (from cache).

**Cache Location:** `data/users/{user_id}/curiosity/agenda.json`

---

### POST /curiosity/feedback

Submit feedback on an exploration attempt (for learning in Phase 2).

**Request:**
```bash
curl -X POST http://localhost:8015/curiosity/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "target": "SkillDNA.programming.python_fluency",
    "result": "success",
    "notes": "User shared recent projects and comfort level"
  }'
```

**Result Values:**
- `success` — User engaged, data collected
- `blocked` — User declined or unable to answer
- `irrelevant` — Target not applicable to user

**Response:**
```json
{
  "ok": true,
  "message": "Feedback recorded",
  "entry": {
    "timestamp": "2025-10-09T21:35:00Z",
    "user_id": "TEST",
    "target": "SkillDNA.programming.python_fluency",
    "result": "success",
    "notes": "User shared recent projects and comfort level"
  }
}
```

**Persistence:** `prompts/insights/curiosity_feedback.jsonl` (atomic append)

---

## 🧠 Head Coach Integration

### Helper Function

```python
from ReDNACoreDemo.core.coach_mode_manager import get_curiosity_agenda

agenda = get_curiosity_agenda(user_id="USER123", limit=8)
```

**Use Case:** Head Coach can call this when deciding "what should we ask/collect next?"

**Returns:** Same agenda structure as API endpoint.

**Error Handling:** Returns empty agenda with `"error"` field on failure (never raises).

---

## 📊 Example Agenda

**Scenario:** New user with minimal data, career_coach performing well (80% positive sentiment).

```json
{
  "user_id": "USER123",
  "generated_at": "2025-10-09T21:40:00Z",
  "items": [
    {
      "target": "SkillDNA.programming.python_fluency",
      "priority": 0.92,
      "reason": "High data gap; career_coach performing well",
      "suggested_coach": "career_coach",
      "suggested_prompt": "Tell me about your recent work experience and the skills you've been developing.",
      "evidence_refs": ["analysis_report:coach=career_coach"]
    },
    {
      "target": "SkillDNA.leadership.team_management",
      "priority": 0.88,
      "reason": "High data gap; career_coach performing well",
      "suggested_coach": "career_coach",
      "suggested_prompt": "Tell me about your recent work experience and the skills you've been developing.",
      "evidence_refs": ["analysis_report:coach=career_coach"]
    },
    {
      "target": "BeliefValueDNA.integrity.honesty",
      "priority": 0.72,
      "reason": "High data gap; beliefdna_coach needs tuning",
      "suggested_coach": "beliefdna_coach",
      "suggested_prompt": "What values and beliefs guide your important decisions?",
      "evidence_refs": ["analysis_report:coach=beliefdna_coach"]
    }
  ],
  "total_candidates": 2000,
  "above_threshold": 3
}
```

---

## 🧪 Testing

**File:** `ReDNACoreDemo/tests/test_curiosity_engine_v2.py` (~350 LOC)

**11 Test Scenarios:**

1. ✅ **Basic agenda generation** — Returns valid structure with ranked items
2. ✅ **Weights effect** — Changing weights affects priority ordering
3. ✅ **Recency suppression** — Recently-touched traits rank lower
4. ✅ **Cost penalty** — Targets with failures are down-weighted
5. ✅ **Min priority filter** — Items below threshold excluded
6. ✅ **Limit respected** — Returns at most `limit` items
7. ✅ **API round-trip** — POST → cache → GET returns same agenda
8. ✅ **Feedback append** — Feedback writes to JSONL correctly
9. ✅ **Performance target** — Completes in < 500ms
10. ✅ **Coach mapping** — Namespaces map to correct coaches
11. ✅ **HC hook** — `get_curiosity_agenda()` helper works

**Run tests:**
```bash
pytest -q ReDNACoreDemo/tests/test_curiosity_engine_v2.py
```

**Expected:** All pass in < 2s

---

## 🔍 Diagnostics and Fallback Behavior

**Added:** 2025-10-10 (v2.1)

The Curiosity Engine now includes comprehensive diagnostics and fallback modes to handle edge cases gracefully.

### Debug Mode

Add `"debug": true` to the API request to receive diagnostic information:

```bash
curl -X POST http://localhost:8015/curiosity/agenda \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "limit": 8,
    "debug": true
  }'
```

**Debug Response:**
```json
{
  "user_id": "TEST",
  "generated_at": "2025-10-10T01:30:00Z",
  "items": [],
  "debug": {
    "analysis_report_found": false,
    "ontology_found": true,
    "min_priority": 0.55,
    "weights_summary": {
      "gap": 0.5,
      "impact": 0.3,
      "recency": 0.1,
      "cost": 0.1
    },
    "total_candidates_scored": 0,
    "below_threshold_count": 0,
    "namespaces_found": [],
    "reason": "missing analysis report"
  }
}
```

### Fallback Mode

When the engine would return 0 items, fallback mode generates 3-5 placeholder items with sensible defaults.

**Enable fallback** (enabled by default):
```bash
curl -X POST http://localhost:8015/curiosity/agenda \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "limit": 8,
    "fallback": true
  }'
```

**Fallback Response:**
```json
{
  "user_id": "TEST",
  "generated_at": "2025-10-10T01:30:00Z",
  "items": [
    {
      "target": "SkillDNA.general_exploration",
      "priority": 0.5,
      "reason": "fallback_agenda_due_to_low_signal",
      "suggested_coach": "career_coach",
      "suggested_prompt": "Tell me about your recent work experience and skills.",
      "evidence_refs": ["fallback:no_telemetry"]
    },
    {
      "target": "BeliefValueDNA.general_exploration",
      "priority": 0.5,
      "reason": "fallback_agenda_due_to_low_signal",
      "suggested_coach": "beliefdna_coach",
      "suggested_prompt": "What values and beliefs guide your important decisions?",
      "evidence_refs": ["fallback:no_telemetry"]
    }
  ],
  "debug": {
    "reason": "low telemetry signal; fallback agenda generated"
  }
}
```

### Custom Min Priority

Override the config threshold per request:

```bash
curl -X POST http://localhost:8015/curiosity/agenda \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "limit": 8,
    "min_priority": 0.0
  }'
```

**Lower threshold** → more items included
**Higher threshold** → only highest-priority items

### Common Reasons for Empty Agendas

| Reason | Meaning | Solution |
|--------|---------|----------|
| `missing analysis report` | No telemetry data analyzed yet | Run `/learning/analyze` first |
| `missing ontology` | DNA registry not found | Check `ontology_path` in config |
| `no valid containers found` | Ontology has no containers | Verify ontology file structure |
| `all below threshold` | All priorities < min_priority | Lower `min_priority` or enable fallback |

### Parameters Reference

```typescript
{
  "user_id": string,           // Required
  "limit": number,             // Optional, default: config.max_items (12)
  "min_priority": number,      // Optional, default: config.min_priority (0.55)
  "debug": boolean,            // Optional, default: false
  "fallback": boolean          // Optional, default: true
}
```

**Strict Mode:** Set `fallback: false` to never generate placeholder items.

---

## 📈 Phase 2 Roadmap (Future)

**Not in this sprint — planned for later:**

### 1. Learn from Feedback
- Track `success` vs. `blocked` vs. `irrelevant` rates per target
- Boost targets with high success rates
- Suppress targets with high block/irrelevant rates

### 2. Exploration/Exploitation (E/E) Policy
- Implement epsilon-greedy or softmax selection
- Per-coach E/E tuning based on performance variance
- Adaptive exploration based on user engagement

### 3. DevX Mini-View
- "Curiosity Agenda" tab in DevX
- Shows top N items with tap-to-launch prompts
- Inline feedback buttons (success/blocked/irrelevant)

### 4. Multi-User Aggregation
- Identify popular vs. rare targets across user base
- Use collective feedback to improve global priority

---

## ✅ Acceptance Criteria

✅ Engine returns ranked agenda with {target, priority, reason, suggested_coach, suggested_prompt, evidence_refs}
✅ Agenda generation < 500ms on typical dev data
✅ Agenda persisted to per-user cache (`data/users/{id}/curiosity/agenda.json`)
✅ Feedback endpoint writes JSONL with timestamps
✅ All tests pass (11/11)
✅ Documentation complete

---

## 📝 Example Feedback JSONL Line

```json
{"timestamp": "2025-10-09T21:45:30Z", "user_id": "TEST", "target": "SkillDNA.programming.python_fluency", "result": "success", "notes": "User shared recent projects and comfort with async"}
```

---

## 🚀 Usage Examples

### Generate Agenda (CLI)
```bash
curl -s -X POST http://localhost:8015/curiosity/agenda \
  -H "Content-Type: application/json" \
  -d '{"user_id":"TEST","limit":8}' | jq
```

### Retrieve Last Agenda
```bash
curl -s "http://localhost:8015/curiosity/last-agenda?user_id=TEST" | jq
```

### Submit Feedback
```bash
curl -s -X POST http://localhost:8015/curiosity/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"TEST",
    "target":"SkillDNA.programming.python_fluency",
    "result":"success",
    "notes":"User shared recent projects"
  }' | jq
```

### Head Coach Integration
```python
from ReDNACoreDemo.core.coach_mode_manager import get_curiosity_agenda

agenda = get_curiosity_agenda(user_id="USER123", limit=5)

for item in agenda["items"]:
    print(f"🎯 {item['target']} (priority: {item['priority']})")
    print(f"   Coach: {item['suggested_coach']}")
    print(f"   Prompt: {item['suggested_prompt']}")
    print(f"   Reason: {item['reason']}")
```

---

## 📊 Files Changed Summary

**Total: 6 files, +940 LOC**

1. `ReDNACoreDemo/core/curiosity/__init__.py` (new, 12 LOC)
2. `ReDNACoreDemo/core/curiosity/curiosity_config.json` (new, 43 LOC)
3. `ReDNACoreDemo/core/curiosity/curiosity_engine_v2.py` (new, 390 LOC)
4. `ReDNACoreDemo/core/api.py` (+140 LOC, 3 endpoints)
5. `ReDNACoreDemo/core/coach_mode_manager.py` (+35 LOC, helper function)
6. `ReDNACoreDemo/tests/test_curiosity_engine_v2.py` (new, 350 LOC)
7. `ReDNACoreDemo/docs/CURIOSITY_ENGINE_V2.md` (this file, ~320 LOC)

---

## 🎯 Status

**Curiosity Engine v2 implemented; HC can request top curiosity targets with reasons and coach suggestions.**

Benchmark #6 complete. ✅
