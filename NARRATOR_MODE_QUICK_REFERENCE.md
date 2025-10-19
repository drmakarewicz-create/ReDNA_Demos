# Narrator Mode — Quick Reference Card

**Benchmark:** 4.A2 | **Status:** ✅ Complete | **LOC:** 2,425

---

## What It Does

Narrator Mode provides **transparent reasoning traces** for all Head Coach decisions:
- 🔄 Coach switches
- 🎭 Tone shifts
- 🔍 Curiosity triggers
- 🤖 Codex actions
- 📋 Delegations

Each trace explains **why** a decision was made, with confidence scores and impact levels.

---

## Quick Access

### DevX UI
```
http://localhost:8100 → 🗣 Narrator
```

### API
```bash
# Get traces
curl "http://localhost:8015/coach/narrator?user_id=TEST&limit=20"

# Export markdown
curl "http://localhost:8015/coach/narrator/export?user_id=TEST&format=markdown" > timeline.md
```

### Python
```python
from ReDNACoreDemo.core.hc_narrator import get_narrator

narrator = get_narrator()

narrator.record_coach_switch(
    user_id="TEST",
    from_coach="head_coach",
    to_coach="career_coach",
    reasoning_factors=["Reason 1", "Reason 2"],
    confidence=0.85,
    context_version=42
)
```

---

## Key Files

| Component | File | LOC |
|-----------|------|-----|
| Engine | `core/hc_narrator.py` | 455 |
| API | `core/api.py` | +180 |
| Frontend | `devx/frontend/src/routes/narrator-timeline/` | 540 |
| Tests | `tests/test_narrator_mode.py` | 499 |
| Docs | `docs/NARRATOR_MODE_PHASE1.md` | 595 |

---

## Decision Types

| Type | Impact | Example |
|------|--------|---------|
| `coach_switch` | High | head_coach → career_coach |
| `tone_shift` | Medium | More encouraging |
| `curiosity_trigger` | Medium | Explore SkillDNA.Programming |
| `codex_action` | High | Propose Empathy refinement |
| `delegation` | High | Delegate to Photo Coach |

---

## Confidence Badges

- 🟢 **Green** (≥80%) - Strong evidence
- 🟡 **Amber** (60-80%) - Reasonable evidence
- 🔴 **Red** (<60%) - Weak evidence

---

## API Endpoints

```
GET  /coach/narrator              # Retrieve traces
POST /coach/narrator/annotate     # Add annotation
GET  /coach/narrator/export       # Export JSON/Markdown
```

---

## Filter Options

- **Decision Type:** All | Coach Switches | Tone Shifts | Curiosity | Codex Actions
- **Session ID:** Filter by session
- **Min Confidence:** 0.0 - 1.0 threshold
- **Limit:** 1-100 traces

---

## Performance

- API: **~45 ms** (target: <200 ms) ✅
- Narrative build: **~50 ms** (target: <300 ms) ✅
- UI render: **~250 ms** (target: <300 ms) ✅

---

## Tests

```bash
# Run all tests
pytest ReDNACoreDemo/tests/test_narrator_mode.py -v

# Run verification
./ReDNACoreDemo/scripts/verify_narrator_mode.sh
```

**Result:** 14/14 tests pass ✅

---

## Integration Example

```python
# In HC orchestrator or session manager
from ReDNACoreDemo.core.hc_narrator import get_narrator

narrator = get_narrator()

# When switching coaches
if new_coach != current_coach:
    narrator.record_coach_switch(
        user_id=user_id,
        from_coach=current_coach,
        to_coach=new_coach,
        reasoning_factors=[
            f"Intent: {intent}",
            f"Curiosity priority: {priority:.2f}",
            f"Sentiment: {sentiment:.0%}"
        ],
        confidence=decision_confidence,
        context_version=context.version,
        session_id=session.id
    )
```

---

## Trace Storage

**Location:** `prompts/insights/narrator_traces.jsonl`

Each line is a JSON trace object:
```json
{
  "ts": "2025-10-11T15:42:33Z",
  "user_id": "TEST",
  "context_version": 87,
  "decision": "Switch from head_coach to career_coach",
  "reasoning": ["Reason 1", "Reason 2", "Reason 3"],
  "confidence": 0.89,
  "impact": "high",
  "duration_ms": 38,
  "session_id": "session_xyz",
  "metadata": {
    "type": "coach_switch",
    "from_coach": "head_coach",
    "to_coach": "career_coach"
  }
}
```

---

## DevX Features

- ✅ Session-grouped timeline
- ✅ Filter chips
- ✅ Color-coded confidence
- ✅ Context version links → Chorus Preview
- ✅ Export JSON/Markdown
- ✅ Statistics dashboard

---

## Documentation

📘 **Full Docs:** [ReDNACoreDemo/docs/NARRATOR_MODE_PHASE1.md](ReDNACoreDemo/docs/NARRATOR_MODE_PHASE1.md)

📊 **Completion Report:** [BENCHMARK_4A2_COMPLETE.md](BENCHMARK_4A2_COMPLETE.md)

📋 **Summary:** [NARRATOR_MODE_SUMMARY.md](NARRATOR_MODE_SUMMARY.md)

🧪 **Example Trace:** [NARRATOR_MODE_EXAMPLE_TRACE.json](NARRATOR_MODE_EXAMPLE_TRACE.json)

---

## Next Phase

**4.A3 - Runtime Tuning Loop**

- Analyze low-confidence decision patterns
- Suggest prompt/threshold tuning
- A/B test improvements
- Auto-deploy with approval

**Estimated LOC:** ~1,500 | **Timeline:** 1-2 weeks

---

## One-Sentence Summary

**"Narrator Mode Phase 1 implemented — Head Coach now records and explains reasoning for major decisions with DevX timeline visibility."**
