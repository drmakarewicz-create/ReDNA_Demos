# Head Coach Jarvis Sprint — Blueprint v1.0

**Sprint Objective**: "Aware, Intelligent, Personalized Head Coach"
**Status**: Ready for Overnight Execution
**Estimated Completion**: 6-8 hours (overnight batch)
**Expected JPI Gain**: +25 points (from ~20 baseline to ~45)

---

## Executive Summary

This sprint transforms Head Coach from a reactive chatbot into a **Jarvis-class orchestrator** with:

1. **Situational Awareness** - Real-time user state model (goals, context, emotions)
2. **Intent Intelligence** - NLU layer that understands what user actually needs
3. **Smart Delegation** - Routes requests to optimal coach with confidence scoring
4. **Adaptive Personality** - CReDNA-powered tone that adapts per user and situation
5. **Learning Foundation** - Reflection stub that logs outcomes for future improvement

**Pillars Targeted**: 1 (Awareness), 2 (Intent/Routing), 3 (CReDNA Personality)
**Deferred to Next Sprint**: 4 (Strategic Planning), 5 (Full Reflection Loop)

---

## Current State vs. Target State

### Before Sprint (Current)
- ❌ No working memory of user state
- ❌ Static LLM prompt, no personality adaptation
- ❌ Reacts to messages, doesn't understand intent
- ❌ No delegation intelligence
- ❌ No learning from outcomes
- **Current JPI**: ~20/100 (basic conversation only)

### After Sprint (Target)
- ✅ 4-layer awareness model (core, goal, context, memory)
- ✅ CReDNA envelope for consistent, trainable personality
- ✅ Intent classification with confidence/ambiguity/emotion
- ✅ Rule-based delegation router with policy YAML
- ✅ Reflection logging for future learning
- ✅ New `/hc/v2/interact` endpoint orchestrating full pipeline
- **Target JPI**: ~45/100 (aware, intelligent, personalized)

---

## Pillar 1: Situational Awareness Engine

### Objective
Build real-time user state model with 4-layer caching architecture

### Components

**1.1 Awareness Schema** (`core/schemas/hc_awareness.schema.json`)
```json
{
  "user_core_state": {
    "user_id": "str",
    "active_coach": "str",
    "last_message_time": "timestamp",
    "current_mode": "str",
    "emotional_tone": "positive|neutral|negative|frustrated|curious",
    "curiosity_hotspots": ["trait_path", ...]
  },
  "goal_task_layer": {
    "active_goals": [{"goal_id": "str", "description": "str", "status": "str"}],
    "pending_tasks": [{"task_id": "str", "coach": "str", "status": "str"}],
    "plan_states": [{"plan_id": "str", "progress": 0.0-1.0}],
    "recent_intent_distribution": {"career": 0.4, "personality": 0.3, ...}
  },
  "context_layer": {
    "local_time": "timestamp",
    "day_of_week": "str",
    "timezone": "str",
    "availability_flag": "active|away|busy",
    "recent_external_interactions": []
  },
  "memory_layer": {
    "traits_summary": {"high_rr_domains": [...], "low_rr_domains": [...]},
    "hc_history_summary": {"successful_patterns": [...], "failed_patterns": [...]},
    "meta_feedback_stats": {"avg_satisfaction": 0.0-1.0, "total_interactions": int}
  }
}
```

**1.2 Awareness Builder** (`core/head_coach/situational_awareness.py` ~250 LOC)
- `get_snapshot(user_id) -> AwarenessSnapshot`
- Pulls from: resolved.json, conversation history, curiosity engine, task state
- TTL caching: core (live), goal/task (5 min), context (60 min), memory (24h)
- Emotional tone extraction from last 5 messages via simple sentiment classifier

**1.3 Persistent Store** (`data/users/<user_id>/head_coach/awareness.json`)
- Cached snapshot with timestamps per layer
- Auto-refresh on cache miss

**1.4 API Endpoint**
```python
GET /hc/awareness?user_id=TEST
→ Returns full AwarenessSnapshot
```

### Deliverables
- ✅ `core/schemas/hc_awareness.schema.json` - JSON schema
- ✅ `core/head_coach/situational_awareness.py` - Builder class
- ✅ `core/head_coach/__init__.py` - Module init
- ✅ API endpoint in `core/api.py`
- ✅ Unit tests: `tests/test_hc_awareness.py`

### Success Metrics
- Awareness snapshot builds in <100ms
- Emotional tone accuracy >70% on test messages
- All 4 layers populated for existing users

---

## Pillar 2: Intent Analysis & Delegation Router

### Objective
NLU layer that classifies user messages and routes to optimal coach

### Components

**2.1 Intent Schema** (extended from base proposal)
```python
{
  "category": "question|request|feedback|task|reflection",
  "domain": "career|personality|relationship|belief|photo|system",
  "urgency": "low|medium|high|critical",
  "confidence": 0.0-1.0,  # Classification confidence
  "ambiguity": 0.0-1.0,   # High ambiguity triggers clarification
  "user_emotion": "positive|neutral|negative|frustrated|curious"
}
```

**2.2 Intent Analyzer** (`core/head_coach/intent_analyzer.py` ~200 LOC)
- `classify(message: str, snapshot: AwarenessSnapshot) -> Intent`
- Rule-based classifier using keyword matching + context signals
- Confidence scoring based on match strength
- Ambiguity detection (multiple domain matches, unclear phrasing)
- Emotional tone extracted from snapshot

**2.3 Intent Log** (`data/users/<user_id>/head_coach/intents_log.jsonl`)
- Append-only log of all classified intents
- Used for future ML training

**2.4 Delegation Policy** (`core/head_coach/delegation_policy.yaml`)
```yaml
routing_rules:
  career:
    coach: career_coach
    confidence_boost: 0.1  # if user has career goals active
    cooldown_check: true

  personality:
    coach: personality_test_coach
    confidence_boost: 0.0
    cooldown_check: true

  # ... etc for all domains

escalation_thresholds:
  low_confidence: 0.4  # Below this, ask clarifying question
  high_ambiguity: 0.5  # Above this, ask clarifying question

fallback:
  route: head_coach  # Handle directly
```

**2.5 Delegation Router** (`core/head_coach/delegation_router.py` ~150 LOC)
- `decide(intent: Intent, snapshot: AwarenessSnapshot) -> RoutingDecision`
- Loads policy from YAML
- Applies confidence modifiers based on user state
- Checks coach cooldowns (user opted out, recent failures)
- Returns: `{"coach": "career_coach", "confidence": 0.85, "reasoning": "..."}`

### Deliverables
- ✅ `core/head_coach/intent_analyzer.py`
- ✅ `core/head_coach/delegation_router.py`
- ✅ `core/head_coach/delegation_policy.yaml`
- ✅ Intent logging to JSONL
- ✅ Unit tests: `tests/test_hc_intent_routing.py`

### Success Metrics
- Intent classification accuracy >85% on test set (100 diverse messages)
- Delegation routing accuracy >90% (correct coach selected)
- Ambiguity detection prevents bad delegations (precision >80%)

---

## Pillar 3: CReDNA-Powered Head Coach Personality

### Objective
Head Coach uses CReDNA envelope for consistent, trainable personality

### Components

**3.1 Head Coach Role Overlay** (update `core/credna/overlays/role_overlays.yaml`)
```yaml
head_coach:
  default:
    tone: balanced
    cadence: medium
    formality: neutral
    vocabulary: medium
    hedging: low
    humor: none
    directness: balanced
    empathy: moderate
    # Meta-dimensions (Head Coach only)
    proactiveness: medium      # How early to suggest actions
    curiosity_drive: medium    # How often to check for new data
    authority_level: medium    # Politeness vs directive balance

  analytical:
    tone: neutral
    cadence: medium-fast
    formality: semi-formal
    vocabulary: high
    hedging: low
    humor: none
    directness: direct
    empathy: low
    proactiveness: low
    curiosity_drive: high
    authority_level: high

  supportive:
    tone: warm
    cadence: medium
    formality: casual
    vocabulary: medium
    hedging: medium
    humor: dry
    directness: balanced
    empathy: high
    proactiveness: high
    curiosity_drive: medium
    authority_level: low
```

**3.2 CReDNA Integration** (update `core/head_coach/hc_llm_agent.py`)
- Replace static system prompt with `build_envelope(user_id, "head_coach", intent)`
- Extract intent from routing decision (default/analytical/supportive)
- Build LLM messages using envelope dimensions
- Log envelope used for provenance

**3.3 Extended CReDNA Schema** (update `core/credna/persona_synthesis.py`)
- Add support for meta-dimensions (proactiveness, curiosity_drive, authority_level)
- Only apply these for head_coach, not other coaches

### Deliverables
- ✅ Updated `core/credna/overlays/role_overlays.yaml`
- ✅ Updated `core/head_coach/hc_llm_agent.py`
- ✅ Updated `core/credna/persona_synthesis.py` (meta-dimensions)
- ✅ Workshop UI showing Head Coach CReDNA profile
- ✅ Unit tests: `tests/test_hc_credna.py`

### Success Metrics
- Head Coach responses use CReDNA envelope (verify in policy logs)
- Personality consistency across conversations (low deviation score)
- Users can train Head Coach personality (test feedback loop)

---

## Integration: /hc/v2/interact Endpoint

### Objective
New orchestrator endpoint combining all 3 pillars

### Flow
```python
POST /hc/v2/interact
{
  "user_id": "TEST",
  "message": "I need help preparing for a career change",
  "context": {}  # optional override
}

Pipeline:
1. situational_awareness.get_snapshot(user_id)
   → AwarenessSnapshot

2. intent_analyzer.classify(message, snapshot)
   → Intent {category: "request", domain: "career", confidence: 0.92, ...}

3. delegation_router.decide(intent, snapshot)
   → RoutingDecision {coach: "career_coach", confidence: 0.88, reasoning: "..."}

4. IF route == "head_coach":
     envelope = build_envelope(user_id, "head_coach", intent.urgency)
     response = hc_llm_agent.generate_reply(message, snapshot, envelope)
   ELSE:
     delegate to coach service (future: POST /api/coach/{coach_id}/delegate)

5. reflection_engine.log_interaction(intent, routing, outcome)
   → Append to learning_log.jsonl

6. RETURN {
     "response": "...",
     "coach_used": "head_coach",
     "policy_trace": {
       "intent": {...},
       "routing": {...},
       "envelope": {...}
     }
   }
```

### Implementation (`core/head_coach/hc_v2_interact.py` ~300 LOC)
- Orchestrates full pipeline
- Error handling with graceful fallback
- Policy logging for every interaction
- Feature flag: `use_v2_interact` in config

### Deliverables
- ✅ `core/head_coach/hc_v2_interact.py`
- ✅ API endpoint in `core/api.py`
- ✅ Feature flag in config
- ✅ Legacy `/hc/say` preserved
- ✅ Integration tests: `tests/test_hc_v2_interact.py`

### Success Metrics
- End-to-end latency <500ms (awareness + intent + routing + generation)
- Policy trace captures all decision points
- Graceful fallback on failures (no 500 errors)

---

## Reflection & Learning Foundation

### Objective
Stub logging for future Pillar 5 (full reflection loop)

### Components

**Learning Log** (`data/users/<user_id>/head_coach/learning_log.jsonl`)
```json
{
  "timestamp": "2025-10-08T03:00:00Z",
  "intent": {"category": "request", "domain": "career", "confidence": 0.92},
  "routed_to": "career_coach",
  "success_estimate": 0.8,
  "feedback_signal": "positive",
  "envelope_used": {"tone": "balanced", "proactiveness": "medium"}
}
```

**Reflection Stub** (`core/head_coach/reflection_engine.py` ~50 LOC)
- `log_interaction(intent, routing, outcome) -> None`
- Simple append to JSONL
- No analysis in this sprint (Pillar 5 deferred)

### Deliverables
- ✅ `core/head_coach/reflection_engine.py`
- ✅ Learning log JSONL format
- ✅ Called from `/hc/v2/interact`

---

## Jarvis Progress Index (JPI) Calculator

### Objective
Quantify "Jarvis-ness" with telemetry-based 0-100 score

### Dimensions (5 × 20 points each)

| Dimension | Source | Metric | Current | Target |
|-----------|--------|--------|---------|--------|
| **Contextual Awareness** | awareness engine | % fields non-null × accuracy | 5/20 | 15/20 |
| **Intent Understanding** | intent analyzer | F1 score on test set | 0/20 | 15/20 |
| **Delegation Intelligence** | router logs | correct routing % | 5/20 | 18/20 |
| **Personality Consistency** | CReDNA deltas | low deviation score | 5/20 | 12/20 |
| **Learning Capability** | reflection engine | improvement rate (future) | 5/20 | 5/20 |

**Total Current**: ~20/100 (basic chatbot)
**Total Target**: ~45/100 (aware, intelligent, personalized)
**Gain**: +25 points

### Implementation (`core/head_coach/jpi_calculator.py` ~100 LOC)
- `calculate_jpi(user_id) -> JPIScore`
- Runs test suite to measure each dimension
- Returns JSON with breakdown

### API Endpoint
```python
GET /hc/jpi?user_id=TEST
→ {
  "total_score": 45,
  "dimensions": {
    "contextual_awareness": 15,
    "intent_understanding": 15,
    "delegation_intelligence": 18,
    "personality_consistency": 12,
    "learning_capability": 5
  },
  "baseline": 20,
  "gain": 25
}
```

### Workshop UI
- "Jarvis Progress" gauge showing 0-100 score
- Breakdown by dimension
- Historical trend chart

### Deliverables
- ✅ `core/head_coach/jpi_calculator.py`
- ✅ API endpoint in `core/api.py`
- ✅ Workshop gauge component (React)
- ✅ Test suite for JPI measurement

---

## File Structure & Estimated LOC

```
ReDNACoreDemo/
  core/
    head_coach/
      __init__.py                      # 20 LOC
      situational_awareness.py         # 250 LOC
      intent_analyzer.py               # 200 LOC
      delegation_router.py             # 150 LOC
      delegation_policy.yaml           # 100 lines
      hc_v2_interact.py                # 300 LOC
      reflection_engine.py             # 50 LOC
      jpi_calculator.py                # 100 LOC

    credna/
      persona_synthesis.py             # +50 LOC (meta-dimensions)
      overlays/
        role_overlays.yaml             # +60 lines (head_coach)

    api.py                             # +200 LOC (new endpoints)

  schemas/
    hc_awareness.schema.json           # 150 lines
    hc_intent.schema.json              # 80 lines

  tests/
    test_hc_awareness.py               # 150 LOC
    test_hc_intent_routing.py          # 200 LOC
    test_hc_credna.py                  # 100 LOC
    test_hc_v2_interact.py             # 250 LOC
    test_hc_jpi.py                     # 100 LOC

  data/users/<user_id>/head_coach/
    awareness.json                     # Auto-generated
    intents_log.jsonl                  # Append-only
    learning_log.jsonl                 # Append-only

  docs/
    HEAD_COACH_JARVIS_SPRINT_BLUEPRINT.md   # This file
    HEAD_COACH_V2_ARCHITECTURE.md           # Architecture guide

  web/src/workshop/
    JarvisProgressGauge.tsx            # 150 LOC
    HeadCoachCrednaPanel.tsx           # 100 LOC

Total New Code: ~2,200 LOC
Total Documentation: ~1,500 lines
```

---

## Implementation Order

### Phase 1: Foundation (Est: 2 hours)
1. Create directory structure
2. Implement awareness schema + builder
3. Implement intent analyzer (rule-based)
4. Write unit tests for Phase 1

### Phase 2: Routing & Integration (Est: 2 hours)
5. Implement delegation router + policy YAML
6. Update CReDNA with meta-dimensions
7. Update hc_llm_agent for CReDNA integration
8. Write unit tests for Phase 2

### Phase 3: Orchestration (Est: 2 hours)
9. Implement hc_v2_interact orchestrator
10. Add API endpoints
11. Implement reflection stub
12. Write integration tests

### Phase 4: JPI & Workshop (Est: 2 hours)
13. Implement JPI calculator
14. Add JPI endpoint
15. Build Workshop gauge component
16. Write JPI tests

### Phase 5: Documentation & Verification (Est: 1 hour)
17. Write architecture guide
18. Run full test suite
19. Calculate baseline vs target JPI
20. Generate sprint completion report

---

## Test Plan

### Unit Tests (pytest)
- `test_hc_awareness.py` - Snapshot building, caching, TTL
- `test_hc_intent_routing.py` - Intent classification, routing decisions
- `test_hc_credna.py` - Envelope generation with meta-dimensions
- `test_hc_v2_interact.py` - End-to-end pipeline
- `test_hc_jpi.py` - JPI calculation accuracy

### Integration Tests
- Full pipeline: message → awareness → intent → routing → response
- Delegation to different coaches based on domain
- CReDNA personality consistency across messages
- Policy trace completeness

### Performance Tests
- Awareness snapshot build <100ms
- Intent classification <50ms
- End-to-end /hc/v2/interact <500ms
- JPI calculation <1s

### Acceptance Criteria
- ✅ All unit tests pass (>90% coverage)
- ✅ Integration tests pass (10 scenarios)
- ✅ Performance benchmarks met
- ✅ JPI score ≥45/100 (target met)
- ✅ Workshop UI shows Jarvis gauge
- ✅ Policy logs capture all decisions

---

## Risks & Safeguards

| Risk | Mitigation |
|------|------------|
| Awareness snapshot too slow | Cache aggressively; lazy load memory layer |
| Intent classifier low accuracy | Start with conservative rules; log failures for ML training later |
| Delegation router routes incorrectly | Policy YAML human-editable; add confidence thresholds |
| CReDNA envelope breaks existing coaches | Feature flag `use_credna_hc`; keep legacy path |
| JPI calculation too complex | Use simple test suite; defer ML-based metrics |
| Breaking changes to existing API | Preserve `/hc/say`; introduce `/hc/v2/interact` separately |

---

## Stretch Goals (If Time Permits)

1. **Emotional Tone ML Model** - Train small classifier on labeled sentiment data
2. **Multi-Step Intent Decomposition** - Break complex requests into subtasks
3. **Delegation Feedback Loop** - User can rate delegation quality
4. **Workshop "Awareness Inspector"** - UI showing live awareness snapshot
5. **JPI Trend Tracking** - Historical JPI scores over time

---

## Success Metrics Summary

**Primary Metrics**:
- JPI Score: 20 → 45 (+25 points) ✅
- Intent Classification Accuracy: >85% ✅
- Delegation Routing Accuracy: >90% ✅
- End-to-End Latency: <500ms ✅

**Secondary Metrics**:
- Code Coverage: >90% ✅
- Policy Trace Completeness: 100% ✅
- Workshop UI Functional: Yes ✅
- Zero Breaking Changes: Yes ✅

---

## Next Sprint Preview (Pillars 4-5)

**Pillar 4: Strategic Planning** - Multi-step goal decomposition, coach orchestration, progress tracking

**Pillar 5: Reflection & Learning** - Full learning loop, delegation strategy improvement, ML classifier training

**Estimated Timeline**: 2-3 weeks after Sprint 1 stabilizes

---

## Handoff Checklist

Before execution:
- ✅ Sprint Blueprint reviewed and approved
- ✅ File structure planned
- ✅ Dependencies identified (none - foundation is complete)
- ✅ Test data prepared (100 diverse user messages for intent classification)
- ✅ Overnight execution environment ready

After execution:
- ✅ All unit tests pass
- ✅ Integration tests pass
- ✅ JPI calculated and ≥45
- ✅ Workshop UI functional
- ✅ Documentation complete
- ✅ Demo video recorded (optional)

---

**Blueprint Status**: ✅ READY FOR EXECUTION
**Estimated Execution Time**: 6-8 hours (overnight)
**Expected Outcome**: Head Coach v2 - Aware, Intelligent, Personalized
