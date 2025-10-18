# Phase 6: Curiosity & Hypothesis Queue Specification

**Version**: 1.0
**Status**: Draft for Review
**Author**: Claude (Conceptual Lead)
**Date**: 2025-10-17

---

## 1. Purpose & Philosophy Alignment

**Philosophy Requirement** (Section 2.4):
> "When uncertain, ReDNA asks instead of assuming. It values exploration and information gain over false precision."

**Current Gap**: Curiosity scores are calculated but never used to trigger follow-up questions.

**Phase 6 Solution**: Curiosity & Hypothesis Queue transforms **uncertainty into action**:
- Low-confidence beliefs → Intelligent follow-up questions
- Contradictions → Gentle clarification requests
- Novel signals → Hypothesis exploration
- Borderline promotions → Strategic verification

---

## 2. Data Model

### 2.1 CuriosityItem Schema

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timedelta
from enum import Enum

class ReasonCode(str, Enum):
    """Why this curiosity item was created."""
    LOW_CONFIDENCE = "low_confidence"  # p ∈ [0.4, 0.6]
    SCHEMA_REPAIR_LOW_CONF = "schema_repair_low_conf"  # Repaired but uncertain
    VALUE_MISSING = "value_missing"  # require_value=True but value=None
    CONTRADICTION = "contradiction"  # Conflicts with another trait
    NOVEL_SIGNAL = "novel_signal"  # New evidence for unknown trait
    POLICY_BORDERLINE = "policy_borderline"  # Near threshold boundary

class QuestionStyle(str, Enum):
    """Tone for the suggested question."""
    GENTLE = "gentle"  # Warm, non-pushy
    DIRECT = "direct"  # Clear, efficient
    PLAYFUL = "playful"  # Lighthearted, curious

class CuriosityStatus(str, Enum):
    """Lifecycle state."""
    QUEUED = "queued"  # Waiting to be asked
    ASKED = "asked"  # Presented to user, awaiting answer
    ANSWERED = "answered"  # User provided answer
    DISMISSED = "dismissed"  # User declined to answer
    EXPIRED = "expired"  # TTL expired

class CuriosityInput(BaseModel):
    """Snapshot of triggering context."""
    rr_score: float  # Raw RR from UCNRR
    base_threshold: float  # Base RR threshold
    adjusted_threshold: Optional[float] = None  # Curiosity-adjusted threshold
    probability: float  # Probability of promotion (0-1)
    raw_text: Optional[str] = None  # Evidence text (first 200 chars)
    evidence_ids: List[str] = Field(default_factory=list)  # Event IDs
    ucn: float  # Original UCN from UCNRR
    curiosity_score: float  # Original curiosity score
    normalization_attempted: bool = False  # Was normalization tried?
    normalization_succeeded: bool = False  # Did normalization succeed?
    schema_repair_used: bool = False  # Was schema repair needed?
    conflicting_trait_ids: List[str] = Field(default_factory=list)  # For contradictions

class CuriosityItem(BaseModel):
    """A single curiosity queue entry."""

    # Identity
    id: str = Field(..., description="UUID v4")
    user_id: str
    trait_id: str

    # Lifecycle
    created_at: datetime
    expires_at: Optional[datetime] = None  # TTL (default: 30 days)
    status: CuriosityStatus = CuriosityStatus.QUEUED

    # Classification
    reason_code: ReasonCode
    inputs: CuriosityInput  # Full context snapshot

    # The Question
    suggested_question: str = Field(
        ...,
        description="1-2 short, natural lines for user",
        examples=["Quick check—are you generally a morning person or more evening?"]
    )
    question_style: QuestionStyle = QuestionStyle.GENTLE

    # Ranking & Prioritization
    expected_information_gain: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Scalar for ranking (0-1, higher = more valuable)"
    )

    # De-duplication
    cooldown_key: str = Field(
        ...,
        description="e.g., 'Chronotype/v1' - prevents re-asking same question",
        examples=["Chronotype/v1", "Age/v1"]
    )

    # Cross-Trait Context
    related_traits: List[str] = Field(
        default_factory=list,
        description="Other trait_ids that might inform this question"
    )

    # Response Tracking
    asked_at: Optional[datetime] = None
    answer_text: Optional[str] = None
    answered_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    dismiss_reason: Optional[str] = None

    # Links
    why_card_id: Optional[str] = None  # Link to current Why-Card
    follow_up_event_id: Optional[str] = None  # Event ID of answer ingestion

class CuriosityQueueSummary(BaseModel):
    """Summary stats for a user's queue."""
    user_id: str
    total_queued: int
    total_asked: int
    total_answered: int
    total_dismissed: int
    total_expired: int
    avg_information_gain: float
    top_items: List[CuriosityItem]  # Top N by IG
```

---

## 3. Enqueue Conditions

### 3.1 Trigger Rules

Create `CuriosityItem` when **ANY** of:

#### 1. **Low Confidence Band**
```python
# Policy probability p ∈ [0.4, 0.6] (ambiguous zone)
p = rr_score / 1000.0  # Convert RR to probability
if 0.4 <= p <= 0.6:
    reason_code = ReasonCode.LOW_CONFIDENCE
```

**Alternative**: RR within ±Δ of threshold
```python
delta = 50  # Configurable threshold margin
if abs(rr_score - base_threshold) <= delta:
    reason_code = ReasonCode.POLICY_BORDERLINE
```

---

#### 2. **Normalization Failed**
```python
if policy.get("require_value") and normalized_value is None:
    reason_code = ReasonCode.VALUE_MISSING
```

---

#### 3. **Schema Repair with Low Confidence**
```python
if schema_repair_used and ucn < 0.7:
    reason_code = ReasonCode.SCHEMA_REPAIR_LOW_CONF
```

---

#### 4. **Contradiction Detected**
```python
# Example: Current value conflicts with previous value
current_value = snapshot.get_trait_value(trait_id)
new_value = extracted_value

if current_value and current_value != new_value:
    reason_code = ReasonCode.CONTRADICTION
    conflicting_trait_ids = [trait_id]  # Can include related traits
```

---

#### 5. **Novel Signal**
```python
# Evidence hints at trait we've never seen for this user
if trait_id not in user_snapshot.traits and ucn > 0.5:
    reason_code = ReasonCode.NOVEL_SIGNAL
```

---

### 3.2 De-Duplication Rules

**Prevent duplicate questions** using cooldown logic:

```python
class CuriosityDeduplicator:
    def should_enqueue(
        self,
        user_id: str,
        trait_id: str,
        reason_code: ReasonCode,
        cooldown_key: str,
        cooldown_sec: int = 604800  # 7 days default
    ) -> bool:
        """Check if we should create a new curiosity item."""

        # 1. Check cooldown (user_id, trait_id, cooldown_key)
        last_asked = self.get_last_asked(user_id, trait_id, cooldown_key)
        if last_asked:
            time_since_ask = (datetime.now() - last_asked).total_seconds()
            if time_since_ask < cooldown_sec:
                return False  # Still in cooldown

        # 2. Check max open items per trait
        MAX_OPEN_PER_TRAIT = 2
        open_for_trait = self.count_open(user_id, trait_id)
        if open_for_trait >= MAX_OPEN_PER_TRAIT:
            return False

        # 3. Check max open items per user
        MAX_OPEN_PER_USER = 20
        open_for_user = self.count_open(user_id)
        if open_for_user >= MAX_OPEN_PER_USER:
            return False

        return True
```

**Cooldown Key Examples**:
- `"Chronotype/v1"` - Version allows asking again if question template changes
- `"Age/direct"` - Different approaches (direct vs. indirect)
- `"Hair/confirmation"` - Re-confirming after new contradictory evidence

---

## 4. Ranking & Information Gain

### 4.1 Expected Information Gain Calculation

```python
def calculate_information_gain(
    item: CuriosityItem,
    trait_impact_weights: Dict[str, float],
    tau_hours: float = 168  # 1 week decay
) -> float:
    """
    Calculate expected information gain for ranking.

    Formula: IG = uncertainty * impact * recency

    Returns: float ∈ [0, 1]
    """

    # 1. Uncertainty score (higher at p=0.5)
    p = item.inputs.probability
    uncertainty = 1 - abs(p - 0.5) * 2  # Maps [0,1] → [0,1], peaks at 0.5

    # 2. Impact weight (trait importance)
    impact_weight = trait_impact_weights.get(item.trait_id, 0.5)  # Default 0.5

    # 3. Recency weight (exponential decay)
    age_hours = (datetime.now() - item.created_at).total_seconds() / 3600
    recency_weight = math.exp(-age_hours / tau_hours)

    # 4. Reason code multiplier
    reason_multipliers = {
        ReasonCode.CONTRADICTION: 1.5,  # Conflicts are high priority
        ReasonCode.NOVEL_SIGNAL: 1.3,  # New discoveries valuable
        ReasonCode.POLICY_BORDERLINE: 1.2,  # Near-miss promotions
        ReasonCode.LOW_CONFIDENCE: 1.0,  # Baseline
        ReasonCode.VALUE_MISSING: 0.9,  # Slightly lower (might be intentional omission)
        ReasonCode.SCHEMA_REPAIR_LOW_CONF: 0.8,  # Lowest (already made best guess)
    }
    reason_mult = reason_multipliers.get(item.reason_code, 1.0)

    # 5. Combine
    ig = uncertainty * impact_weight * recency_weight * reason_mult

    # 6. Normalize to [0, 1]
    return min(1.0, max(0.0, ig))
```

---

### 4.2 Trait Impact Weights (Example)

```python
TRAIT_IMPACT_WEIGHTS = {
    # High Impact (foundational traits)
    "BasicDNA.Age": 0.9,
    "BasicDNA.Gender": 0.9,
    "BasicDNA.RelationshipStatus": 0.8,

    # Medium-High Impact (lifestyle traits)
    "BehaviorDNA.Sleep.Chronotype": 0.75,
    "BehaviorDNA.Exercise.Frequency": 0.7,
    "BehaviorDNA.Work.Location": 0.7,

    # Medium Impact (preferences)
    "PreferenceDNA.Social.GroupSize": 0.6,
    "PreferenceDNA.Food.Cuisine": 0.5,

    # Low Impact (optional details)
    "PreferenceDNA.Food.Pizza": 0.3,
    "PaDNA.EyeDNA.IrisColor": 0.4,

    # Default for unknown traits
    "_default": 0.5
}
```

---

## 5. API Design

### 5.1 Core Endpoints

#### `POST /core/api/curiosity/enqueue`

**Purpose**: Create a new curiosity item (called by ingestion pipeline)

**Request**:
```json
{
  "user_id": "user123",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "reason_code": "low_confidence",
  "inputs": {
    "rr_score": 480.0,
    "base_threshold": 780.0,
    "adjusted_threshold": 680.0,
    "probability": 0.48,
    "raw_text": "I might be a morning person but not always.",
    "evidence_ids": ["text_1760749571378"],
    "ucn": 0.6,
    "curiosity_score": 0.52,
    "normalization_attempted": true,
    "normalization_succeeded": true
  },
  "context": {
    "existing_beliefs": ["BehaviorDNA.Exercise.Outdoor: true"],
    "cooldown_sec": 604800
  }
}
```

**Response**:
```json
{
  "id": "curio_abc123def456",
  "user_id": "user123",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "status": "queued",
  "suggested_question": "Quick check—are you generally a morning person or more evening?",
  "expected_information_gain": 0.73,
  "created_at": "2025-10-17T14:30:00Z",
  "expires_at": "2025-11-16T14:30:00Z"
}
```

**Error Cases**:
- `409 Conflict`: De-duplication rules prevent enqueue (cooldown active)
- `429 Too Many Requests`: User has too many open items

---

#### `GET /core/api/curiosity`

**Purpose**: Retrieve curiosity items (for Northstar consumption)

**Query Params**:
- `user_id` (required)
- `status` (default: "queued")
- `limit` (default: 20)
- `min_information_gain` (default: 0.0)

**Response**:
```json
{
  "user_id": "user123",
  "items": [
    {
      "id": "curio_abc123",
      "trait_id": "BehaviorDNA.Sleep.Chronotype",
      "suggested_question": "Quick check—are you generally a morning person or more evening?",
      "expected_information_gain": 0.73,
      "reason_code": "low_confidence",
      "created_at": "2025-10-17T14:30:00Z",
      "related_traits": [],
      "why_card_id": "why_card_789"
    }
  ],
  "total": 1,
  "stats": {
    "queued": 1,
    "asked": 2,
    "answered": 5,
    "dismissed": 1
  }
}
```

**Ordering**: Items sorted by `expected_information_gain` DESC

---

#### `POST /core/api/curiosity/{id}/ack`

**Purpose**: Mark item as "asked" (Northstar consumed it)

**Request**:
```json
{
  "asked_at": "2025-10-17T15:00:00Z",
  "context": "head_coach_chat"
}
```

**Response**:
```json
{
  "id": "curio_abc123",
  "status": "asked",
  "asked_at": "2025-10-17T15:00:00Z"
}
```

---

#### `POST /core/api/curiosity/{id}/answer`

**Purpose**: User provided an answer; trigger re-evaluation

**Request**:
```json
{
  "answer_text": "I'm definitely morning",
  "answered_at": "2025-10-17T15:05:00Z"
}
```

**Response**:
```json
{
  "id": "curio_abc123",
  "status": "answered",
  "answer_text": "I'm definitely morning",
  "answered_at": "2025-10-17T15:05:00Z",
  "follow_up": {
    "reingest_triggered": true,
    "event_id": "text_1760850000123",
    "promotion_result": {
      "promoted": true,
      "new_rr": 850.0,
      "new_confidence": 0.85
    }
  }
}
```

**Side Effect**:
1. Ingest `answer_text` as new evidence (source: "curiosity_answer")
2. Trigger UCNRR rescore
3. Update Why-Card with new explanation
4. Log `curiosity_answer` event

---

#### `POST /core/api/curiosity/{id}/dismiss`

**Purpose**: User declined to answer

**Request**:
```json
{
  "dismiss_reason": "too_personal",
  "dismissed_at": "2025-10-17T15:01:00Z"
}
```

**Response**:
```json
{
  "id": "curio_abc123",
  "status": "dismissed",
  "dismiss_reason": "too_personal",
  "dismissed_at": "2025-10-17T15:01:00Z"
}
```

**Side Effect**: Log `curiosity_dismiss` event with reason

---

### 5.2 Debug & Admin Endpoints

#### `GET /core/api/debug/curiosity_dump`

**Purpose**: DevX visibility into queue state

**Query Params**:
- `user_id` (optional)
- `format` (json|csv, default: json)

**Response**: Full dump of all items

---

#### `POST /core/api/debug/curiosity_clear`

**Purpose**: Clear queue (for testing)

**Request**:
```json
{
  "user_id": "test_user",
  "status": "queued"  // Optional filter
}
```

**Response**:
```json
{
  "cleared": 5,
  "user_id": "test_user"
}
```

---

## 6. Question Generation

### 6.1 LLM-Based Generation (Primary)

**Prompt Template**:
```python
CURIOSITY_QUESTION_PROMPT = """You are helping ReDNA ask a user a clarifying question about themselves.

CONTEXT:
- User ID: {user_id}
- Trait: {trait_id}
- Current belief: {current_value} (confidence: {confidence_pct}%)
- Reason for asking: {reason_explanation}

EVIDENCE SO FAR:
{evidence_summary}

EXISTING PROFILE:
{user_profile_summary}

TASK:
Generate ONE short, natural question (1-2 sentences max) to help clarify this trait.

REQUIREMENTS:
- Tone: {question_style} ({style_guidance})
- Length: 10-20 words
- Format: Direct question, no preamble
- Avoid: "Can I ask...", "Would you mind...", "Just curious..."
- Start with action: "Are you...", "Do you...", "What's your..."

EXAMPLES:
- Gentle: "Are you generally a morning person or more evening?"
- Direct: "What time do you typically wake up on weekdays?"
- Playful: "Morning lark or night owl—which sounds more like you?"

QUESTION:"""

# Style guidance
STYLE_GUIDANCE = {
    QuestionStyle.GENTLE: "warm, non-pushy, optional feel",
    QuestionStyle.DIRECT: "clear, efficient, straightforward",
    QuestionStyle.PLAYFUL: "lighthearted, curious, friendly"
}
```

---

### 6.2 Fallback Templates (When LLM Unavailable)

```python
FALLBACK_TEMPLATES = {
    (ReasonCode.LOW_CONFIDENCE, "BehaviorDNA.Sleep.Chronotype"): {
        QuestionStyle.GENTLE: "Quick check—are you generally a morning person or more evening?",
        QuestionStyle.DIRECT: "Are you a morning person or a night owl?",
        QuestionStyle.PLAYFUL: "Morning lark or night owl—which fits you better?"
    },

    (ReasonCode.VALUE_MISSING, "BasicDNA.Age"): {
        QuestionStyle.GENTLE: "Would you mind sharing your age range?",
        QuestionStyle.DIRECT: "What's your age range?",
        QuestionStyle.PLAYFUL: "Care to share which decade you're rocking?"
    },

    (ReasonCode.CONTRADICTION, None): {  # Generic contradiction
        QuestionStyle.GENTLE: "I noticed two different signals about {trait_label}—which fits you best?",
        QuestionStyle.DIRECT: "You mentioned {old_value} and {new_value}—which is accurate?",
        QuestionStyle.PLAYFUL: "Plot twist: {old_value} or {new_value}? Help me out here!"
    },

    (ReasonCode.NOVEL_SIGNAL, None): {  # Generic novel
        QuestionStyle.GENTLE: "I'm curious—does {trait_label} = {value} sound right to you?",
        QuestionStyle.DIRECT: "Is {value} accurate for {trait_label}?",
        QuestionStyle.PLAYFUL: "Spotted something new—are you {value}?"
    },

    # Default fallback
    "_default": {
        QuestionStyle.GENTLE: "Could you tell me a bit more about {trait_label}?",
        QuestionStyle.DIRECT: "What's your {trait_label}?",
        QuestionStyle.PLAYFUL: "Tell me about your {trait_label}!"
    }
}

def get_fallback_question(
    reason_code: ReasonCode,
    trait_id: str,
    style: QuestionStyle,
    **template_vars
) -> str:
    """Get fallback question when LLM unavailable."""
    # Try specific template
    key = (reason_code, trait_id)
    if key in FALLBACK_TEMPLATES:
        template = FALLBACK_TEMPLATES[key][style]
    else:
        # Try generic for reason
        key = (reason_code, None)
        if key in FALLBACK_TEMPLATES:
            template = FALLBACK_TEMPLATES[key][style]
        else:
            # Use default
            template = FALLBACK_TEMPLATES["_default"][style]

    return template.format(**template_vars)
```

---

## 7. Integration Points

### 7.1 Core Ingestion Pipeline

**Location**: `ReDNACoreDemo/core/api.py` (promotion loop)

**Current Code** (simplified):
```python
# After UCNRR rescore
if score_float >= policy.get("rr_min"):
    promote(trait_id, value)
else:
    skip(trait_id)
```

**Phase 6 Enhancement**:
```python
# After UCNRR rescore
base_threshold = policy.get("rr_min", 0.0)
curiosity = rescore_result.get("curiosity_by_trait", {}).get(trait_id, 0.0)
adjusted_threshold = base_threshold * (1 - 0.15 * curiosity)

p = score_float / 1000.0  # Probability

if score_float >= adjusted_threshold:
    promote(trait_id, value)

# Check if curiosity item should be enqueued
elif should_enqueue_curiosity(user_id, trait_id, p, policy, value):
    enqueue_curiosity_item(
        user_id=user_id,
        trait_id=trait_id,
        reason_code=determine_reason_code(p, policy, value),
        inputs=CuriosityInput(
            rr_score=score_float,
            base_threshold=base_threshold,
            adjusted_threshold=adjusted_threshold,
            probability=p,
            raw_text=source_text[:200],
            evidence_ids=[event_id],
            ucn=score_float / 1000.0,
            curiosity_score=curiosity,
            normalization_attempted=True,
            normalization_succeeded=value is not None
        )
    )

    stack_log(
        service="core",
        level="INFO",
        event="curiosity_enqueue",
        msg=f"Enqueued curiosity for {trait_id}",
        meta={
            "user_id": user_id,
            "trait_id": trait_id,
            "reason_code": reason_code,
            "expected_ig": item.expected_information_gain
        }
    )
```

---

### 7.2 UCNRR Hints

**UCNRR Response Enhancement**:
```json
{
  "rr_by_trait": {"BehaviorDNA.Sleep.Chronotype": 480.0},
  "curiosity_by_trait": {"BehaviorDNA.Sleep.Chronotype": 0.52},
  "curiosity_hints": {
    "BehaviorDNA.Sleep.Chronotype": {
      "schema_repair_used": false,
      "normalization_confidence": "low",
      "suggested_reason_code": "low_confidence"
    }
  }
}
```

---

### 7.3 Northstar Integration

**Head Coach Queue Display**:
```python
@app.get("/northstar/curiosity/pending")
def get_pending_curiosity(user_id: str, limit: int = 3):
    """Get top curiosity items for user."""
    response = requests.get(
        f"{CORE_BASE}/core/api/curiosity",
        params={
            "user_id": user_id,
            "status": "queued",
            "limit": limit,
            "min_information_gain": 0.3  # Only show high-value items
        }
    )

    items = response.json()["items"]

    # Format for Northstar UI
    return {
        "pending_questions": [
            {
                "id": item["id"],
                "question": item["suggested_question"],
                "priority": item["expected_information_gain"],
                "trait": item["trait_id"],
                "why_card_link": item.get("why_card_id")
            }
            for item in items
        ]
    }
```

**Ask & Answer Flow**:
```python
# 1. User sees question in chat
coach_message = f"🤔 {curiosity_item['suggested_question']}"

# 2. User responds
user_response = "I'm definitely morning"

# 3. Acknowledge ask
requests.post(
    f"{CORE_BASE}/core/api/curiosity/{item_id}/ack",
    json={"asked_at": datetime.now().isoformat()}
)

# 4. Submit answer
answer_response = requests.post(
    f"{CORE_BASE}/core/api/curiosity/{item_id}/answer",
    json={
        "answer_text": user_response,
        "answered_at": datetime.now().isoformat()
    }
)

# 5. Get updated belief
if answer_response.json()["follow_up"]["promoted"]:
    new_confidence = answer_response.json()["follow_up"]["new_confidence"]
    coach_message = f"✅ Got it! Updated to {new_confidence*100:.0f}% confident."
```

---

## 8. Safety & UX Guardrails

### 8.1 Rate Limiting

```python
class CuriosityRateLimiter:
    """Prevent overwhelming users with questions."""

    MAX_ASKS_PER_DAY = 3
    MIN_HOURS_BETWEEN_ASKS_SAME_TRAIT = 48

    def can_ask(self, user_id: str, trait_id: str) -> Tuple[bool, str]:
        """Check if we can ask this user about this trait."""

        # 1. Check daily limit
        asks_today = self.count_asks_today(user_id)
        if asks_today >= self.MAX_ASKS_PER_DAY:
            return False, f"Daily limit reached ({self.MAX_ASKS_PER_DAY} asks/day)"

        # 2. Check trait cooldown
        last_ask_for_trait = self.get_last_ask_time(user_id, trait_id)
        if last_ask_for_trait:
            hours_since = (datetime.now() - last_ask_for_trait).total_seconds() / 3600
            if hours_since < self.MIN_HOURS_BETWEEN_ASKS_SAME_TRAIT:
                return False, f"Asked about this trait {hours_since:.1f}h ago (min: {self.MIN_HOURS_BETWEEN_ASKS_SAME_TRAIT}h)"

        return True, "OK"
```

---

### 8.2 Opt-Out & Deferral

**Environment Flag**:
```bash
ENABLE_CURIOSITY_LOOP=true  # Global toggle
```

**Per-User Preference**:
```json
// data/users/{user_id}/preferences.json
{
  "curiosity_enabled": true,
  "curiosity_frequency": "moderate",  // "low" | "moderate" | "high"
  "curiosity_defer_until": null  // ISO timestamp or null
}
```

**Defer Flow**:
```python
@app.post("/northstar/curiosity/defer")
def defer_curiosity(user_id: str, hours: int = 24):
    """User clicks 'Ask me later'."""
    defer_until = datetime.now() + timedelta(hours=hours)

    update_user_preferences(
        user_id,
        {"curiosity_defer_until": defer_until.isoformat()}
    )

    return {
        "deferred": True,
        "defer_until": defer_until,
        "message": f"No problem! I'll hold off on questions for {hours} hours."
    }
```

---

### 8.3 Privacy & Sensitivity

**Sensitive Trait Detection**:
```python
SENSITIVE_TRAITS = {
    "BasicDNA.MentalHealth.*",
    "BasicDNA.MedicalHistory.*",
    "BasicDNA.FinancialStatus",
    "BasicDNA.SexualOrientation"
}

def is_sensitive(trait_id: str) -> bool:
    """Check if trait requires explicit consent."""
    for pattern in SENSITIVE_TRAITS:
        if fnmatch.fnmatch(trait_id, pattern):
            return True
    return False

# Only enqueue if user has opted in
if is_sensitive(trait_id) and not user_consented_to_sensitive_questions(user_id):
    return False  # Skip enqueue
```

---

## 9. Storage & Operations

### 9.1 File-Based Storage (MVP)

**Structure**:
```
data/users/{user_id}/curiosity/
  ├── queue.jsonl          # Append-only log of all items
  ├── index.json           # In-memory index for fast queries
  └── stats.json           # Summary stats
```

**queue.jsonl** (append-only):
```jsonl
{"event":"enqueue","item":{...},"timestamp":"2025-10-17T14:30:00Z"}
{"event":"ack","id":"curio_abc123","timestamp":"2025-10-17T15:00:00Z"}
{"event":"answer","id":"curio_abc123","answer_text":"...","timestamp":"2025-10-17T15:05:00Z"}
```

**index.json** (rebuilt on load):
```json
{
  "queued": ["curio_abc123", "curio_def456"],
  "asked": ["curio_ghi789"],
  "answered": ["curio_jkl012"],
  "by_trait": {
    "BehaviorDNA.Sleep.Chronotype": ["curio_abc123"]
  }
}
```

---

### 9.2 TTL Cleanup Job

```python
@app.on_event("startup")
async def start_cleanup_job():
    """Background task to expire stale items."""

    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # Run every hour

            expired_count = expire_stale_curiosity_items()
            if expired_count > 0:
                stack_log(
                    service="core",
                    level="INFO",
                    event="curiosity_cleanup",
                    msg=f"Expired {expired_count} stale curiosity items"
                )

    task = asyncio.create_task(cleanup_loop())
    return task

def expire_stale_curiosity_items() -> int:
    """Mark items past TTL as expired."""
    now = datetime.now()
    count = 0

    for user_dir in Path("data/users").iterdir():
        queue_path = user_dir / "curiosity" / "queue.jsonl"
        if not queue_path.exists():
            continue

        # Load all items
        items = load_curiosity_items(user_dir.name)

        for item in items:
            if item.status == CuriosityStatus.QUEUED and item.expires_at:
                if now > item.expires_at:
                    update_curiosity_status(item.id, CuriosityStatus.EXPIRED)
                    count += 1

    return count
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

**File**: `tests/test_curiosity_queue.py`

```python
def test_enqueue_low_confidence():
    """Enqueue when p ∈ [0.4, 0.6]."""
    item = enqueue_curiosity_item(
        user_id="test_user",
        trait_id="BehaviorDNA.Sleep.Chronotype",
        reason_code=ReasonCode.LOW_CONFIDENCE,
        inputs=CuriosityInput(
            rr_score=480.0,
            base_threshold=780.0,
            probability=0.48,
            ucn=0.6,
            curiosity_score=0.52
        )
    )

    assert item.status == CuriosityStatus.QUEUED
    assert item.reason_code == ReasonCode.LOW_CONFIDENCE
    assert 0.0 <= item.expected_information_gain <= 1.0

def test_ranking_by_information_gain():
    """Items sorted by IG descending."""
    # Create 3 items with different IGs
    item1 = create_item(ig=0.8)
    item2 = create_item(ig=0.5)
    item3 = create_item(ig=0.9)

    items = get_curiosity_items("test_user", status="queued")

    assert items[0].id == item3.id  # Highest IG
    assert items[1].id == item1.id
    assert items[2].id == item2.id  # Lowest IG

def test_deduplication_cooldown():
    """Cooldown prevents duplicate questions."""
    # First enqueue succeeds
    item1 = enqueue_curiosity_item(
        user_id="test_user",
        trait_id="BehaviorDNA.Sleep.Chronotype",
        cooldown_key="Chronotype/v1"
    )
    assert item1 is not None

    # Second enqueue within cooldown fails
    item2 = enqueue_curiosity_item(
        user_id="test_user",
        trait_id="BehaviorDNA.Sleep.Chronotype",
        cooldown_key="Chronotype/v1"
    )
    assert item2 is None  # Blocked by cooldown

def test_max_open_per_user():
    """Respect max open items per user."""
    MAX_OPEN_PER_USER = 20

    # Create 20 items
    for i in range(MAX_OPEN_PER_USER):
        item = enqueue_curiosity_item(
            user_id="test_user",
            trait_id=f"Trait_{i}"
        )
        assert item is not None

    # 21st item fails
    item = enqueue_curiosity_item(
        user_id="test_user",
        trait_id="Trait_21"
    )
    assert item is None

def test_state_transitions():
    """Test queued → asked → answered flow."""
    # Create item
    item = enqueue_curiosity_item(...)
    assert item.status == CuriosityStatus.QUEUED

    # Acknowledge
    ack_curiosity_item(item.id)
    item = get_curiosity_item(item.id)
    assert item.status == CuriosityStatus.ASKED
    assert item.asked_at is not None

    # Answer
    answer_curiosity_item(item.id, "I'm morning")
    item = get_curiosity_item(item.id)
    assert item.status == CuriosityStatus.ANSWERED
    assert item.answer_text == "I'm morning"
    assert item.answered_at is not None
```

---

### 10.2 Integration Tests

**File**: `tests/integration/test_curiosity_northstar.py`

```python
def test_full_curiosity_flow():
    """Test complete flow: ingest → enqueue → ask → answer → re-evaluate."""

    # 1. Ingest ambiguous text (should trigger curiosity)
    response = client.post("/core/api/ingest_text", json={
        "user_id": "test_user",
        "text": "I might be a morning person but not always.",
        "source": "test"
    })
    assert response.status_code == 200

    # 2. Check curiosity was enqueued
    curiosity_response = client.get("/core/api/curiosity", params={
        "user_id": "test_user",
        "status": "queued"
    })
    items = curiosity_response.json()["items"]
    assert len(items) > 0

    chronotype_item = next(
        (item for item in items if "Chronotype" in item["trait_id"]),
        None
    )
    assert chronotype_item is not None
    item_id = chronotype_item["id"]

    # 3. Northstar acknowledges (ask)
    ack_response = client.post(f"/core/api/curiosity/{item_id}/ack", json={
        "asked_at": datetime.now().isoformat()
    })
    assert ack_response.status_code == 200

    # 4. User answers
    answer_response = client.post(f"/core/api/curiosity/{item_id}/answer", json={
        "answer_text": "I'm definitely morning",
        "answered_at": datetime.now().isoformat()
    })
    assert answer_response.status_code == 200

    # 5. Check re-evaluation happened
    follow_up = answer_response.json()["follow_up"]
    assert follow_up["reingest_triggered"] == True
    assert follow_up["promotion_result"]["promoted"] == True
    assert follow_up["promotion_result"]["new_confidence"] > 0.8

    # 6. Verify updated snapshot
    snapshot_response = client.get(f"/ui/unabridged", params={
        "user_id": "test_user"
    })
    snapshot = snapshot_response.json()

    chronotype_trait = next(
        t for t in snapshot["traits"]
        if t["trait_id"] == "BehaviorDNA.Sleep.Chronotype"
    )
    assert chronotype_trait["value"] == "morning"
    assert chronotype_trait["ucn"] > 800.0
```

---

## 11. Verification Snippet

**For Human to Run**:

```bash
#!/bin/bash
# Phase 6 Curiosity Queue Verification

set -e

CORE_BASE="http://127.0.0.1:8004"
USER_ID="dbg_c"

echo "=== Phase 6 Curiosity Queue Verification ==="
echo

# 1. Trigger low-confidence case
echo "1. Ingesting ambiguous chronotype text..."
curl -s -X POST $CORE_BASE/core/api/ingest_text \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"'$USER_ID'","text":"I might be a morning person but not always.","source":"bench"}' \
  | jq -r '.success'

echo

# 2. Check queued curiosity
echo "2. Checking queued curiosity items..."
QUEUE_RESPONSE=$(curl -s "$CORE_BASE/core/api/curiosity?user_id=$USER_ID&status=queued&limit=5")
echo "$QUEUE_RESPONSE" | jq '.'

ITEM_COUNT=$(echo "$QUEUE_RESPONSE" | jq '.items | length')
echo "   Found $ITEM_COUNT queued items"

if [ "$ITEM_COUNT" -eq 0 ]; then
  echo "   ❌ FAIL: Expected at least 1 curiosity item"
  exit 1
fi

ITEM_ID=$(echo "$QUEUE_RESPONSE" | jq -r '.items[0].id')
QUESTION=$(echo "$QUEUE_RESPONSE" | jq -r '.items[0].suggested_question')
echo "   Top item: $QUESTION"
echo

# 3. Acknowledge ask
echo "3. Acknowledging ask (marking as 'asked')..."
curl -s -X POST "$CORE_BASE/core/api/curiosity/$ITEM_ID/ack" \
  -H 'Content-Type: application/json' \
  -d '{"asked_at":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}' \
  | jq -r '.status'

echo

# 4. Submit answer
echo "4. Submitting answer..."
ANSWER_RESPONSE=$(curl -s -X POST "$CORE_BASE/core/api/curiosity/$ITEM_ID/answer" \
  -H 'Content-Type: application/json' \
  -d '{"answer_text":"I am definitely morning","answered_at":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}')

echo "$ANSWER_RESPONSE" | jq '.'

PROMOTED=$(echo "$ANSWER_RESPONSE" | jq -r '.follow_up.promotion_result.promoted')
NEW_CONF=$(echo "$ANSWER_RESPONSE" | jq -r '.follow_up.promotion_result.new_confidence')

echo "   Promoted: $PROMOTED"
echo "   New confidence: $NEW_CONF"

if [ "$PROMOTED" != "true" ]; then
  echo "   ❌ FAIL: Expected promotion after definitive answer"
  exit 1
fi

echo

# 5. Verify final state
echo "5. Verifying final belief state..."
SNAPSHOT=$(curl -s "$CORE_BASE/ui/unabridged?user_id=$USER_ID")

CHRONOTYPE_RR=$(echo "$SNAPSHOT" | jq -r '.traits[] | select(.trait_id == "BehaviorDNA.Sleep.Chronotype") | .rr')

echo "   Final RR: $CHRONOTYPE_RR"

if (( $(echo "$CHRONOTYPE_RR > 800" | bc -l) )); then
  echo "   ✅ PASS: Chronotype promoted with RR > 800"
else
  echo "   ❌ FAIL: Expected RR > 800, got $CHRONOTYPE_RR"
  exit 1
fi

echo
echo "=== All Verification Tests Passed ✅ ==="
```

---

## 12. Dependencies & Interfaces

### 12.1 Why-Card Integration

**Link Curiosity to Why-Cards**:
```python
# When generating Why-Card, check for pending curiosity
curiosity_items = get_curiosity_items(user_id, trait_id, status="queued")

if curiosity_items:
    why_card.next_question = curiosity_items[0].suggested_question
    why_card.curiosity_score = curiosity_items[0].expected_information_gain
```

**Why-Card References Curiosity**:
```json
{
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "summary": "I'm tentatively thinking you're a morning person (48%)...",
  "needs_verification": true,
  "curiosity_score": 0.73,
  "next_question": "Quick check—are you generally a morning person or more evening?",
  "curiosity_item_id": "curio_abc123"  // Link
}
```

---

### 12.2 LLM Layer Router

**Placeholder for Shared LLM Layer** (Phase 6.2):
```python
# ReDNACoreDemo/core/llm/router.py
class LLMRouter:
    """Unified LLM gateway for all AI calls."""

    def generate_curiosity_question(
        self,
        trait_id: str,
        reason_code: ReasonCode,
        context: Dict,
        style: QuestionStyle = QuestionStyle.GENTLE
    ) -> str:
        """Generate curiosity question via LLM or fallback."""

        try:
            # Primary: LLM generation
            prompt = render_template(CURIOSITY_QUESTION_PROMPT, context)
            response = self.call_llm(
                prompt,
                model="phi3:mini",  # Fast model for questions
                timeout=5
            )
            return response.strip()

        except Exception as e:
            # Fallback: Template
            stack_log(
                service="core",
                level="WARNING",
                event="llm_fallback",
                msg="LLM unavailable for curiosity question; using template",
                meta={"error": str(e)}
            )
            return get_fallback_question(reason_code, trait_id, style, **context)
```

---

## 13. Rollout Plan

### Phase 6.1 (Week 1-2): Core Infrastructure

- [ ] Implement `CuriosityItem` Pydantic model
- [ ] Create enqueue logic with de-duplication
- [ ] Build information gain calculation
- [ ] File-based storage (queue.jsonl)
- [ ] Unit tests for enqueue/rank/dedup

### Phase 6.2 (Week 3-4): API & Integration

- [ ] POST `/core/api/curiosity/enqueue`
- [ ] GET `/core/api/curiosity`
- [ ] POST `/curiosity/{id}/ack`, `/answer`, `/dismiss`
- [ ] Integrate with Core ingestion pipeline
- [ ] Question generation (templates for MVP)

### Phase 6.3 (Week 5-6): Northstar & UX

- [ ] Northstar curiosity queue display
- [ ] Ask/answer flow in Head Coach
- [ ] Rate limiting and cooldown logic
- [ ] User deferral ("Ask me later")
- [ ] Integration tests

### Phase 6.4 (Week 7-8): LLM & Optimization

- [ ] LLM-based question generation
- [ ] TTL cleanup job
- [ ] Performance tuning
- [ ] DevX debug endpoints
- [ ] Documentation

---

## 14. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Curiosity enqueue rate | 10-20% of ingestions | Log analysis |
| Answer rate (answered / asked) | >60% | Curiosity item stats |
| Promotion after answer | >70% | Follow-up promotion tracking |
| Avg time to answer | <24 hours | asked_at → answered_at delta |
| User satisfaction | >4.0/5.0 | Post-answer survey (optional) |
| False enqueues (user frustrated) | <5% | Dismiss rate with reason="not_relevant" |

---

## 15. Open Questions for Review

1. **Should curiosity items expire after TTL or stay indefinitely**? (Spec says 30 days default)
2. **LLM model for questions**: Always phi3:mini or upgrade to llama for complex cases?
3. **Multi-turn conversations**: Should answering one question trigger follow-up questions in same session?
4. **Privacy**: Should curiosity items be included in data exports?
5. **Personalization**: Should question style adapt to user's communication preferences?

---

## 16. Next Steps

**For Codex** (Implementation):
1. Review spec for feasibility
2. Implement `CuriosityItem` in `ReDNACoreDemo/core/schemas.py`
3. Create `ReDNACoreDemo/core/curiosity/` module:
   - `enqueue.py` (enqueue logic + de-dup)
   - `ranking.py` (IG calculation)
   - `storage.py` (file-based JSONL)
   - `api.py` (FastAPI routes)
   - `generator.py` (question generation)

**For Claude** (Conceptual Lead):
1. Await Codex feedback
2. Generate 20+ example curiosity items for quality baseline
3. Begin DevX AI Diagnostics spec (next deliverable)
4. Design Guardian LLM spec

---

**Status**: Ready for Review
**Next Spec**: Phase6_DevX_Diagnostics_Spec.md (coming next)
