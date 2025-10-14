# Coach Delegation Framework Design

**Status**: Design Phase (Phase B Priority)
**Last Updated**: October 6, 2025

---

## Overview

The Coach Delegation Framework enables the Head Coach to orchestrate specialized coaches to satisfy curiosity through their natural domains, rather than forcing awkward data collection in inappropriate contexts.

### Core Principle

**The Head Coach should DELEGATE, not DEMAND.**

When the system has high curiosity for `PaDNA.NoseDNA.TipShapeDNA`, the Head Coach should:
- ❌ **NOT** ask: "By the way, can you describe your nose tip shape?"
- ✅ **DO** delegate: "Photo Coach, please work with user on facial features"

The Photo Coach naturally explores nose traits as part of photo analysis, making data collection feel organic.

---

## Architecture

### 1. Coach Registry

Maps DNA namespaces/containers to specialized coaches who naturally work in those domains.

```python
COACH_REGISTRY = {
    "PaDNA": {
        "primary_coach": "Photo Coach",
        "capabilities": [
            "HairDNA", "FaceDNA", "FacialDNA", "EyeDNA",
            "NoseDNA", "SkinDNA", "BodyDNA"
        ],
        "delegation_context": "photo analysis and visual trait extraction"
    },
    "PsyDNA": {
        "primary_coach": "Relationship Coach",  # Psychology expert
        "capabilities": [
            "PersonalityDNA", "MotivationDNA", "BeliefDNA",
            "ValuesDNA", "FearDNA"
        ],
        "delegation_context": "psychological profiling and self-reflection"
    },
    "EmDNA": {
        "primary_coach": "Relationship Coach",
        "capabilities": [
            "BaselineDNA", "TriggerDNA", "RegulationDNA",
            "ExpressionDNA", "AttachmentDNA"
        ],
        "delegation_context": "emotional patterns and relationship dynamics"
    },
    "ReDNA": {
        "primary_coach": "Relationship Coach",
        "capabilities": ["*"],  # All relationship traits
        "delegation_context": "relationship patterns and dynamics"
    },
    "CogDNA": {
        "primary_coach": "Head Coach",  # HC handles cognitive
        "capabilities": [
            "ThinkingStyleDNA", "LearningDNA", "MemoryDNA",
            "AttentionDNA"
        ],
        "delegation_context": "direct conversation and reflection"
    }
    # ... more mappings
}
```

### 2. Delegation Protocol

**Head Coach Workflow:**

```python
# 1. Identify high-curiosity items
high_curiosity = curiosity_engine.generate_curiosity_agenda(user_id, top_n=10)

# 2. Group by responsible coach
by_coach = {}
for item in high_curiosity:
    namespace = item.path.split(".")[0]
    coach = COACH_REGISTRY.get(namespace, {}).get("primary_coach", "Head Coach")
    by_coach.setdefault(coach, []).append(item)

# 3. Delegate to appropriate coaches
if "Photo Coach" in by_coach and photo_coach_available():
    delegate_to_coach(
        coach="Photo Coach",
        context={
            "delegation_reason": "high_curiosity_exploration",
            "curiosity_targets": by_coach["Photo Coach"],
            "user_id": user_id,
            "priority": "explore_facial_features"
        }
    )

# 4. Head Coach continues with items it can handle naturally
head_coach_items = by_coach.get("Head Coach", [])
# ... integrate into conversation
```

---

## Delegation Scenarios

### Scenario 1: Physical Appearance (PaDNA)

**System State:**
```python
high_curiosity = [
    {"path": "PaDNA.NoseDNA.TipShapeDNA", "curiosity": 85, "type": "missing"},
    {"path": "PaDNA.EyeDNA.SettingDNA", "curiosity": 78, "type": "missing"},
    {"path": "PaDNA.HairDNA.TextureDNA", "curiosity": 65, "type": "trait"}
]
```

**Head Coach Decision:**
```
1. Check: Is Photo Coach available? YES
2. Delegate: All 3 items to Photo Coach
3. Context: "User needs PaDNA refinement - focus on facial features and hair"
4. Head Coach continues: Focus on conversation quality, let Photo Coach handle data collection
```

**Photo Coach Execution:**
```
Photo Coach: "Hey! I'd love to help refine your physical appearance profile.
              Would you be up for sharing a recent photo? I can analyze facial
              features, eye characteristics, and hair details."

(Natural, contextual, non-awkward)
```

---

### Scenario 2: Relationship Dynamics (ReDNA)

**System State:**
```python
high_curiosity = [
    {"path": "ReDNA.AttachmentStyleDNA", "curiosity": 92, "type": "missing"},
    {"path": "ReDNA.ConflictResolutionDNA", "curiosity": 88, "type": "container"}
]
```

**Head Coach Decision:**
```
1. Check: Is Relationship Coach available? YES
2. Delegate: Both items to Relationship Coach
3. Context: "User needs relationship profiling - explore attachment and conflict patterns"
4. Head Coach: "I think the Relationship Coach could help explore some patterns. Want to chat with them?"
```

**Relationship Coach Execution:**
```
RC: "Hi! I'm here to help you understand your relationship patterns.
     Let's start with how you typically handle conflict in close relationships..."

(Domain expert, natural conversation flow)
```

---

### Scenario 3: Mixed Domains

**System State:**
```python
high_curiosity = [
    {"path": "PaDNA.HairDNA.ColorDNA", "curiosity": 82, "type": "trait"},
    {"path": "CogDNA.LearningDNA.StyleDNA", "curiosity": 75, "type": "missing"},
    {"path": "PsyDNA.PersonalityDNA.OpennessLevelDNA", "curiosity": 68, "type": "trait"}
]
```

**Head Coach Decision:**
```
1. Group by coach:
   - Photo Coach: PaDNA.HairDNA.ColorDNA
   - Head Coach: CogDNA.LearningDNA.StyleDNA (can handle conversationally)
   - Relationship Coach: PsyDNA.PersonalityDNA.OpennessLevelDNA

2. Prioritize: CogDNA is conversational, handle directly
3. Delegate: PaDNA to Photo Coach (if available), PsyDNA to RC (if available)
4. Execution: Head Coach explores learning style naturally, delegates others
```

---

## Delegation API

### Core Functions

#### `can_delegate_to(coach_name: str, user_id: str) -> bool`
```python
def can_delegate_to(coach_name: str, user_id: str) -> bool:
    """
    Check if a coach is available for delegation.

    Criteria:
    - Coach is enabled in system config
    - User has access to coach (RR thresholds, subscriptions)
    - Coach is not currently busy with user
    """
    pass
```

#### `delegate_to_coach(coach: str, context: Dict[str, Any]) -> DelegationResult`
```python
@dataclass
class DelegationResult:
    success: bool
    coach: str
    delegation_id: str  # Track this delegation
    message: str  # Message to show user
    curiosity_targets: List[str]  # What coach should explore

def delegate_to_coach(coach: str, context: Dict[str, Any]) -> DelegationResult:
    """
    Delegate curiosity exploration to specialized coach.

    Context should include:
    - user_id
    - curiosity_targets (list of high-curiosity paths)
    - delegation_reason
    - priority (low/medium/high)
    - suggested_approach (optional guidance for coach)
    """
    pass
```

#### `check_delegation_status(delegation_id: str) -> DelegationStatus`
```python
@dataclass
class DelegationStatus:
    delegation_id: str
    coach: str
    status: str  # "pending", "active", "completed", "failed"
    traits_collected: List[str]
    curiosity_satisfied: float  # 0.0-1.0, how much curiosity was reduced
    timestamp: str

def check_delegation_status(delegation_id: str) -> DelegationStatus:
    """
    Check status of a delegation.

    Head Coach can use this to:
    - Know when to follow up
    - Understand what was collected
    - Decide if further delegation needed
    """
    pass
```

---

## Return Protocol

When a specialized coach completes a delegation:

### 1. Coach Reports Back

```python
delegation_result = {
    "delegation_id": "abc123",
    "coach": "Photo Coach",
    "status": "completed",
    "traits_collected": [
        "PaDNA.NoseDNA.TipShapeDNA",
        "PaDNA.EyeDNA.SettingDNA",
        "PaDNA.HairDNA.TextureDNA"
    ],
    "curiosity_before": {
        "PaDNA.NoseDNA.TipShapeDNA": 85,
        "PaDNA.EyeDNA.SettingDNA": 78,
        "PaDNA.HairDNA.TextureDNA": 65
    },
    "curiosity_after": {
        "PaDNA.NoseDNA.TipShapeDNA": 12,  # RR went from 0 → 88
        "PaDNA.EyeDNA.SettingDNA": 18,
        "PaDNA.HairDNA.TextureDNA": 8
    },
    "curiosity_satisfied": 0.92,  # 92% of curiosity addressed
    "notes": "User shared photo, analyzed 12 facial traits",
    "timestamp": "2025-10-06T14:30:00Z"
}
```

### 2. Head Coach Updates Context

```python
# Head Coach receives notification
def on_delegation_complete(result: Dict[str, Any]):
    """
    Handle delegation completion.

    Actions:
    1. Update curiosity agenda (traits now have lower curiosity)
    2. Thank user for engagement (if appropriate)
    3. Decide next steps (more delegation? different domain?)
    """

    # Refresh curiosity agenda
    new_agenda = curiosity_engine.generate_curiosity_agenda(user_id)

    # Check if more work needed
    if result["curiosity_satisfied"] < 0.7:
        # Partial completion - might need follow-up
        plan_follow_up(result)
    else:
        # Success - move to next priority area
        focus_on_next_domain(new_agenda)
```

---

## Guardrail Integration

Delegation respects user tolerance:

```python
def should_delegate(user_tolerance: float, coach: str) -> bool:
    """
    Decide if delegation is appropriate based on user tolerance.

    Rules:
    - tolerance >= 0.8: Delegate aggressively, any coach
    - tolerance >= 0.5: Delegate when contextually appropriate
    - tolerance < 0.5: Only delegate if user explicitly requests coach
    """

    if user_tolerance >= 0.8:
        return True  # User wants aggressive data collection

    if user_tolerance >= 0.5:
        # Check if delegation is contextually appropriate
        return is_contextually_appropriate(coach, conversation_context)

    # Low tolerance - wait for explicit invitation
    return user_requested_coach(coach)
```

---

## Implementation Phases

### Phase 1: Foundation (1-2 days)
**Deliverables:**
- Coach registry (JSON/YAML config)
- `can_delegate_to()` function
- Basic delegation API endpoints
- Unit tests for delegation logic

**Files:**
- `core/coach_registry.yaml` - Coach capabilities mapping
- `core/coach_delegation.py` - Delegation logic
- `core/api_coach_delegation.py` - API endpoints

---

### Phase 2: Integration (2-3 days)
**Deliverables:**
- Head Coach uses delegation in conversation flow
- Specialized coaches accept delegation context
- Return protocol implemented
- Dev Mode delegation viewer

**Files:**
- `core/hc_llm_agent.py` - Enhanced with delegation
- `core/photo_coach.py` - Accept delegation context
- `core/relationship_coach.py` - Accept delegation context
- `web/src/components/delegation-viewer.tsx` - Dev Mode UI

---

### Phase 3: Optimization (1-2 days)
**Deliverables:**
- Delegation prioritization (which coach first?)
- Parallel delegations (multiple coaches at once?)
- Delegation analytics (success rates, curiosity reduction)
- User feedback integration

**Files:**
- `core/delegation_optimizer.py` - Smart delegation routing
- `core/delegation_analytics.py` - Track effectiveness

---

## Success Metrics

### Quantitative
- **Curiosity Reduction Rate**: % of curiosity satisfied per delegation
- **User Satisfaction**: Feedback scores on delegated sessions
- **Natural Context Rate**: % of delegations that felt contextually appropriate
- **Coach Utilization**: How often each coach is delegated to

### Qualitative
- **Awkwardness Avoided**: No forced data collection questions
- **Domain Expertise**: Specialized coaches handle their domains
- **Conversation Flow**: Smooth handoffs, no jarring transitions
- **User Comfort**: Users feel conversations are natural, not system-driven

---

## Example: Full Delegation Flow

**Starting State:**
```
User: "I've been thinking about my relationships lately"
System Curiosity: High for ReDNA.AttachmentStyleDNA (curiosity: 92)
User Tolerance: 0.65 (balanced mode)
```

**Head Coach Internal Logic:**
```python
# 1. Detect opportunity
user_mentioned_relationships = True
high_curiosity_redna = True
relationship_coach_available = True

# 2. Check guardrails
if user_tolerance >= 0.5 and user_mentioned_relationships:
    # Contextually appropriate to delegate

    # 3. Prepare delegation
    delegation = {
        "coach": "Relationship Coach",
        "user_id": user_id,
        "curiosity_targets": ["ReDNA.AttachmentStyleDNA"],
        "context": "User initiated conversation about relationships",
        "priority": "high"
    }

    # 4. Delegate
    result = delegate_to_coach(**delegation)

    # 5. Hand off to user
    return "The Relationship Coach would be great for exploring this. Want to chat with them?"
```

**Relationship Coach Execution:**
```
RC: "Hi! I heard you've been thinking about relationships.
     I'd love to help you explore your patterns.
     Let's start with attachment style - how do you typically feel
     in close relationships? Secure? Anxious? Independent?"

(Natural, expert-driven, contextually perfect)
```

**Return Protocol:**
```python
# After RC session
delegation_result = {
    "delegation_id": "xyz789",
    "coach": "Relationship Coach",
    "status": "completed",
    "traits_collected": [
        "ReDNA.AttachmentStyleDNA",
        "ReDNA.IntimacyPatternsDNA",
        "ReDNA.ConflictResolutionDNA"
    ],
    "curiosity_satisfied": 0.89,
    "notes": "User engaged deeply, explored attachment and conflict patterns"
}

# Head Coach gets notification
# Updates curiosity agenda
# Continues conversation naturally
```

---

## Next Steps

1. **Review & Approve**: Get stakeholder approval on design
2. **Phase 1 Implementation**: Build foundation (coach registry, delegation API)
3. **Phase 2 Integration**: Connect Head Coach and specialized coaches
4. **Testing**: Validate natural conversation flow, measure curiosity reduction
5. **Phase 3 Optimization**: Refine based on real usage data

---

## Open Questions

1. **Parallel Delegations**: Can multiple coaches work with user simultaneously?
2. **Delegation Fatigue**: What if user is delegated too often?
3. **Coach Availability**: What if primary coach is unavailable? Fallback strategy?
4. **Cross-Coach Context**: Do coaches share context from delegations?
5. **User Control**: Can user veto delegations? ("I don't want to talk to RC right now")

---

**End of Coach Delegation Framework Design**
