# ReDNA AI-First Quick Reference Card

**Print this and keep it visible while coding** 📋

---

## The Philosophy in One Sentence

> "ReDNA is not a deterministic program. It is a living, adaptive intelligence framework. AI is not an add-on—AI is the organism."

---

## Pre-Commit Checklist ✅

Before committing ANY code, ask yourself:

- [ ] **Where does intelligence live here?** (If nowhere, add an AI reasoning hook)
- [ ] **Can this decision learn and adapt?** (If no, replace constant with learned policy)
- [ ] **Can I explain WHY this happened?** (If no, generate a Why-Card)
- [ ] **What does the system want to know next?** (If uncertain, log curiosity)
- [ ] **How does this relate to other beliefs?** (If isolated, add cross-trait reasoning)

---

## The 10 Commandments (From Philosophy Doc)

1. **AI at Every Layer** - Every component must think, infer, and adapt via LLM
2. **Dynamic Behavior** - Determinism for control only; AI drives decisions
3. **Adaptation Over Perfection** - System revises itself based on evidence
4. **Curiosity Before Certainty** - Ask instead of assume
5. **Holism Over Isolation** - Traits reason together, not alone
6. **Explainability** - Every decision has a natural-language "why"
7. **Forgiving Intelligence** - Handle noise gracefully, not with rejection
8. **Scientific Curiosity** - Hypothesize, test, update, record
9. **Emotional Awareness** - Be smart AND empathetic
10. **Self-Evolution** - Improve automatically with better models/data

---

## Code Patterns to AVOID ❌

```python
# ❌ Fixed threshold with no learning path
if rr_score >= 780:
    promote(trait)

# ❌ Hard rejection with no explanation
if not is_valid(value):
    raise ValueError("Invalid input")

# ❌ Single-trait decision without context
promote(trait, based_only_on=trait.rr)

# ❌ Silent decision without logging reasoning
update_belief(trait, value)  # Why? Based on what?

# ❌ Curiosity calculated but unused
curiosity = compute_curiosity(trait)
# ...then nothing happens with it
```

---

## Code Patterns to EMBRACE ✅

```python
# ✅ Adaptive threshold that learns
threshold = adaptive_policy.compute_threshold(trait_id, history)
if rr_score >= threshold:
    promote(trait, why_card=generate_explanation(...))

# ✅ Graceful handling with repair
if not is_valid(value):
    repaired = llm_repair_schema(value)
    log_attempted_repair(original=value, repaired=repaired)

# ✅ Cross-trait holistic reasoning
promote_candidates = holistic_inference(
    newly_extracted=traits,
    full_context=snapshot
)

# ✅ Explainable decision with reasoning chain
update_belief(
    trait,
    value,
    evidence=evidence,
    why_card=generate_why_card(...),
    confidence_interval=[lower, upper]
)

# ✅ Curiosity drives behavior
if curiosity > 0.7:
    adjusted_threshold = base_threshold * 0.85  # Ask sooner
```

---

## Layer Responsibilities (Quick Lookup)

| Layer | AI Should Do | Determinism Can Do |
|-------|-------------|-------------------|
| **UCNRR** | Extract, score, normalize via LLM | Cache results, enforce timeouts |
| **Core** | Update beliefs, resolve conflicts, infer | Store snapshots, enforce schema |
| **Northstar** | Plan conversation, adapt tone | Track conversation history |
| **DevX** | Diagnose issues, suggest fixes | Display metrics, execute commands |

---

## Key Metrics to Track

- **AI Coverage**: % of decisions using LLM vs. fixed logic (target: 95%)
- **Explainability**: % of promotions with Why-Cards (target: 100%)
- **Adaptivity**: % of thresholds that learn from history (target: 80%)
- **Holism**: % of promotions using cross-trait inference (target: 30%)
- **Curiosity**: % of uncertain traits that trigger exploration (target: 50%)

---

## When to Use LLM vs. Heuristic

**Use LLM for** (Intelligence):
- Trait extraction from natural language
- Contradiction resolution ("which source is more reliable?")
- Cross-trait inference ("what else can we infer?")
- Why-Card generation ("explain this belief")
- Threshold adjustment reasoning ("why change from 780 to 763?")
- Diagnostic explanations ("why is this slow?")

**Use Heuristic for** (Safety & Speed):
- Input validation (format checks, null checks)
- Cache lookup (exact match on previous query)
- Fallback when LLM unavailable (graceful degradation)
- Safety bounds (threshold can't drop below 50% of base)
- Rate limiting (max N LLM calls per minute)

---

## Common Questions

**Q: "Isn't this expensive/slow?"**
A: Batch calls, cache aggressively, use fast models (phi3) for simple tasks. Graceful degradation prevents outages.

**Q: "What if LLM hallucinates?"**
A: Schema constraints, ensemble voting, confidence thresholds, human oversight for critical decisions.

**Q: "Don't we lose control?"**
A: No! Deterministic controls preserved for start/stop, debug, overrides. AI drives behavior, not infrastructure.

**Q: "How do we debug AI decisions?"**
A: Why-Cards, reasoning graphs, replay tools. Every decision is explainable and traceable.

**Q: "What about privacy/ethics?"**
A: LLM calls are logged, consent-aware, with PII scrubbing. Emotional intelligence includes ethical awareness.

---

## The Acid Test

**Before merging, ask**: "If this code ran for a year without updates, would it get smarter or just older?"

- If **smarter**: ✅ It learns, adapts, has feedback loops
- If **just older**: ❌ It's static, add learning mechanisms

---

## Quick Links

- [Full Philosophy Doc](ReDNA_System_Philosophy_v1.md)
- [Developer Handoff Preamble](ReDNA_Developer_Handoff_Preamble.md)
- [Detailed Architecture Audit](AI_First_Architecture_Audit.md)
- [Integration Summary](AI_Philosophy_Integration_Summary.md)

---

## Remember

**"Every engineering decision must preserve the system's ability to reason, learn, and improve autonomously."**

— *ReDNA System Philosophy v1.0, Section 8*

---

*Print, laminate, and keep near your keyboard* 🖨️
