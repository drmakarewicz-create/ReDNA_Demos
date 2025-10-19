# Head Coach Awareness Snapshot Example

**User**: TEST
**Timestamp**: 2025-10-08
**System**: Jarvis Sprint v2.0

---

## Full Awareness Snapshot

```json
{
  "user_core_state": {
    "user_id": "TEST",
    "active_coach": "head_coach",
    "last_message_time": "2025-10-08T16:30:00Z",
    "current_mode": "exploration",
    "emotional_tone": "negative",
    "emotion_confidence": 0.77,
    "curiosity_hotspots": [
      "PaDNA.HairDNA.Color",
      "PaDNA.HairDNA.Length",
      "PaDNA.EyeDNA.Color"
    ]
  },
  "goal_task_layer": {
    "active_goals": [],
    "pending_tasks": [],
    "plan_states": [],
    "recent_intent_distribution": {}
  },
  "context_layer": {
    "local_time": "2025-10-08T16:30:00Z",
    "day_of_week": "Tuesday",
    "timezone": "UTC",
    "availability_flag": "active",
    "recent_external_interactions": []
  },
  "memory_layer": {
    "traits_summary": {
      "high_rr_domains": [],
      "low_rr_domains": ["PaDNA", "BioDNA"],
      "overall_rr": 27.2
    },
    "hc_history_summary": {
      "successful_patterns": [],
      "failed_patterns": [],
      "total_interactions": 0
    },
    "meta_feedback_stats": {
      "avg_satisfaction": 0.0,
      "total_feedback_count": 0
    },
    "ontology_context": {
      "high_rr_concepts": [],
      "low_rr_concepts": [],
      "related_concepts": [],
      "coverage_score": 0.0
    }
  },
  "ttl_hints": {
    "core": "live",
    "goal_task": "live",
    "context": "live",
    "memory": "live"
  },
  "policy": {
    "awareness_version": "v1",
    "schema": "hc_awareness.schema.json@v1",
    "build_ms": 182.29,
    "redacted_fields": ["raw_messages"]
  },
  "summary": {
    "active_goal_count": 0,
    "pending_tasks": 0,
    "top_curiosity": [
      "PaDNA.HairDNA.Color",
      "PaDNA.HairDNA.Length",
      "PaDNA.EyeDNA.Color"
    ],
    "emotional_state": "Concerned or uncertain (low confidence)"
  }
}
```

---

## Awareness Context String (for LLM)

```markdown
# User Context

**Current Mode**: head_coach
**Emotional Tone**: negative (confidence: 77%)

**Curiosity Hotspots** (areas of high uncertainty):
- PaDNA.HairDNA.Color
- PaDNA.HairDNA.Length
- PaDNA.EyeDNA.Color

**Overall Understanding**: 27.2/100 RR
**Areas to Explore**: PaDNA, BioDNA
```

---

## How It Works

### 1. Core State (Always Fresh)
```yaml
Active Coach: head_coach
Emotional Tone: negative (77% confidence)
  Detection: Keyword-based analysis of recent messages
  Keywords found: "wrong", "not", "can't" → negative tone

Curiosity Hotspots:
  - PaDNA.HairDNA.Color (RR: 5.0, curiosity: 75)
  - PaDNA.HairDNA.Length (RR: 10.0, curiosity: 70)
  - PaDNA.EyeDNA.Color (RR: 15.0, curiosity: 68)

Source: Curiosity engine + ontology adapter
Refresh: Every request (no cache)
```

### 2. Goal/Task Layer (5-minute TTL)
```yaml
Active Goals: 0
  Source: goal_states.json (future feature)

Pending Tasks: 0
  Source: task_runner.json (future feature)

Recent Intent Distribution: {}
  Source: intents_log.jsonl (future feature)

Status: Empty (new user)
Cache: 5-minute TTL
```

### 3. Context Layer (1-hour TTL)
```yaml
Time: 2025-10-08T16:30:00Z
Day: Tuesday
Timezone: UTC (default - future: user-specific)
Availability: active (inferred from recent activity)

Cache: 1-hour TTL
```

### 4. Memory Layer (24-hour TTL)
```yaml
Trait Summary:
  Overall RR: 27.2/100 (low - early user)
  High RR Domains: [] (none yet)
  Low RR Domains: [PaDNA, BioDNA]

  Calculation:
    - 35 traits in resolved.json
    - Average RR: sum(rr) / count = 952 / 35 = 27.2

Ontology Context:
  High RR Concepts: [] (no traits >70 RR)
  Low RR Concepts: [] (no ontology matches for TEST user)
  Related Concepts: [] (no cross-link traversal results)
  Coverage: 0.0% (35 / 2000 containers = 1.75%)

HC History:
  Total Interactions: 0 (new user)
  Successful Patterns: []
  Failed Patterns: []

Feedback Stats:
  Avg Satisfaction: 0.0
  Total Feedback: 0

Cache: 24-hour TTL
```

---

## Performance Metrics

```yaml
Build Time: 182.29ms
  Breakdown:
    - Core State Build: ~5ms
    - Curiosity Hotspots: ~150ms (dominates)
    - Goal/Task Layer: ~10ms
    - Context Layer: ~5ms
    - Memory Layer: ~10ms
    - Ontology Context: ~2ms (cached in adapter)

Cache Status: All layers fresh ("live")
Schema Version: v1
Redacted Fields: [raw_messages]
```

---

## Decision Impact

### Intent Classification
```yaml
Input: "I need career advice"
Intent Result:
  Primary: career_guidance
  Confidence: 0.40 (LOW)
  Ambiguity: 0.60 (HIGH)

Awareness Impact:
  - Emotional tone: negative → Boost supportive mode
  - Recent intents: {} → No domain boost
  - Overall RR: 27.2 → User is new, needs guidance

Decision: RETAIN (HC handles)
Reason: Low confidence + high ambiguity → clarify first
```

### CReDNA Personality Selection
```yaml
Awareness Inputs:
  - emotional_tone: "negative" (0.77 confidence)
  - high_curiosity_count: 3
  - overall_rr: 27.2

Mode Selection Logic:
  IF emotional_tone in [frustrated, negative]:
    mode = "supportive"  ✅ SELECTED
  ELIF high_curiosity_count > 10:
    mode = "delegation_mode"
  ELIF overall_rr >= 70:
    mode = "analytical"
  ELSE:
    mode = "default"

Selected Mode: "supportive"
  tone: warm
  empathy: high
  directness: balanced
  proactiveness: high
  authority_level: gentle
```

### Delegation Routing
```yaml
Intent: career_guidance (0.40 confidence)
Domain: career
Target Coach: career_coach

Policy Check:
  - Delegation threshold: 0.6
  - Confidence: 0.40
  - Result: BELOW THRESHOLD

Escalation Check:
  - Low confidence threshold: 0.4
  - Confidence: 0.40
  - Result: AT THRESHOLD → ESCALATE

Final Decision: RETAIN (HC handles)
Routing Action: retain
Target Coach: head_coach
Requires Handoff: false
Clarification Needed: true
```

---

## Example Interaction Flow

### User Message
```
"I need career advice"
```

### Step 1: Awareness Snapshot
```
Build time: 182ms
Emotional tone: negative (77%)
Curiosity hotspots: [PaDNA.HairDNA.Color, PaDNA.HairDNA.Length, PaDNA.EyeDNA.Color]
Overall RR: 27.2
```

### Step 2: Intent Classification
```
Primary intent: career_guidance
Confidence: 0.40 (LOW)
Category: request
Domain: career
Urgency: medium
```

### Step 3: Delegation Routing
```
Action: retain
Target: head_coach
Reason: Low confidence - retain for clarification
Requires handoff: false
```

### Step 4: CReDNA Personality
```
Mode: supportive (due to negative emotion)
Tone: warm
Empathy: high
Directness: balanced
```

### Step 5: HC Response (Mock Mode)
```
⚠️ I can't generate a live response because no LLM API key is configured.

To enable AI responses:
1. Get an API key from OpenAI (https://platform.openai.com/api-keys) or Anthropic (https://console.anthropic.com)
2. Set it as an environment variable...
```

### Step 6: Metadata Logging
```json
{
  "timestamp": "2025-10-08T16:30:05Z",
  "message_preview": "I need career advice",
  "intent": {
    "primary_intent": "career_guidance",
    "confidence": 0.40
  },
  "routing": {
    "action": "retain",
    "target_coach": "head_coach"
  },
  "response_preview": "⚠️ I can't generate a live response because no LLM API key is configured...",
  "awareness": {
    "emotional_tone": "negative",
    "curiosity_hotspots": ["PaDNA.HairDNA.Color", "PaDNA.HairDNA.Length", "PaDNA.EyeDNA.Color"],
    "overall_rr": 27.2
  },
  "performance_ms": 147.79
}
```

---

## Comparison: Before vs After Jarvis Sprint

### Before (JPI ~20)
```yaml
Input: "I need career advice"

Processing:
  1. Load conversation history
  2. Build static system prompt
  3. Call LLM
  4. Return response

Awareness: NONE
Intent Understanding: NONE
Routing Decision: NONE
Personality: STATIC ("encouraging, supportive")
Performance: ~50ms (simple passthrough)

Response Quality: Generic, no context
```

### After (JPI ~45)
```yaml
Input: "I need career advice"

Processing:
  1. Build 4-layer awareness snapshot (182ms)
     - Detect emotional tone: negative (77%)
     - Identify curiosity hotspots: [PaDNA.HairDNA.Color, ...]
     - Load trait summary: 27.2 RR
     - Check ontology context

  2. Classify intent (5ms)
     - Primary: career_guidance
     - Confidence: 0.40 (LOW)
     - Ambiguity: 0.60 (HIGH)

  3. Route with policy (5ms)
     - Target: career_coach
     - Decision: RETAIN (low confidence)
     - Clarification needed: true

  4. Select CReDNA personality (2ms)
     - Mode: supportive (due to negative emotion)
     - Tone: warm, empathy: high

  5. Build context-aware prompt (10ms)
     - Include awareness context
     - Apply supportive personality
     - Add curiosity hotspots

  6. Generate response with LLM (varies)

Total: ~200ms + LLM time

Response Quality: Contextual, aware, personalized
```

---

## Key Insights

### User Profile Analysis
```
User: TEST
Status: New user (27.2 RR, 35 traits)
Focus Area: Physical appearance (PaDNA)
Emotional State: Negative/uncertain
Needs: Supportive guidance, clarification
```

### System Behavior
```
Conservative Routing: Retains low-confidence intents
Adaptive Personality: Switches to supportive for negative emotions
Performance: <200ms awareness build (acceptable)
Ontology Integration: Minimal (user has few traits)
```

### Opportunities
```
1. Populate more traits → Enable ontology traversal
2. Build conversation history → Improve intent confidence
3. Track feedback → Tune delegation thresholds
4. Add goals/tasks → Enable proactive suggestions
```

---

**Snapshot Generated**: 2025-10-08T16:30:00Z
**Build Time**: 182.29ms
**Schema Version**: v1
**Jarvis Sprint**: v2.0
