# Phase 6: Why-Card Service Specification

**Version**: 1.0
**Status**: Draft for Review
**Author**: Claude (Conceptual Lead)
**Date**: 2025-10-17

---

## 1. Purpose & Philosophy Alignment

**Philosophy Requirement** (Section 2.6):
> "Every change in belief or trait must be explainable. The Core and Coaches generate 'Why-Cards'—short, natural-language explanations of what changed and why."

**Current Gap**: Promotions generate structured logs but no human-readable narratives.

**Phase 6 Solution**: Why-Card Service provides:
- Natural-language explanation for every trait belief
- Evidence tracing from belief back to source
- Confidence reasoning and uncertainty acknowledgment
- User-friendly rendering in Northstar UI

---

## 2. Data Model

### 2.1 WhyCard Schema

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class Evidence(BaseModel):
    """A piece of evidence supporting this belief."""
    source: str  # "chat", "photo", "onboarding", "inference"
    text: str  # Raw evidence text or description
    timestamp: datetime
    contribution_score: float  # 0.0-1.0, how much this evidence contributed
    event_id: Optional[str] = None

class ConfidenceExplanation(BaseModel):
    """Explains why confidence is at this level."""
    point_estimate: float  # 0.0-1.0
    interval_95: tuple[float, float]  # Confidence interval
    factors_increasing: List[str]  # "explicit mention", "corroborating evidence"
    factors_decreasing: List[str]  # "ambiguous wording", "contradicts prior belief"
    uncertainty_sources: List[str]  # "sarcasm possible", "time-dependent"

class WhyCard(BaseModel):
    """Complete explanation for a trait belief."""

    # Identity
    trait_id: str
    value: str | bool | int | float | None
    user_id: str

    # Core Narrative
    summary: str = Field(
        ...,
        description="2-3 sentence human-readable explanation",
        examples=[
            "I'm quite confident (80%) you're a morning person because you explicitly mentioned waking before sunrise. This suggests you have a morning chronotype—people who naturally feel most energetic early in the day."
        ]
    )

    # Supporting Evidence
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="All evidence supporting this belief, ordered by contribution"
    )

    # Confidence Reasoning
    confidence: ConfidenceExplanation

    # Inference Chain (for derived beliefs)
    inference_method: Optional[Literal["direct", "holistic", "correlation", "population_prior"]] = "direct"
    inferred_from: Optional[List[str]] = Field(
        default=None,
        description="Trait IDs this was inferred from (for holistic reasoning)"
    )

    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int = 1  # Increments when belief changes
    generated_by: Literal["ucnrr", "core_holistic", "northstar", "manual"] = "ucnrr"

    # Quality Indicators
    needs_verification: bool = False  # True if confidence < 60%
    curiosity_score: float = 0.0  # How much we want to know more (0.0-1.0)
    next_question: Optional[str] = None  # Suggested follow-up question

class WhyCardHistory(BaseModel):
    """Historical record of how belief evolved."""
    trait_id: str
    user_id: str
    versions: List[WhyCard]  # Ordered by version
```

---

## 3. API Design

### 3.1 Core Endpoints

#### `POST /why-cards/generate`

**Purpose**: Generate a Why-Card for a trait belief

**Request**:
```json
{
  "user_id": "user123",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "value": "morning",
  "confidence": 0.80,
  "evidence": [
    {
      "source": "chat",
      "text": "I am a morning person, up before sunrise.",
      "timestamp": "2025-10-17T08:23:45Z",
      "contribution_score": 0.9,
      "event_id": "text_1760749571378"
    }
  ],
  "context": {
    "existing_beliefs": ["BehaviorDNA.Exercise.Outdoor: true"],
    "population_prior": 0.35,
    "user_history_length": 12
  }
}
```

**Response**:
```json
{
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "value": "morning",
  "user_id": "user123",
  "summary": "I'm quite confident (80%) you're a morning person because you explicitly mentioned waking before sunrise. This suggests you have a morning chronotype—people who naturally feel most energetic early in the day.",
  "evidence": [...],
  "confidence": {
    "point_estimate": 0.80,
    "interval_95": [0.68, 0.89],
    "factors_increasing": [
      "Explicit self-identification as 'morning person'",
      "Specific time reference ('before sunrise')",
      "Consistent with outdoor exercise preference"
    ],
    "factors_decreasing": [
      "Single data point (would be more confident with multiple mentions)",
      "Possible context-dependence (vacation vs. work schedule)"
    ],
    "uncertainty_sources": [
      "Don't know if this is aspirational or actual behavior",
      "Sleep schedule can vary by life circumstances"
    ]
  },
  "inference_method": "direct",
  "needs_verification": false,
  "curiosity_score": 0.15,
  "next_question": "What time do you typically wake up on weekdays?",
  "created_at": "2025-10-17T08:24:12Z",
  "updated_at": "2025-10-17T08:24:12Z",
  "version": 1,
  "generated_by": "ucnrr"
}
```

---

#### `GET /why-cards/{user_id}/{trait_id}`

**Purpose**: Retrieve current Why-Card for a trait

**Response**: Same as generation response above

---

#### `GET /why-cards/{user_id}/all`

**Purpose**: Get all Why-Cards for a user

**Query Params**:
- `confidence_min`: Filter by minimum confidence (default: 0.0)
- `needs_verification`: Filter by verification status (default: false)
- `limit`: Max results (default: 50)

**Response**:
```json
{
  "user_id": "user123",
  "why_cards": [
    { /* WhyCard 1 */ },
    { /* WhyCard 2 */ }
  ],
  "count": 24,
  "stats": {
    "avg_confidence": 0.76,
    "needs_verification_count": 3,
    "direct_inferences": 18,
    "holistic_inferences": 6
  }
}
```

---

#### `GET /why-cards/{user_id}/{trait_id}/history`

**Purpose**: See how belief evolved over time

**Response**:
```json
{
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "user_id": "user123",
  "versions": [
    {
      "version": 1,
      "value": "morning",
      "confidence": 0.60,
      "summary": "Initial inference based on 'early riser' mention",
      "created_at": "2025-10-15T10:23:00Z"
    },
    {
      "version": 2,
      "value": "morning",
      "confidence": 0.80,
      "summary": "Confidence increased after explicit 'morning person' statement",
      "created_at": "2025-10-17T08:24:12Z",
      "changes": "Added corroborating evidence; raised confidence from 60% to 80%"
    }
  ]
}
```

---

### 3.2 Integration Endpoints

#### `POST /why-cards/batch-generate`

**Purpose**: Generate Why-Cards for multiple traits in one call (efficiency)

**Request**:
```json
{
  "user_id": "user123",
  "traits": [
    {
      "trait_id": "BehaviorDNA.Sleep.Chronotype",
      "value": "morning",
      "confidence": 0.80,
      "evidence": [...]
    },
    {
      "trait_id": "BasicDNA.Age",
      "value": "30s",
      "confidence": 0.65,
      "evidence": [...]
    }
  ],
  "context": { /* shared context */ }
}
```

**Response**: Array of WhyCard objects

---

#### `POST /why-cards/update-from-correction`

**Purpose**: User corrects a belief; Why-Card explains what changed

**Request**:
```json
{
  "user_id": "user123",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "old_value": "morning",
  "new_value": "evening",
  "correction_source": "user_explicit",
  "correction_text": "Actually, I stay up late most nights",
  "timestamp": "2025-10-18T20:15:00Z"
}
```

**Response**: New WhyCard with updated summary explaining the correction

---

## 4. LLM Prompt Templates

### 4.1 Direct Extraction Why-Card

```python
DIRECT_WHY_CARD_PROMPT = """You are explaining why ReDNA believes something about a user.

USER PROFILE CONTEXT:
- User ID: {user_id}
- Existing beliefs: {existing_beliefs_summary}

NEW BELIEF:
- Trait: {trait_id}
- Value: {value}
- Confidence: {confidence_pct}%

EVIDENCE:
{evidence_list}

POPULATION CONTEXT:
- {population_pct}% of users have this trait value
- Typical confidence for this trait: {typical_confidence}%

TASK:
Generate a 2-3 sentence explanation that:
1. States the belief clearly and warmly
2. Points to specific evidence that supports it
3. Explains the confidence level (why this % and not higher/lower)
4. Acknowledges uncertainty if confidence < 90%
5. Suggests what would increase confidence if needed

TONE: Warm, humble, curious, non-judgmental
STYLE: Conversational, avoid jargon
LENGTH: 50-100 words

Example format:
"I'm [certainty level] you're [trait]. This is because [specific evidence]. [Confidence reasoning]. [Uncertainty acknowledgment if needed]."

WHY-CARD:"""

# Certainty levels:
# 90-100%: "very confident"
# 75-89%: "quite confident"
# 60-74%: "moderately confident"
# 40-59%: "tentatively thinking"
# <40%: "curious whether"
```

---

### 4.2 Holistic Inference Why-Card

```python
HOLISTIC_WHY_CARD_PROMPT = """You are explaining an inference ReDNA made by connecting multiple traits.

USER PROFILE:
{existing_beliefs_summary}

NEW INFERENCE:
- Trait: {trait_id}
- Value: {value}
- Confidence: {confidence_pct}%
- Inferred from: {source_traits}

REASONING:
{inference_reasoning}

TASK:
Generate a 2-4 sentence explanation that:
1. States the inference
2. Explains which other traits led to this conclusion
3. Describes the logical connection
4. Acknowledges this is an educated guess, not directly stated
5. Invites correction if wrong

TONE: Warm, humble, transparent about reasoning process
STYLE: "I noticed X and Y, which made me think Z..."

WHY-CARD:"""
```

---

### 4.3 Confidence Explanation

```python
CONFIDENCE_EXPLANATION_PROMPT = """Analyze why confidence is at this level for a trait belief.

BELIEF:
- Trait: {trait_id}
- Value: {value}
- Confidence: {confidence_pct}%

EVIDENCE:
{evidence_list}

CONTEXT:
- Evidence count: {evidence_count}
- Evidence sources: {evidence_sources}
- Ambiguity detected: {ambiguity_flags}
- Contradictions: {contradiction_count}
- Population prior: {population_prior}

TASK:
List 2-4 factors that INCREASE confidence.
List 1-3 factors that DECREASE confidence.
List 1-2 sources of uncertainty.

Format as structured lists, brief phrases.

FACTORS INCREASING CONFIDENCE:
-

FACTORS DECREASING CONFIDENCE:
-

UNCERTAINTY SOURCES:
-"""
```

---

## 5. Storage Strategy

### 5.1 File-Based (MVP)

```
data/users/{user_id}/why_cards/
  ├── BehaviorDNA.Sleep.Chronotype.json
  ├── BasicDNA.Age.json
  └── ... (one file per trait)

data/users/{user_id}/why_card_history/
  ├── BehaviorDNA.Sleep.Chronotype.jsonl  (append-only log)
  └── ...
```

### 5.2 Schema Versioning

```json
{
  "schema_version": "1.0",
  "why_card": { /* WhyCard object */ }
}
```

**Migration Path**: When schema updates, provide converter function

---

### 5.3 Caching Strategy

- **In-Memory Cache**: Last 100 Why-Cards per user (LRU eviction)
- **TTL**: 1 hour (Why-Cards should refresh when beliefs update)
- **Invalidation**: On trait value change or new evidence

---

## 6. UI Integration (Northstar)

### 6.1 Trait Detail View

```
┌─────────────────────────────────────────────────┐
│  BehaviorDNA.Sleep.Chronotype: Morning         │
├─────────────────────────────────────────────────┤
│  ✨ Why I Believe This                          │
│                                                  │
│  I'm quite confident (80%) you're a morning     │
│  person because you explicitly mentioned waking │
│  before sunrise. This suggests you have a       │
│  morning chronotype—people who naturally feel   │
│  most energetic early in the day.               │
│                                                  │
│  📊 Confidence: 80% [████████░░] (68%-89%)      │
│                                                  │
│  📝 Based on:                                    │
│    • "I am a morning person, up before sunrise" │
│      (Oct 17, 8:23 AM - Chat)                  │
│                                                  │
│  ✅ What increases my confidence:               │
│    • Explicit self-identification               │
│    • Specific time reference                    │
│                                                  │
│  ⚠️ Remaining uncertainty:                       │
│    • Single data point                          │
│    • Context-dependence possible                │
│                                                  │
│  🤔 Next question to ask:                        │
│    "What time do you typically wake up?"        │
│                                                  │
│  [View History] [This is wrong ✗]              │
└─────────────────────────────────────────────────┘
```

---

### 6.2 Snapshot Overview

```
┌─────────────────────────────────────────────────┐
│  Your Trait Snapshot                            │
├─────────────────────────────────────────────────┤
│                                                  │
│  Chronotype: Morning ✨                         │
│    "I'm quite confident (80%) because you       │
│     mentioned waking before sunrise..."         │
│    [Why?]                                       │
│                                                  │
│  Age: 30s ⚠️ Needs Verification                 │
│    "I'm tentatively thinking you're in your 30s │
│     based on career stage mentions..."          │
│    [Tell me more]                               │
│                                                  │
│  Exercise: Outdoor Running ✅                    │
│    "I'm very confident (95%) because you shared │
│     multiple photos of trail runs..."           │
│    [Why?]                                       │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

### 6.3 Correction Flow

```
User clicks: "This is wrong ✗"

┌─────────────────────────────────────────────────┐
│  Help me understand                              │
├─────────────────────────────────────────────────┤
│  I thought you were a morning person because:    │
│  • You said "I am a morning person"             │
│  • You mentioned "up before sunrise"            │
│                                                  │
│  What should I know instead?                     │
│                                                  │
│  [  I'm actually a night owl                    │
│                                                  │
│  [Submit Correction]                            │
└─────────────────────────────────────────────────┘

After correction:

┌─────────────────────────────────────────────────┐
│  ✅ Updated                                      │
├─────────────────────────────────────────────────┤
│  Thanks! I've updated your chronotype to        │
│  "evening" based on your correction.            │
│                                                  │
│  I previously thought you were a morning person │
│  because of the "before sunrise" mention—I now  │
│  realize that might have been sarcasm or a      │
│  specific situation.                            │
│                                                  │
│  New confidence: 85% (higher because you told   │
│  me directly!)                                  │
└─────────────────────────────────────────────────┘
```

---

## 7. Integration Points

### 7.1 Core Promotion Loop

**Current** (ReDNACoreDemo/core/api.py:5900):
```python
value = normalize_value(trait_id, source_text or "")

stack_log(
    service="core",
    level="INFO",
    event="promotion_value",
    msg=f"value for {trait_id}",
    meta={"value": value},
)
```

**Phase 6 Enhancement**:
```python
value = normalize_value(trait_id, source_text or "")

# Generate Why-Card
why_card_response = generate_why_card(
    user_id=user_id,
    trait_id=trait_id,
    value=value,
    confidence=score_float / 1000.0,
    evidence=[{
        "source": "ucnrr_rescore",
        "text": source_text[:200],
        "timestamp": datetime.now(timezone.utc),
        "contribution_score": 1.0,
        "event_id": event_id
    }],
    context={
        "existing_beliefs": get_user_trait_summary(user_id),
        "population_prior": get_population_prior(trait_id, value)
    }
)

# Store Why-Card
save_why_card(user_id, trait_id, why_card_response)

# Add to trait record
trait_record = {
    "trait_id": trait_id,
    "ucn": score_float,
    "value": value,
    "why_card_id": why_card_response.get("id"),  # Reference
    "source": "ucnrr_rescore",
    "event_id": event_id
}
```

---

### 7.2 UCNRR Rescore Response

**Current Response**:
```json
{
  "rr_by_trait": {"BehaviorDNA.Sleep.Chronotype": 800.0},
  "curiosity_by_trait": {"BehaviorDNA.Sleep.Chronotype": 0.15}
}
```

**Phase 6 Enhancement**:
```json
{
  "rr_by_trait": {"BehaviorDNA.Sleep.Chronotype": 800.0},
  "curiosity_by_trait": {"BehaviorDNA.Sleep.Chronotype": 0.15},
  "why_card_hints": {
    "BehaviorDNA.Sleep.Chronotype": {
      "evidence_summary": "Explicit mention: 'morning person, up before sunrise'",
      "confidence_factors": {
        "increasing": ["direct_self_identification", "specific_time_reference"],
        "decreasing": ["single_data_point"]
      }
    }
  }
}
```

---

## 8. Test Data Examples

### 8.1 Example 1: High-Confidence Direct Extraction

**Input**:
```json
{
  "user_id": "test_user_1",
  "trait_id": "PaDNA.HairDNA.Color.Natural",
  "value": "brown",
  "confidence": 0.95,
  "evidence": [
    {
      "source": "photo",
      "text": "Uploaded selfie showing brown hair",
      "timestamp": "2025-10-15T14:30:00Z",
      "contribution_score": 0.7
    },
    {
      "source": "chat",
      "text": "My hair is naturally brown",
      "timestamp": "2025-10-16T10:22:00Z",
      "contribution_score": 0.3
    }
  ]
}
```

**Expected WhyCard**:
```json
{
  "summary": "I'm very confident (95%) your natural hair color is brown because you both told me directly and I can see it in your photos. This is one of the most certain traits I have about you!",
  "confidence": {
    "point_estimate": 0.95,
    "interval_95": [0.91, 0.97],
    "factors_increasing": [
      "Visual confirmation from photo",
      "Explicit verbal statement",
      "Multiple evidence sources"
    ],
    "factors_decreasing": [],
    "uncertainty_sources": [
      "Hair color can change naturally with age"
    ]
  },
  "needs_verification": false,
  "curiosity_score": 0.05,
  "next_question": null
}
```

---

### 8.2 Example 2: Moderate-Confidence with Ambiguity

**Input**:
```json
{
  "user_id": "test_user_2",
  "trait_id": "BasicDNA.Age",
  "value": "30s",
  "confidence": 0.65,
  "evidence": [
    {
      "source": "chat",
      "text": "I'm in my early 30s",
      "timestamp": "2025-10-17T09:15:00Z",
      "contribution_score": 1.0
    }
  ]
}
```

**Expected WhyCard**:
```json
{
  "summary": "I'm moderately confident (65%) you're in your 30s because you mentioned being in your 'early 30s'. While this is pretty clear, I'd be more certain if I knew your exact age, since people sometimes round or use age ranges casually.",
  "confidence": {
    "point_estimate": 0.65,
    "interval_95": [0.55, 0.75],
    "factors_increasing": [
      "Direct age mention"
    ],
    "factors_decreasing": [
      "Vague phrasing ('early 30s' could be 30-34)",
      "Single data point",
      "Age can be sensitive topic (possible deflection)"
    ],
    "uncertainty_sources": [
      "Don't know exact birth year",
      "Context unclear (dating profile vs. casual chat)"
    ]
  },
  "needs_verification": true,
  "curiosity_score": 0.35,
  "next_question": "Would you mind sharing your birth year, or at least which half of the decade you're in?"
}
```

---

### 8.3 Example 3: Holistic Inference

**Input**:
```json
{
  "user_id": "test_user_3",
  "trait_id": "BehaviorDNA.Social.Style",
  "value": "family-oriented",
  "confidence": 0.60,
  "evidence": [],
  "inference_method": "holistic",
  "inferred_from": [
    "BasicDNA.RelationshipStatus: married",
    "BasicDNA.Age: 30s",
    "PreferenceDNA.Leisure.Type: home-activities"
  ]
}
```

**Expected WhyCard**:
```json
{
  "summary": "I'm tentatively thinking you're family-oriented (60% confidence) based on connecting a few dots: you're married, in your 30s, and mentioned enjoying activities at home. This is an educated guess rather than something you directly told me—so definitely let me know if I'm off base!",
  "confidence": {
    "point_estimate": 0.60,
    "interval_95": [0.45, 0.73],
    "factors_increasing": [
      "Multiple correlated traits point this direction",
      "Common pattern in population data"
    ],
    "factors_decreasing": [
      "No direct statement about family orientation",
      "Home activities could mean many things",
      "Inference based on stereotypical patterns"
    ],
    "uncertainty_sources": [
      "Making assumptions from limited data",
      "Could be introverted without being family-focused"
    ]
  },
  "inference_method": "holistic",
  "inferred_from": [
    "BasicDNA.RelationshipStatus",
    "BasicDNA.Age",
    "PreferenceDNA.Leisure.Type"
  ],
  "needs_verification": true,
  "curiosity_score": 0.40,
  "next_question": "How do you typically like to spend your free time—with family, friends, or solo?"
}
```

---

## 9. Performance Considerations

### 9.1 Generation Latency

**Target**: <500ms per Why-Card (95th percentile)

**Optimization Strategies**:
1. **Batching**: Generate multiple Why-Cards in single LLM call
2. **Caching**: Cache Why-Cards for unchanged beliefs (1 hour TTL)
3. **Async**: Generate Why-Cards in background after promotion
4. **Fast Model**: Use phi3:mini for simple Why-Cards, llama3.1 for complex inferences

---

### 9.2 Cost Control

**Estimated Cost**: ~$0.001-0.003 per Why-Card (using Ollama: $0)

**Budget Constraints**:
- Max 100 Why-Card generations per user per day
- Use template-based fallback if LLM unavailable
- Cache aggressively to avoid re-generation

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
def test_why_card_generation_direct():
    """Test Why-Card for direct extraction."""
    result = generate_why_card(
        trait_id="PaDNA.HairDNA.Color.Natural",
        value="brown",
        confidence=0.95,
        evidence=[{
            "source": "photo",
            "text": "Brown hair visible",
            "contribution_score": 1.0
        }]
    )

    assert result.summary is not None
    assert len(result.summary.split()) >= 20  # At least 20 words
    assert "brown" in result.summary.lower()
    assert result.confidence.point_estimate == 0.95
    assert result.needs_verification == False

def test_why_card_low_confidence():
    """Low confidence should flag for verification."""
    result = generate_why_card(
        trait_id="BasicDNA.Age",
        value="40s",
        confidence=0.45,
        evidence=[...]
    )

    assert result.needs_verification == True
    assert result.curiosity_score > 0.5
    assert result.next_question is not None
```

---

### 10.2 Integration Tests

```python
def test_why_card_promotion_integration():
    """Test Why-Card generation during promotion."""
    # Ingest text that should trigger promotion
    response = client.post("/core/api/ingest_text", json={
        "user_id": "test_user",
        "text": "I am a morning person, up before sunrise.",
        "source": "test"
    })

    assert response.status_code == 200
    snapshot = response.json()["snapshot"]

    # Check Why-Card was generated
    chronotype_trait = next(
        t for t in snapshot["traits"]
        if t["trait_id"] == "BehaviorDNA.Sleep.Chronotype"
    )

    assert "why_card_id" in chronotype_trait

    # Fetch Why-Card
    why_card_response = client.get(
        f"/why-cards/test_user/BehaviorDNA.Sleep.Chronotype"
    )

    assert why_card_response.status_code == 200
    why_card = why_card_response.json()

    assert "morning" in why_card["summary"].lower()
    assert why_card["confidence"]["point_estimate"] >= 0.7
```

---

### 10.3 Quality Tests

```python
def test_why_card_tone():
    """Ensure Why-Cards have appropriate tone."""
    result = generate_why_card(...)

    summary = result.summary.lower()

    # Avoid overly certain language
    assert "definitely" not in summary
    assert "absolutely" not in summary

    # Use humble language
    assert any(word in summary for word in ["think", "believe", "suggest", "seems"])

    # Acknowledge uncertainty if <90% confidence
    if result.confidence.point_estimate < 0.9:
        assert any(word in summary for word in [
            "tentatively", "moderately", "quite", "fairly"
        ])
```

---

## 11. Rollout Plan

### Phase 6.1 (Week 1-2): MVP

- [ ] Implement WhyCard data model
- [ ] Create LLM prompt templates
- [ ] Build `/why-cards/generate` endpoint
- [ ] Integrate with Core promotion loop (stub version)
- [ ] Unit tests for generation logic

### Phase 6.2 (Week 3-4): Storage & Retrieval

- [ ] File-based storage implementation
- [ ] Caching layer
- [ ] History tracking
- [ ] GET endpoints for retrieval
- [ ] Integration tests

### Phase 6.3 (Week 5-6): UI Integration

- [ ] Northstar trait detail view with Why-Card
- [ ] Snapshot overview with explanations
- [ ] Correction flow with Why-Card update
- [ ] User acceptance testing

### Phase 6.4 (Week 7-8): Optimization

- [ ] Batch generation
- [ ] Performance tuning (target <500ms)
- [ ] Cost optimization
- [ ] Quality metrics dashboard

---

## 12. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Why-Card coverage | 100% of promoted traits | Audit snapshot.traits |
| Generation latency (p95) | <500ms | Timing logs |
| User engagement | 30%+ click "Why?" | UI analytics |
| Correction rate | <5% | User corrections / promotions |
| Explanation quality score | >4.0/5.0 | Manual review sample (N=50) |

---

## 13. Open Questions for Review

1. **Should Why-Cards be versioned in Git** (for reproducibility) or just in user data?
2. **LLM model selection**: Always phi3:mini, or adaptive based on complexity?
3. **Privacy**: Should Why-Cards be included in data exports? Anonymized?
4. **Multilingual**: Plan for i18n from start, or English-only MVP?
5. **Tone customization**: Should users control how "certain" vs. "humble" the Why-Cards sound?

---

## 14. Next Steps

**For Codex** (Implementation):
1. Review this spec for feasibility
2. Implement WhyCard Pydantic models in `ReDNACoreDemo/core/schemas.py`
3. Create `ReDNACoreDemo/core/why_cards/` module with:
   - `generator.py` (LLM prompt assembly + call)
   - `storage.py` (file-based storage)
   - `api.py` (FastAPI routes)

**For Claude** (Conceptual Lead):
1. Await Codex feedback on spec
2. Generate 10+ example Why-Cards for quality baseline
3. Begin Curiosity Queue spec (next deliverable)
4. Design alignment scoring methodology

---

**Status**: Ready for Review
**Next Spec**: Phase6_Curiosity_Spec.md (coming next)
