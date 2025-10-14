# Jarvis Phase 1 — Example Outputs

**Generated:** 2025-10-10

---

## Example 1: What-Next Query Classification

```python
from ReDNACoreDemo.core import coach_mode_manager

queries = [
    "what next?",
    "what should we do now?",
    "any ideas?",
    "I like pizza"
]

for q in queries:
    result = coach_mode_manager.is_what_next_query(q)
    print(f"{q:30} -> {result}")
```

**Output:**

```
what next?                     -> True
what should we do now?         -> True
any ideas?                     -> True
I like pizza                   -> False
```

---

## Example 2: Behavior Context Enrichment

When learning report exists, orchestrator enriches behavior context with tone/creativity hints:

```python
from ReDNACoreDemo.core.hc_orchestrator import create_orchestrator

orchestrator = create_orchestrator()

context = orchestrator.on_turn_start(
    user_id="TEST",
    text="Hello",
    meta={"developer_mode": True},
    behavior_context={}
)

print(json.dumps(context, indent=2))
```

**Output (with learning report):**

```json
{
  "tone_hint": "empathetic",
  "tone_bias": 0.75,
  "creativity_bias": 0.68,
  "learning_summary": {
    "total_turns_analyzed": 290,
    "avg_positive_rate": 0.75,
    "coaches_analyzed": 3
  }
}
```

**Output (without learning report):**

```json
{}
```

---

## Example 3: Nudge Structure

```python
from ReDNACoreDemo.core.hc_orchestrator import Nudge

nudge = Nudge(
    kind="curiosity_nudge",
    title="Close a high-value gap",
    coach_id="career_coach",
    prompt="Tell me about your recent Python projects and your comfort level with async programming.",
    priority=0.86,
    reason="High impact + low coverage",
    requires_consent=False,
    target="SkillDNA.programming.python_fluency",
    evidence_refs=["gap:SkillDNA.programming"]
)

print(json.dumps(nudge.to_dict(), indent=2))
```

**Output:**

```json
{
  "kind": "curiosity_nudge",
  "title": "Close a high-value gap",
  "coach_id": "career_coach",
  "prompt": "Tell me about your recent Python projects and your comfort level with async programming.",
  "priority": 0.86,
  "reason": "High impact + low coverage",
  "requires_consent": false,
  "target": "SkillDNA.programming.python_fluency",
  "evidence_refs": [
    "gap:SkillDNA.programming"
  ]
}
```

---

## Example 4: Complete API Response (with nudge)

**Request:**

```bash
curl -X POST http://localhost:8015/hc/say \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "message": "what next?",
    "skip_llm": false
  }'
```

**Response:**

```json
{
  "user_id": "TEST",
  "message": "what next?",
  "timestamp": "2025-10-10T02:15:30.123456+00:00",
  "reply_logged": true,
  "llm_provider": "openai",
  "tokens_used": 156,
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Close a high-value gap",
    "coach_id": "career_coach",
    "prompt": "Tell me about your recent Python projects and your comfort level with async programming.",
    "priority": 0.86,
    "reason": "High impact + low coverage",
    "requires_consent": false,
    "target": "SkillDNA.programming.python_fluency",
    "evidence_refs": [
      "gap:SkillDNA.programming"
    ]
  }
}
```

---

## Example 5: Nudge with Consent Required (PaDNA)

**Scenario:** User asks "what next?" and top curiosity item is PaDNA-related.

**Response:**

```json
{
  "user_id": "TEST",
  "message": "what next?",
  "timestamp": "2025-10-10T02:16:00.123456+00:00",
  "reply_logged": true,
  "llm_provider": "openai",
  "tokens_used": 142,
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Close a high-value gap",
    "coach_id": "padna_coach",
    "prompt": "Tell me about your relationship values and what matters most to you in partnerships.",
    "priority": 0.78,
    "reason": "High impact + low coverage",
    "requires_consent": true,
    "target": "PaDNA.relationship_values",
    "evidence_refs": [
      "gap:PaDNA"
    ]
  }
}
```

**Note:** `requires_consent: true` means frontend should show permission dialog before proceeding.

---

## Example 6: No Nudge (Regular Message)

**Request:**

```bash
curl -X POST http://localhost:8015/hc/say \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "message": "I love hiking in the mountains.",
    "skip_llm": false
  }'
```

**Response:**

```json
{
  "user_id": "TEST",
  "message": "I love hiking in the mountains.",
  "timestamp": "2025-10-10T02:17:00.123456+00:00",
  "reply_logged": true,
  "llm_provider": "openai",
  "tokens_used": 134
}
```

**Note:** No `nudge` field because user didn't ask "what next?".

---

## Example 7: Telemetry Log (nudge_shown)

**Location:** `data/learning/nudge_telemetry.jsonl`

```json
{
  "timestamp": "2025-10-10T02:15:30.456789+00:00",
  "user_id": "TEST",
  "event": "nudge_shown",
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Close a high-value gap",
    "coach_id": "career_coach",
    "prompt": "Tell me about your recent Python projects and your comfort level with async programming.",
    "priority": 0.86,
    "reason": "High impact + low coverage",
    "requires_consent": false,
    "target": "SkillDNA.programming.python_fluency",
    "evidence_refs": [
      "gap:SkillDNA.programming"
    ]
  }
}
```

---

## Example 8: Telemetry Log (nudge_suppressed)

**Scenario:** Curiosity agenda has item with priority 0.45 (below 0.65 threshold).

```json
{
  "timestamp": "2025-10-10T02:18:00.456789+00:00",
  "user_id": "TEST",
  "event": "nudge_suppressed",
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Low priority exploration",
    "coach_id": "head_coach",
    "prompt": "Tell me more.",
    "priority": 0.45,
    "reason": "Low priority",
    "requires_consent": false,
    "target": "SomeDNA.low_priority",
    "evidence_refs": []
  },
  "reason": "below_threshold"
}
```

---

## Example 9: Developer Mode Trace

When `developer_mode: true` is set in model_config:

**Console logs:**

```
[HC-Orchestrator] top_target=SkillDNA.programming.python_fluency p=0.86 coach=career_coach consent=false
[Learning] tone_hint=empathetic creativity_bias=0.78
```

**Behavior context includes learning summary:**

```json
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

## Example 10: Fallback Agenda Nudge

**Scenario:** Learning report missing or all priorities below threshold, but fallback enabled.

**Response:**

```json
{
  "nudge": {
    "kind": "curiosity_nudge",
    "title": "Close a high-value gap",
    "coach_id": "career_coach",
    "prompt": "Tell me about your recent work experience and skills.",
    "priority": 0.5,
    "reason": "fallback_agenda_due_to_low_signal",
    "requires_consent": false,
    "target": "SkillDNA.general_exploration",
    "evidence_refs": [
      "fallback:no_telemetry"
    ]
  }
}
```

**Note:** Priority 0.5 is below default threshold (0.65), so to accept fallback nudges, lower `min_nudge_priority` to 0.4 in config.

---

## Example 11: Test Results

```bash
PYTHONPATH=. python3 -m pytest ReDNACoreDemo/tests/test_hc_orchestrator.py -v
```

**Output:**

```
============================= test session starts ==============================
platform darwin -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /Users/davidmakarewicz/Documents/ReDNA_Demos
configfile: pytest.ini
plugins: asyncio-1.2.0, anyio-4.10.0
collecting ... collected 13 items

ReDNACoreDemo/tests/test_hc_orchestrator.py::test_what_next_triggers_nudge PASSED [  7%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_idle_triggers_nudge PASSED [ 15%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_padna_requires_consent PASSED [ 23%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_learning_influences_tone PASSED [ 30%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_no_agenda_returns_none PASSED [ 38%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_nudge_telemetry_logged PASSED [ 46%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_performance_target PASSED [ 53%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_what_next_classifier PASSED [ 61%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_below_threshold_suppressed PASSED [ 69%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_nudge_to_dict PASSED [ 76%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_developer_mode_learning_summary PASSED [ 84%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_photo_namespace_requires_consent PASSED [ 92%]
ReDNACoreDemo/tests/test_hc_orchestrator.py::test_fallback_agenda_generates_nudge PASSED [100%]

============================== 13 passed in 0.05s ==============================
```

---

## Summary

All examples demonstrate:
- ✅ What-next query detection
- ✅ Behavior context enrichment from learning
- ✅ Nudge structure and serialization
- ✅ API response format with optional nudge
- ✅ Permission gating for PaDNA/Photo
- ✅ Telemetry logging
- ✅ Developer mode traces
- ✅ Fallback agenda handling
- ✅ All 13 tests passing
