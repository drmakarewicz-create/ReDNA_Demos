# Jarvis Functionality Phase 1 — Autonomous HC Orchestration

**Status:** ✅ Complete
**Version:** 1.0
**Date:** 2025-10-10

---

## Overview

Jarvis Functionality Phase 1 enables the Head Coach (HC) to proactively orchestrate learning and exploration by:

1. **Consulting the Curiosity Engine v2** for "what to pursue next" based on gap analysis and coach performance
2. **Consulting Self-Improvement analytics** for live tone/creativity guidance based on telemetry
3. **Proposing contextual nudges** to the user with safe, permission-aware actions

This is the first step toward full Jarvis-class autonomy, where the HC can autonomously guide users through their ReDNA journey.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  HC Orchestrator (Jarvis Phase 1)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  on_turn_start()                     maybe_nudge()             │
│  ┌────────────────────┐              ┌──────────────────────┐  │
│  │ Behavior Context   │              │ Curiosity Nudge      │  │
│  │ Enrichment         │              │ Generation           │  │
│  │                    │              │                      │  │
│  │ • Learning Report  │              │ • Top Agenda Item    │  │
│  │ • Tone Hints       │              │ • Priority Filter    │  │
│  │ • Creativity Bias  │              │ • Permission Gate    │  │
│  └────────────────────┘              └──────────────────────┘  │
│           │                                   │                 │
│           ▼                                   ▼                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         hc_llm_agent.generate_reply()                    │  │
│  │  (Enriched context + optional nudge in response)         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              API Response (POST /hc/say)                 │  │
│  │  {                                                        │  │
│  │    "content": "...",                                      │  │
│  │    "nudge": {                                             │  │
│  │      "kind": "curiosity_nudge",                           │  │
│  │      "coach_id": "career_coach",                          │  │
│  │      "prompt": "Tell me about your Python projects...",   │  │
│  │      "priority": 0.86,                                    │  │
│  │      "requires_consent": false                            │  │
│  │    }                                                      │  │
│  │  }                                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. HC Orchestrator Core (`hc_orchestrator.py`)

**Location:** `ReDNACoreDemo/core/hc_orchestrator.py` (350 LOC)

**Key Classes:**

#### `Nudge`
Structured nudge object for HC suggestions.

```python
class Nudge:
    def __init__(
        self,
        kind: str,              # "curiosity_nudge"
        title: str,             # "Close a high-value gap"
        coach_id: str,          # "career_coach"
        prompt: str,            # Suggested question to ask
        priority: float,        # 0.0-1.0 priority score
        reason: str,            # Human-readable explanation
        requires_consent: bool, # True for PaDNA/Photo
        target: Optional[str],  # Container path (e.g., "SkillDNA.python")
        evidence_refs: List[str] # Evidence references
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
```

#### `HCOrchestrator`
Main orchestration engine.

**Methods:**

```python
def on_turn_start(
    user_id: str,
    text: str,
    meta: Optional[Dict[str, Any]] = None,
    behavior_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Called at the start of each HC turn to enrich behavior context.

    Applies learning influence:
    - Tone hints (empathetic/balanced/concise) based on positive_rate
    - Creativity bias based on avg_latency_ms
    - Learning summary for developer mode

    Returns:
        Updated behavior context with learning influences
    """
```

```python
def maybe_nudge(
    user_id: str,
    text: str,
    idle_flag: bool = False,
    developer_mode: bool = False,
) -> Optional[Nudge]:
    """
    Generate a curiosity-driven nudge if appropriate.

    Triggers:
    - User asks "what next?" (detected by is_what_next_query)
    - Idle flag (future: timeout-based)

    Returns:
        Nudge object or None if no nudge appropriate
    """
```

```python
def apply_permission_gate(
    nudge: Nudge,
    user_id: str,
) -> Nudge:
    """
    Apply permission checks for sensitive namespaces.

    Flags nudges as requires_consent=True if targeting:
    - PaDNA (relationship/intimacy data)
    - Photo (image data)

    Returns:
        Nudge with requires_consent flag set
    """
```

---

### 2. Configuration (`hc_orchestrator_config.json`)

**Location:** `ReDNACoreDemo/core/hc_orchestrator_config.json`

```json
{
  "min_nudge_priority": 0.65,
  "idle_seconds": 90,
  "learning_influence": {
    "tone_weight": 0.3,
    "creativity_weight": 0.2
  },
  "respect_consent": true,
  "max_nudges_per_turn": 1,
  "sensitive_namespaces": [
    "PaDNA",
    "Photo"
  ]
}
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_nudge_priority` | float | 0.65 | Minimum priority to surface nudge (0.0-1.0) |
| `idle_seconds` | int | 90 | Idle timeout before nudge (future use) |
| `learning_influence.tone_weight` | float | 0.3 | Weight for tone adjustments from learning |
| `learning_influence.creativity_weight` | float | 0.2 | Weight for creativity bias from learning |
| `respect_consent` | bool | true | Apply permission gating |
| `max_nudges_per_turn` | int | 1 | Max nudges per turn |
| `sensitive_namespaces` | list | ["PaDNA", "Photo"] | Namespaces requiring consent |

---

### 3. Integration Points

#### HC LLM Agent (`hc_llm_agent.py`)

**Changes:** +35 LOC

```python
def generate_reply(...) -> Dict[str, Any]:
    # 1. Create orchestrator
    orchestrator = create_orchestrator()

    # 2. Enrich behavior context with learning influence
    behavior_context = orchestrator.on_turn_start(
        user_id=user_id,
        text=user_message,
        meta={"developer_mode": model_config.get("developer_mode", False)},
        behavior_context=behavior_context
    )

    # ... build prompt with enriched context ...

    # 3. Generate nudge if user asks "what next?"
    if coach_mode_manager.is_what_next_query(user_message):
        nudge = orchestrator.maybe_nudge(
            user_id=user_id,
            text=user_message,
            idle_flag=False,
            developer_mode=meta.get("developer_mode", False)
        )

        # Include nudge in response
        if nudge:
            response["nudge"] = nudge.to_dict()

    return response
```

#### Coach Mode Manager (`coach_mode_manager.py`)

**Changes:** +45 LOC

```python
def is_what_next_query(text: str) -> bool:
    """
    Detect if user message is asking "what next?" for proactive nudging.

    Patterns:
    - "what next", "what should we do", "what now"
    - "any ideas", "what else", "suggest something"
    - "where should we start", "what should we explore"
    - Short ambiguous queries: "?", "what?", "next?"

    Returns:
        True if message indicates user wants suggestions
    """
```

#### API Layer (`api.py`)

**Changes:** +7 LOC

```python
@app.post("/hc/say")
def hc_say(...):
    # ... generate LLM reply ...

    llm_response = generate_reply(...)

    # Include nudge if present (Jarvis Phase 1)
    if "nudge" in llm_response:
        result["nudge"] = llm_response["nudge"]

    return JSONResponse(content=result, status_code=200)
```

---

## Nudge Format

When a nudge is generated, it's included in the API response:

```json
{
  "content": "Let me help you explore your skills!",
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Close a high-value gap",
    "coach_id": "career_coach",
    "prompt": "Tell me about your recent Python projects and your comfort level with async programming.",
    "priority": 0.86,
    "reason": "High impact + low coverage",
    "requires_consent": false,
    "target": "SkillDNA.programming.python_fluency",
    "evidence_refs": ["gap:SkillDNA.programming"]
  }
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `kind` | string | Type of nudge (currently only "curiosity_nudge") |
| `title` | string | Short title for UI display |
| `coach_id` | string | Suggested coach to handle this exploration |
| `prompt` | string | Suggested question to ask the user |
| `priority` | float | Priority score (0.0-1.0) from curiosity engine |
| `reason` | string | Human-readable explanation for this nudge |
| `requires_consent` | boolean | True if touching sensitive namespace |
| `target` | string | Container path being explored |
| `evidence_refs` | array | References to evidence supporting this nudge |

---

## Learning Influence

The orchestrator consults the Self-Improvement learning report to adjust HC behavior:

### Tone Hints

Based on `positive_rate` (sentiment from telemetry):

| Positive Rate | Tone Hint | Behavior |
|---------------|-----------|----------|
| > 0.7 | "empathetic" | Warm, supportive, encouraging |
| 0.4 - 0.7 | "balanced" | Neutral, informative |
| < 0.4 | "concise" | Brief, direct, efficient |

### Creativity Bias

Based on `avg_latency_ms` (inverse proxy for creativity):

| Avg Latency | Creativity Bias | Behavior |
|-------------|-----------------|----------|
| < 1000ms | 0.7-0.8 | More exploratory, creative suggestions |
| 1000-2000ms | 0.5-0.7 | Balanced exploration |
| > 2000ms | 0.2-0.5 | More structured, less exploratory |

**Example enriched context:**

```python
{
    "tone_hint": "empathetic",
    "tone_bias": 0.75,
    "creativity_bias": 0.68,
    "learning_summary": {  # Only in developer mode
        "total_turns_analyzed": 290,
        "avg_positive_rate": 0.75,
        "coaches_analyzed": 3
    }
}
```

---

## Permission Gating

Nudges targeting sensitive namespaces are flagged `requires_consent: true`:

**Sensitive Namespaces:**
- `PaDNA` (relationship, intimacy data)
- `Photo` (image data)

**Behavior:**
- If `requires_consent: true`, UI should request explicit permission before proceeding
- No auto-action is taken
- User must explicitly approve before HC asks the suggested question

**Example:**

```json
{
  "nudge": {
    "coach_id": "padna_coach",
    "prompt": "Tell me about your relationship values.",
    "target": "PaDNA.relationship_values",
    "requires_consent": true
  }
}
```

**Frontend handling:**
```javascript
if (nudge.requires_consent) {
  // Show permission dialog
  showConsentDialog(nudge.coach_id, nudge.prompt);
} else {
  // Can proceed directly
  executeSuggestion(nudge);
}
```

---

## Telemetry

Nudge events are logged to `data/learning/nudge_telemetry.jsonl`:

**Event Types:**
- `nudge_shown` — Nudge surfaced to user
- `nudge_suppressed` — Nudge below threshold or blocked

**Example entry:**

```json
{
  "timestamp": "2025-10-10T01:45:00.123456+00:00",
  "user_id": "TEST",
  "event": "nudge_shown",
  "nudge": {
    "kind": "curiosity_nudge",
    "coach_id": "career_coach",
    "prompt": "Tell me about your Python projects...",
    "priority": 0.86,
    "target": "SkillDNA.programming.python_fluency",
    "requires_consent": false
  }
}
```

**Suppressed example:**

```json
{
  "timestamp": "2025-10-10T01:45:00.123456+00:00",
  "user_id": "TEST",
  "event": "nudge_suppressed",
  "nudge": {...},
  "reason": "below_threshold"
}
```

---

## Developer Mode (Narrator Trace)

When `developer_mode: true`, the orchestrator includes additional diagnostics:

**Example trace:**

```
[HC-Orchestrator] top_target=SkillDNA.programming.python_fluency p=0.86 coach=career_coach consent=false
[Learning] tone_hint=empathetic creativity_bias=0.78
```

**In behavior context:**

```python
{
    "tone_hint": "empathetic",
    "tone_bias": 0.75,
    "creativity_bias": 0.78,
    "learning_summary": {
        "total_turns_analyzed": 290,
        "avg_positive_rate": 0.75,
        "coaches_analyzed": 3
    }
}
```

---

## Usage Examples

### Python

```python
from ReDNACoreDemo.core.hc_orchestrator import create_orchestrator

orchestrator = create_orchestrator()

# Enrich behavior context
context = orchestrator.on_turn_start(
    user_id="USER123",
    text="Hello",
    meta={"developer_mode": True},
    behavior_context={}
)

# Generate nudge
nudge = orchestrator.maybe_nudge(
    user_id="USER123",
    text="what should we do next?",
    idle_flag=False,
    developer_mode=True
)

if nudge:
    print(f"Nudge: {nudge.prompt}")
    print(f"Priority: {nudge.priority}")
    print(f"Requires consent: {nudge.requires_consent}")
```

### cURL (via API)

```bash
# Send "what next?" message
curl -X POST http://localhost:8015/hc/say \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "message": "what next?",
    "skip_llm": false
  }' | jq '.nudge'

# Response:
{
  "kind": "curiosity_nudge",
  "coach_id": "career_coach",
  "prompt": "Tell me about your recent Python projects...",
  "priority": 0.86,
  "requires_consent": false
}
```

---

## Configuration Tuning

### Adjust Nudge Threshold

Lower threshold to surface more nudges:

```json
{
  "min_nudge_priority": 0.50  // Default: 0.65
}
```

### Adjust Learning Influence

Increase tone/creativity influence from learning analytics:

```json
{
  "learning_influence": {
    "tone_weight": 0.5,       // Default: 0.3
    "creativity_weight": 0.4  // Default: 0.2
  }
}
```

### Add Sensitive Namespaces

Extend permission gating to other namespaces:

```json
{
  "sensitive_namespaces": [
    "PaDNA",
    "Photo",
    "HealthDNA",  // NEW
    "EmDNA"       // NEW
  ]
}
```

---

## Testing

**Test Suite:** `ReDNACoreDemo/tests/test_hc_orchestrator.py` (13 tests)

### Test Scenarios

1. ✅ **What-next query triggers nudge** — User asks "what next?", top agenda item returned
2. ✅ **Idle triggers nudge** — Idle flag triggers nudge
3. ✅ **PaDNA requires consent** — PaDNA targets flagged as requiring consent
4. ✅ **Learning influences tone** — Tone hints shift based on learning report
5. ✅ **No agenda returns None** — Empty curiosity agenda returns no nudge
6. ✅ **Telemetry logged** — Nudge_shown events logged to telemetry
7. ✅ **Performance target** — Orchestration completes in <200ms with cached data
8. ✅ **What-next classifier** — Pattern detection for "what next?" queries
9. ✅ **Below threshold suppressed** — Low-priority nudges suppressed
10. ✅ **Nudge serialization** — Nudge.to_dict() works correctly
11. ✅ **Developer mode** — Learning summary included in dev mode
12. ✅ **Photo namespace** — Photo targets require consent
13. ✅ **Fallback agenda** — Fallback agenda generates nudge with note

**Run tests:**

```bash
PYTHONPATH=. python3 -m pytest ReDNACoreDemo/tests/test_hc_orchestrator.py -v
```

**Result:** All 13 tests passing in 0.05s

---

## Performance

**Targets:**
- Orchestration overhead: <200ms with cached learning report ✅
- Nudge generation: <500ms (includes curiosity agenda generation) ✅

**Caching:**
- Learning report cached for 5 minutes
- Curiosity agenda NOT cached (generated fresh per request)

**Optimization tips:**
- Keep `min_nudge_priority` at 0.65 or higher to reduce spurious nudges
- Use `max_nudges_per_turn: 1` to avoid overwhelming user
- Enable `developer_mode` only when debugging (adds ~10ms overhead)

---

## Limitations & Future Work

### Current Limitations

1. **No idle timeout yet** — Idle flag must be set manually; future: auto-detect based on session inactivity
2. **Single nudge per turn** — `max_nudges_per_turn: 1` enforced; future: support multi-nudge scenarios
3. **No nudge acceptance tracking** — Telemetry logs shown/suppressed but not accepted/rejected
4. **No adaptive thresholds** — `min_nudge_priority` is static; future: learn optimal threshold per user

### Phase 2 Roadmap

1. **Nudge Acceptance Feedback Loop**
   - Track when users accept/reject/ignore nudges
   - Adjust `min_nudge_priority` per user based on acceptance rate

2. **Idle Detection**
   - Auto-detect session inactivity
   - Surface nudge after `idle_seconds` without user input

3. **Multi-Nudge Support**
   - Allow 2-3 nudges when user explicitly asks "give me options"
   - Rank by priority, diversity (different coaches/namespaces)

4. **Proactive Nudging**
   - Surface nudges without "what next?" query
   - Based on user tolerance and completion rate

5. **Delegation Integration**
   - Auto-delegate to suggested coach when nudge accepted
   - Seamless handoff with context preservation

---

## Troubleshooting

### No nudge generated when expected

**Check:**
1. Curiosity agenda has items with `priority >= min_nudge_priority`
2. Learning report exists at `data/learning/analysis_report.json`
3. User message matches `is_what_next_query()` patterns
4. No errors in orchestrator logs

**Debug:**
```python
orchestrator = create_orchestrator()
nudge = orchestrator.maybe_nudge(
    user_id="TEST",
    text="what next?",
    developer_mode=True  # Enables verbose logging
)
```

### Nudge priority too low

**Solution:** Lower threshold in config:

```json
{
  "min_nudge_priority": 0.50  // Was 0.65
}
```

### PaDNA nudge not requiring consent

**Check:** Config has `"respect_consent": true` and `"PaDNA"` in `sensitive_namespaces`

**Verify:**
```bash
cat ReDNACoreDemo/core/hc_orchestrator_config.json | jq '.respect_consent, .sensitive_namespaces'
```

---

## Summary

Jarvis Functionality Phase 1 implemented: HC now consults learning + curiosity to propose permission-aware nudges and adjust behavior hints autonomously.

**Key Achievements:**
- ✅ Curiosity-driven nudge generation with top agenda item
- ✅ Learning-influenced tone/creativity adjustments
- ✅ Permission gating for PaDNA/Photo namespaces
- ✅ Telemetry logging for all nudge events
- ✅ <200ms orchestration overhead (cached)
- ✅ 13/13 tests passing
- ✅ Backward compatible (nudge is optional in response)

**Files Added/Modified:** 750+ LOC across 5 files

**Next Steps:** Phase 2 — Nudge acceptance feedback loop, idle detection, multi-nudge support
