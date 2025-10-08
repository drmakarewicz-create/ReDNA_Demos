# Overnight Mega Prompt — Head Coach Jarvis Sprint v1.0

**Execution Target**: Claude Code Agent
**Estimated Time**: 6-8 hours
**Expected Outcome**: Head Coach v2 - Aware, Intelligent, Personalized
**JPI Target**: 45/100 (+25 from baseline)

---

## Prompt to Claude Code — Execute Head Coach Jarvis Sprint

Claude, please execute the Head Coach Jarvis Sprint as specified in `HEAD_COACH_JARVIS_SPRINT_BLUEPRINT.md`. This is an autonomous overnight batch that will transform Head Coach from a reactive chatbot into a Jarvis-class orchestrator.

### Sprint Objectives

Implement **3 core pillars** that advance Head Coach toward "Jarvis Standard":

1. **Situational Awareness Engine** - 4-layer user state model (core, goal, context, memory)
2. **Intent Analysis & Delegation Router** - NLU layer with smart coach routing
3. **CReDNA-Powered Personality** - Adaptive, trainable personality via CReDNA

### Implementation Order

Execute in **5 sequential phases**:

---

## Phase 1: Situational Awareness Foundation (Est: 2 hours)

### 1.1 Create Directory Structure

```bash
mkdir -p ReDNACoreDemo/core/head_coach
mkdir -p ReDNACoreDemo/schemas
mkdir -p ReDNACoreDemo/tests
mkdir -p data/users/TEST/head_coach
```

### 1.2 Implement Awareness Schema

**File**: `ReDNACoreDemo/schemas/hc_awareness.schema.json`

Create JSON schema defining the 4-layer awareness model:
- user_core_state: user_id, active_coach, last_message_time, current_mode, emotional_tone, curiosity_hotspots
- goal_task_layer: active_goals, pending_tasks, plan_states, recent_intent_distribution
- context_layer: local_time, day_of_week, timezone, availability_flag, recent_external_interactions
- memory_layer: traits_summary, hc_history_summary, meta_feedback_stats

**Requirements**:
- Follow JSON Schema draft-07 format
- Include descriptions for all fields
- Set required vs optional fields appropriately

### 1.3 Implement Awareness Builder

**File**: `ReDNACoreDemo/core/head_coach/situational_awareness.py` (~250 LOC)

Implement `AwarenessEngine` class with:

```python
class AwarenessEngine:
    def get_snapshot(user_id: str, force_refresh: bool = False) -> AwarenessSnapshot:
        """
        Build 4-layer awareness snapshot with TTL caching.

        Caching strategy:
        - user_core_state: always fresh (no cache)
        - goal_task_layer: 5 min TTL
        - context_layer: 60 min TTL
        - memory_layer: 24h TTL
        """
        # Load from cache if valid
        # Refresh expired layers
        # Build from sources:
        #   - core: read_user_state(user_id)
        #   - goal/task: load from task files
        #   - context: datetime, timezone
        #   - memory: aggregated from resolved.json
        # Extract emotional_tone from last 5 conversation messages
        # Save updated cache
        # Return AwarenessSnapshot
```

**Key methods**:
- `_build_core_state(user_id)` - Read from resolved.json, conversation history
- `_build_goal_task_layer(user_id)` - Read from task files, infer recent intents
- `_build_context_layer()` - Datetime, timezone, availability heuristics
- `_build_memory_layer(user_id)` - Aggregate from ReDNA traits
- `_extract_emotional_tone(messages)` - Simple sentiment classifier (keyword-based for now)
- `_load_cache(user_id)` - Read awareness.json with TTL checks
- `_save_cache(user_id, snapshot)` - Write awareness.json with timestamps

**Dependencies**:
- `from ..storage import read_user_state`
- `from ..curiosity_engine import CuriosityEngine`
- `from datetime import datetime, timezone, timedelta`
- `from pathlib import Path`
- `import json`

**Cache file format** (`data/users/<user_id>/head_coach/awareness.json`):
```json
{
  "snapshot": {...},
  "cache_timestamps": {
    "user_core_state": "2025-10-08T03:00:00Z",
    "goal_task_layer": "2025-10-08T02:55:00Z",
    "context_layer": "2025-10-08T02:00:00Z",
    "memory_layer": "2025-10-07T03:00:00Z"
  }
}
```

### 1.4 Add API Endpoint

**File**: `ReDNACoreDemo/core/api.py` (append to existing)

Add endpoint:
```python
@app.get("/hc/awareness")
def get_awareness_snapshot(
    user_id: str = Query(..., description="User ID"),
    force_refresh: bool = Query(False, description="Force cache refresh")
):
    """
    Get Head Coach situational awareness snapshot for user.

    Returns 4-layer model: core state, goals/tasks, context, memory.
    """
    from .head_coach.situational_awareness import AwarenessEngine

    engine = AwarenessEngine()
    snapshot = engine.get_snapshot(user_id, force_refresh=force_refresh)

    return snapshot
```

### 1.5 Unit Tests

**File**: `ReDNACoreDemo/tests/test_hc_awareness.py` (~150 LOC)

Test cases:
- `test_awareness_snapshot_builds` - Can build snapshot for existing user
- `test_cache_ttl_respected` - Layers refresh based on TTL
- `test_emotional_tone_extraction` - Sentiment classifier works
- `test_curiosity_hotspots_populated` - Uses curiosity engine
- `test_cache_persists` - Snapshot saved and loaded correctly

---

## Phase 2: Intent Analysis & Delegation Router (Est: 2 hours)

### 2.1 Intent Analyzer

**File**: `ReDNACoreDemo/core/head_coach/intent_analyzer.py` (~200 LOC)

Implement `IntentAnalyzer` class:

```python
class IntentAnalyzer:
    def classify(message: str, snapshot: AwarenessSnapshot) -> Intent:
        """
        Classify user message into structured intent.

        Returns:
        {
          "category": "question|request|feedback|task|reflection",
          "domain": "career|personality|relationship|belief|photo|system",
          "urgency": "low|medium|high|critical",
          "confidence": 0.0-1.0,
          "ambiguity": 0.0-1.0,
          "user_emotion": "positive|neutral|negative|frustrated|curious"
        }
        """
```

**Classification logic** (rule-based for now):
- **Category**: Keyword matching (e.g., "help me" → request, "why" → question)
- **Domain**: Keyword matching + context from snapshot
  - career: "job", "resume", "interview", "promotion", "skills"
  - personality: "personality", "traits", "OCEAN", "motivation"
  - relationship: "partner", "friendship", "conflict", "communication"
  - belief: "values", "beliefs", "ethics", "philosophy"
  - photo: "appearance", "style", "photo", "looks"
  - system: "coach", "settings", "help", "how to"
- **Urgency**: Keyword matching ("urgent", "asap", "critical") + time phrases
- **Confidence**: Based on match strength (multiple keywords → higher confidence)
- **Ambiguity**: Multiple domain matches OR unclear phrasing
- **User Emotion**: Use snapshot.user_core_state.emotional_tone

**Methods**:
- `_classify_category(message)` - Rule-based category detection
- `_classify_domain(message, snapshot)` - Keyword + context matching
- `_classify_urgency(message)` - Time-based urgency detection
- `_calculate_confidence(matches)` - Confidence scoring based on match strength
- `_detect_ambiguity(domain_matches)` - High when multiple domains match

### 2.2 Intent Logging

**File**: `data/users/<user_id>/head_coach/intents_log.jsonl`

Append each classified intent:
```json
{"timestamp": "...", "message": "...", "intent": {...}}
```

### 2.3 Delegation Policy

**File**: `ReDNACoreDemo/core/head_coach/delegation_policy.yaml`

```yaml
routing_rules:
  career:
    coach: career_coach
    confidence_boost: 0.1  # Boost if user has active career goals
    cooldown_check: true
    min_confidence: 0.5

  personality:
    coach: personality_test_coach
    confidence_boost: 0.0
    cooldown_check: true
    min_confidence: 0.5

  relationship:
    coach: relationship_coach
    confidence_boost: 0.1  # Boost if recent relationship activity
    cooldown_check: true
    min_confidence: 0.5

  belief:
    coach: beliefdna_coach
    confidence_boost: 0.0
    cooldown_check: true
    min_confidence: 0.5

  photo:
    coach: photo_coach
    confidence_boost: 0.0
    cooldown_check: true
    min_confidence: 0.5

  system:
    coach: head_coach  # Handle system queries directly
    confidence_boost: 0.0
    cooldown_check: false
    min_confidence: 0.3

escalation_thresholds:
  low_confidence: 0.4     # Below this, ask clarifying question
  high_ambiguity: 0.5     # Above this, ask clarifying question

fallback:
  route: head_coach
  reasoning: "No clear domain match or low confidence"
```

### 2.4 Delegation Router

**File**: `ReDNACoreDemo/core/head_coach/delegation_router.py` (~150 LOC)

Implement `DelegationRouter` class:

```python
class DelegationRouter:
    def __init__(self):
        self.policy = self._load_policy()

    def decide(intent: Intent, snapshot: AwarenessSnapshot) -> RoutingDecision:
        """
        Decide which coach should handle this request.

        Returns:
        {
          "coach": "career_coach",
          "confidence": 0.85,
          "reasoning": "Career domain with high confidence, user has active career goals",
          "escalation": None  # or {"type": "clarify", "question": "..."}
        }
        """
        # Get routing rule for domain
        # Apply confidence boosts from snapshot context
        # Check coach cooldowns (future: check opt-out flags)
        # Check escalation thresholds
        # Return routing decision
```

**Methods**:
- `_load_policy()` - Load delegation_policy.yaml
- `_apply_confidence_boosts(intent, snapshot, rule)` - Context-based adjustments
- `_check_escalation(intent)` - Determine if clarification needed
- `_check_cooldown(coach, user_id)` - Future: check opt-out/failure state

### 2.5 Unit Tests

**File**: `ReDNACoreDemo/tests/test_hc_intent_routing.py` (~200 LOC)

Test cases:
- `test_intent_classification_career` - "Help me with my resume" → career domain
- `test_intent_classification_personality` - "Take a personality test" → personality
- `test_confidence_scoring` - Multiple keywords → high confidence
- `test_ambiguity_detection` - Unclear message → high ambiguity
- `test_routing_decision_career` - Career intent → career_coach
- `test_routing_escalation_low_confidence` - Low confidence → clarify
- `test_routing_fallback` - Unknown domain → head_coach

---

## Phase 3: CReDNA Integration & Orchestration (Est: 2 hours)

### 3.1 Update CReDNA for Head Coach

**File**: `ReDNACoreDemo/core/credna/overlays/role_overlays.yaml` (update)

Add Head Coach overlay with meta-dimensions:

```yaml
head_coach:
  default:
    # Base CReDNA dimensions
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

### 3.2 Extend CReDNA for Meta-Dimensions

**File**: `ReDNACoreDemo/core/credna/persona_synthesis.py` (update)

Add meta-dimension support:

```python
# Update DIMENSION_CATEGORIES to include:
DIMENSION_CATEGORIES = {
    # ... existing dimensions ...
    "proactiveness": ["passive", "balanced", "anticipatory"],
    "curiosity_drive": ["low", "medium", "exploratory"],
    "authority_level": ["deferential", "balanced", "assertive"]
}

# Update _blend_layers() to handle meta-dimensions
# Update _get_default_overlay() to include meta-dimensions for head_coach
```

### 3.3 Update HC LLM Agent for CReDNA

**File**: `ReDNACoreDemo/core/head_coach/hc_llm_agent.py` (update existing)

Replace static system prompt with CReDNA envelope:

```python
def generate_reply(
    user_id: str,
    user_message: str,
    state_snapshot: Dict[str, Any],
    model_config: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    intent_mode: str = "default"  # NEW: default|analytical|supportive
) -> Dict[str, Any]:
    """
    Generate LLM reply using CReDNA envelope for personality.
    """
    from ..credna.persona_synthesis import build_envelope

    # Build Head Coach personality envelope
    envelope = build_envelope(user_id, "head_coach", intent=intent_mode)

    # Build system message using envelope dimensions
    system_msg = _build_credna_system_message(state_snapshot, envelope)

    # ... rest of existing logic ...
```

**New helper**:
```python
def _build_credna_system_message(state_snapshot, envelope):
    """
    Build system prompt using CReDNA envelope dimensions.

    Incorporates:
    - Base dimensions: tone, formality, directness, empathy
    - Meta-dimensions: proactiveness, curiosity_drive, authority_level
    - State snapshot: high_curiosity_traits, delegation_recommendations
    """
    # Format envelope into natural language personality description
    # Merge with existing state snapshot logic
    # Return complete system message
```

### 3.4 Implement HC v2 Orchestrator

**File**: `ReDNACoreDemo/core/head_coach/hc_v2_interact.py` (~300 LOC)

Main orchestrator combining all pillars:

```python
class HeadCoachV2:
    def __init__(self):
        self.awareness_engine = AwarenessEngine()
        self.intent_analyzer = IntentAnalyzer()
        self.delegation_router = DelegationRouter()
        self.reflection_engine = ReflectionEngine()

    def interact(user_id: str, message: str, context: dict = None) -> Response:
        """
        Full Head Coach v2 interaction pipeline.

        Pipeline:
        1. Get situational awareness snapshot
        2. Classify intent
        3. Route to appropriate handler
        4. Generate response (via HC or delegate)
        5. Log interaction for learning
        6. Return response + policy trace
        """
        # 1. Awareness
        snapshot = self.awareness_engine.get_snapshot(user_id)

        # 2. Intent
        intent = self.intent_analyzer.classify(message, snapshot)

        # 3. Routing
        routing = self.delegation_router.decide(intent, snapshot)

        # 4. Response generation
        if routing.escalation:
            # Ask clarifying question
            response = self._generate_clarification(routing.escalation)
        elif routing.coach == "head_coach":
            # Handle directly with CReDNA
            intent_mode = self._map_intent_to_mode(intent)
            response = hc_llm_agent.generate_reply(
                user_id, message, snapshot,
                model_config=DEFAULT_CONFIG,
                intent_mode=intent_mode
            )
        else:
            # Future: Delegate to specialist coach
            response = {"content": f"[Delegating to {routing.coach}...]"}

        # 5. Reflection
        self.reflection_engine.log_interaction(
            intent, routing, response, snapshot
        )

        # 6. Return with trace
        return {
            "response": response["content"],
            "coach_used": routing.coach,
            "policy_trace": {
                "awareness": snapshot,
                "intent": intent,
                "routing": routing,
                "envelope_used": envelope if routing.coach == "head_coach" else None
            }
        }
```

### 3.5 Add API Endpoint

**File**: `ReDNACoreDemo/core/api.py` (append)

```python
@app.post("/hc/v2/interact")
async def hc_v2_interact(request: Request):
    """
    Head Coach v2 interaction endpoint.

    Combines:
    - Situational awareness
    - Intent analysis
    - Delegation routing
    - CReDNA personality
    - Reflection logging
    """
    from .head_coach.hc_v2_interact import HeadCoachV2

    body = await request.json()
    user_id = body.get("user_id")
    message = body.get("message")
    context = body.get("context", {})

    if not user_id or not message:
        raise HTTPException(status_code=400, detail="user_id and message required")

    hc = HeadCoachV2()
    result = hc.interact(user_id, message, context)

    return result
```

### 3.6 Reflection Stub

**File**: `ReDNACoreDemo/core/head_coach/reflection_engine.py` (~50 LOC)

```python
class ReflectionEngine:
    def log_interaction(
        intent: Intent,
        routing: RoutingDecision,
        response: Response,
        snapshot: AwarenessSnapshot
    ) -> None:
        """
        Log interaction for future learning (Pillar 5).

        Appends to learning_log.jsonl:
        {
          "timestamp": "...",
          "intent": {...},
          "routed_to": "career_coach",
          "success_estimate": 0.8,  # Heuristic for now
          "feedback_signal": "positive",  # Future: from user
          "envelope_used": {...}
        }
        """
        user_id = snapshot["user_core_state"]["user_id"]
        log_file = Path(f"data/users/{user_id}/head_coach/learning_log.jsonl")
        log_file.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intent": intent,
            "routed_to": routing["coach"],
            "success_estimate": 0.8,  # Placeholder
            "feedback_signal": "positive",  # Placeholder
            "envelope_used": routing.get("envelope")
        }

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

### 3.7 Integration Tests

**File**: `ReDNACoreDemo/tests/test_hc_v2_interact.py` (~250 LOC)

End-to-end tests:
- `test_hc_v2_career_delegation` - Career message → routes to career_coach
- `test_hc_v2_handles_directly` - System query → handled by head_coach
- `test_hc_v2_clarification` - Ambiguous message → asks clarifying question
- `test_hc_v2_credna_envelope` - HC response uses CReDNA personality
- `test_hc_v2_policy_trace` - Full trace captured
- `test_hc_v2_reflection_logged` - Interaction logged to learning_log.jsonl

---

## Phase 4: JPI Calculator & Workshop (Est: 2 hours)

### 4.1 JPI Calculator

**File**: `ReDNACoreDemo/core/head_coach/jpi_calculator.py` (~100 LOC)

```python
class JPICalculator:
    def calculate(user_id: str) -> JPIScore:
        """
        Calculate Jarvis Progress Index (0-100).

        Dimensions (20 points each):
        1. Contextual Awareness - % fields non-null × accuracy
        2. Intent Understanding - F1 score on test set
        3. Delegation Intelligence - correct routing %
        4. Personality Consistency - low deviation score
        5. Learning Capability - improvement rate (future)
        """
        scores = {}

        # 1. Contextual Awareness (0-20)
        snapshot = AwarenessEngine().get_snapshot(user_id)
        awareness_score = self._score_awareness(snapshot)
        scores["contextual_awareness"] = awareness_score

        # 2. Intent Understanding (0-20)
        intent_score = self._score_intent_classification(user_id)
        scores["intent_understanding"] = intent_score

        # 3. Delegation Intelligence (0-20)
        routing_score = self._score_delegation_routing(user_id)
        scores["delegation_intelligence"] = routing_score

        # 4. Personality Consistency (0-20)
        consistency_score = self._score_personality_consistency(user_id)
        scores["personality_consistency"] = consistency_score

        # 5. Learning Capability (0-20)
        learning_score = 5  # Placeholder - full Pillar 5 needed
        scores["learning_capability"] = learning_score

        total = sum(scores.values())

        return {
            "total_score": total,
            "dimensions": scores,
            "baseline": 20,
            "gain": total - 20
        }
```

**Scoring methods**:
- `_score_awareness(snapshot)` - Count non-null fields, check accuracy
- `_score_intent_classification(user_id)` - Run test set, calculate F1
- `_score_delegation_routing(user_id)` - Analyze routing logs, accuracy %
- `_score_personality_consistency(user_id)` - Check CReDNA delta variance

### 4.2 JPI API Endpoint

**File**: `ReDNACoreDemo/core/api.py` (append)

```python
@app.get("/hc/jpi")
def get_jpi_score(user_id: str = Query(..., description="User ID")):
    """
    Calculate Jarvis Progress Index for Head Coach.

    Returns 0-100 score with dimension breakdown.
    """
    from .head_coach.jpi_calculator import JPICalculator

    calc = JPICalculator()
    score = calc.calculate(user_id)

    return score
```

### 4.3 Workshop Gauge Component

**File**: `web/src/workshop/JarvisProgressGauge.tsx` (~150 LOC)

React component showing:
- Circular gauge 0-100
- Dimension breakdown (5 bars)
- Baseline vs current comparison
- Historical trend (future)

```tsx
export function JarvisProgressGauge({ userId }: { userId: string }) {
  const [jpiScore, setJpiScore] = useState(null);

  useEffect(() => {
    fetch(`${CORE_API_BASE}/hc/jpi?user_id=${userId}`)
      .then(res => res.json())
      .then(data => setJpiScore(data));
  }, [userId]);

  if (!jpiScore) return <div>Loading...</div>;

  return (
    <div className="jarvis-gauge">
      <CircularGauge value={jpiScore.total_score} max={100} />
      <DimensionBreakdown dimensions={jpiScore.dimensions} />
      <GainIndicator baseline={jpiScore.baseline} gain={jpiScore.gain} />
    </div>
  );
}
```

### 4.4 JPI Tests

**File**: `ReDNACoreDemo/tests/test_hc_jpi.py` (~100 LOC)

Test cases:
- `test_jpi_calculates` - Can calculate JPI for user
- `test_jpi_awareness_score` - Awareness dimension scores correctly
- `test_jpi_intent_score` - Intent dimension uses test set
- `test_jpi_total_in_range` - Total score 0-100
- `test_jpi_api_endpoint` - API returns valid JSON

---

## Phase 5: Documentation & Verification (Est: 1 hour)

### 5.1 Architecture Documentation

**File**: `docs/HEAD_COACH_V2_ARCHITECTURE.md`

Write comprehensive architecture guide covering:
- Overview: Jarvis Standard vision
- 4-layer awareness model
- Intent classification schema
- Delegation routing logic
- CReDNA integration
- Reflection & learning foundation
- JPI calculation methodology
- Future roadmap (Pillars 4-5)

### 5.2 Run Test Suite

```bash
cd ReDNACoreDemo
pytest tests/test_hc_*.py -v --cov=core/head_coach
```

**Target**: >90% code coverage, all tests pass

### 5.3 Calculate Baseline vs Target JPI

```bash
curl http://127.0.0.1:8000/hc/jpi?user_id=TEST | python3 -m json.tool
```

**Expected**:
```json
{
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

### 5.4 Generate Sprint Completion Report

**File**: `docs/JARVIS_SPRINT_COMPLETION_REPORT.md`

Summary including:
- What was built (file list, LOC)
- Test results (coverage, pass/fail)
- JPI score achieved
- Performance benchmarks
- Known issues / future work
- Demo instructions

---

## Execution Checklist

Before starting:
- ✅ Blueprint reviewed (`HEAD_COACH_JARVIS_SPRINT_BLUEPRINT.md`)
- ✅ Dependencies met (CReDNA foundation complete)
- ✅ Test data prepared (100 diverse messages for intent classification)
- ✅ Development environment ready

During execution:
- ✅ Follow phase order strictly (1→2→3→4→5)
- ✅ Run unit tests after each phase
- ✅ Commit after each phase completion
- ✅ Log any deviations or issues

After completion:
- ✅ All unit tests pass (>90% coverage)
- ✅ Integration tests pass
- ✅ JPI ≥45 achieved
- ✅ Workshop UI functional
- ✅ Documentation complete
- ✅ Completion report generated

---

## Success Criteria

**Primary**:
- ✅ JPI Score: 45/100 (+25 from baseline 20)
- ✅ Intent Classification Accuracy: >85% on test set
- ✅ Delegation Routing Accuracy: >90% correct coach
- ✅ End-to-End Latency: <500ms for `/hc/v2/interact`

**Secondary**:
- ✅ Code Coverage: >90% for head_coach module
- ✅ Policy Trace Completeness: 100% (all decisions logged)
- ✅ Zero Breaking Changes: Legacy `/hc/say` still works
- ✅ Workshop Gauge Displays: Shows JPI score correctly

---

## Risk Mitigation

- If awareness snapshot too slow → Cache aggressively, lazy load memory layer
- If intent classifier accuracy low → Log failures for review, adjust rules
- If delegation routing wrong → Policy YAML is human-editable
- If CReDNA breaks → Feature flag allows rollback
- If tests fail → Skip optional tests, document issues

---

## Overnight Execution Instructions

Claude, please:

1. **Read the blueprint** (`HEAD_COACH_JARVIS_SPRINT_BLUEPRINT.md`) for full context
2. **Execute phases 1-5 sequentially** as specified above
3. **Run tests after each phase** to verify correctness
4. **Generate completion report** with JPI calculation and summary
5. **Commit all changes** with descriptive messages

**Estimated time**: 6-8 hours

**Expected outcome**: Head Coach v2 - Aware, Intelligent, Personalized, with JPI score of 45/100

Begin execution now.
