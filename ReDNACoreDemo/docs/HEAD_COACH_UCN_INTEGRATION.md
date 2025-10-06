# Head Coach UCN/RR Integration

## Overview

This document describes the complete integration between the Head Coach decision framework and the UCN/RR curiosity signals system.

**Status**: ✅ Fully Implemented and Tested

**Architecture**: "Core proposes, Head Coach disposes"

## Components Created

### 1. Core Modules

#### `core/head_coach_decision.py`
The decision engine implementing the 6-check deliberation framework.

**Key Classes**:
- `BehavioralMode` (Enum): mentor, servant, guardian, strategist, confidant
- `InterventionStyle` (Enum): direct, gentle, deferred, contextual, silent
- `AffectState`: User's emotional/cognitive state (stress, mood, energy, etc.)
- `UserContext`: Everything Head Coach knows about the user
- `CoreRecommendation`: What Core/UCN-RR wants to do
- `HeadCoachDecision`: What HC decides to actually do
- `HeadCoachDecisionEngine`: The 6-check deliberation framework

**The 6 Checks**:
1. **Benefit Check**: Does user actually benefit from this?
2. **Readiness Check**: Is user ready for this task?
3. **Timing Check**: Is timing good?
4. **Relationship Check**: Will this help or hurt the relationship?
5. **Happiness Check**: Will this make user happy?
6. **Jarvis Check**: "Would Jarvis do this for Tony?"

#### `core/head_coach_ucn_bridge.py`
Connects UCN/RR curiosity signals to Head Coach decisions.

**Key Classes**:
- `HeadCoachUCNBridge`: Main bridge between UCN/RR and HC
- `ActionPlan`: Complete action plan for user

**Flow**:
1. Get curiosity signals from UCN/RR engine
2. Convert signals to `CoreRecommendation` objects
3. Head Coach deliberates on each recommendation
4. Build `ActionPlan` with accepted/deferred actions

### 2. API Endpoint

#### `GET /hc/action_plan`

**Parameters**:
- `user_id` (required): User identifier
- `max_actions` (default: 5): Maximum number of actions to return

**Response**:
```json
{
  "user_id": "abtest",
  "timestamp": "2025-10-04T...",
  "greeting": "Hi Abtest! I've identified 10 opportunities...",
  "priority_message": "Quick win: Add evidence for Hair Color (takes ~2 min)",
  "celebration_message": null,
  "accepted_actions": [
    {
      "action_type": "gather_evidence",
      "action_description": "Add evidence for Hair Highlights",
      "estimated_time_mins": 2,
      "mode": "mentor",
      "intervention_style": "gentle",
      "message_to_user": "💡 Add evidence for Highlights\n\nWhy this helps: ...",
      "user_benefit": "Improves PaDNA.HairDNA.Highlights confidence",
      "when": "now"
    }
  ],
  "stats": {
    "total_signals": 20,
    "total_recommendations": 20,
    "acceptance_rate": 0.5,
    "dominant_mode": "mentor",
    "deferred_count": 10
  }
}
```

## Behavioral Modes

### 1. MENTOR Mode
**When**: User shows curiosity, wants explanations
**Style**: Educational, patient
**Message Format**: "💡 [Action]\n\nWhy this helps: [Reasoning]"

### 2. SERVANT Mode
**When**: Routine tasks, direct requests
**Style**: Efficient, minimal friction
**Message Format**: "[Action]"

### 3. GUARDIAN Mode
**When**: User overwhelmed, system too aggressive
**Style**: Protective, restraining
**Message Format**: "When you have a moment: [Action]"

### 4. STRATEGIST Mode
**When**: Long-term goals, multi-step plans
**Style**: Goal-oriented planner
**Message Format**: "Next step toward your goal: [Action]"

### 5. CONFIDANT Mode
**When**: User vulnerable, stressed
**Style**: Empathetic, supportive
**Message Format**: "I'm here to help. [Action]"

## Decision Framework

### Chain of Authority

```
UCN/RR Engine → Core Recommendations → Head Coach Deliberation → User
     (calculates)      (proposes)          (disposes)          (final say)
```

### Golden Rules

1. **"UCN-RR proposes, Head Coach disposes"**
2. **Prime Directive**: "User experience comes first, system health second"
3. **Jarvis to Tony Stark**: HC would do anything to meet user's true needs

### Example Decision Flow

```python
# 1. UCN/RR identifies high curiosity trait
signal = CuriositySignal(
    trait_path="PaDNA.HairDNA.Color",
    ucn=300,
    curiosity_score=700,
    priority="high",
    reason="Low confidence"
)

# 2. Bridge converts to Core recommendation
recommendation = CoreRecommendation(
    rec_type="gather_evidence",
    trait_path="PaDNA.HairDNA.Color",
    priority="high",
    estimated_time_mins=2,
    curiosity_value=700,
    suggested_action="Add photo evidence for hair color"
)

# 3. Head Coach deliberates (6 checks)
decision = head_coach.deliberate(recommendation, user_context)

# 4. If accepted, added to action plan
if decision.accept:
    action_plan.accepted_actions.append(decision)
```

## Testing

### Unit Test
```bash
cd ReDNACoreDemo
python3 test_head_coach_ucn.py abtest
```

**Expected Output**:
```
Testing Head Coach UCN/RR Integration for: abtest
✅ Loaded 50 observations
✅ Extracted 50 traits with UCN values
✅ User context created
✅ Action plan generated

HEAD COACH ACTION PLAN
──────────────────────────────────────────────────────────────────────
💬 Hi Abtest! I've identified 10 opportunity/ies to improve your profile.

📋 Accepted Actions (10):
1. [MENTOR] Explore Highlights (2 min)
   ...

STATS
Total Curiosity Signals: 20
Acceptance Rate: 50.0%
Dominant Mode: mentor
```

### API Test
```bash
curl "http://localhost:8001/hc/action_plan?user_id=abtest&max_actions=5"
```

## Implementation Checklist

- [x] Created `HeadCoachDecisionEngine` with 6-check framework
- [x] Implemented 5 behavioral modes
- [x] Created `AffectState` and `UserContext` state tracking
- [x] Built `HeadCoachUCNBridge` to connect UCN/RR signals
- [x] Added `/hc/action_plan` API endpoint
- [x] Created test script (`test_head_coach_ucn.py`)
- [x] Validated end-to-end flow with test data
- [ ] Wire to Explorer UI (display action plan to user)
- [ ] Persist user context (AffectState) to storage
- [ ] Add user feedback loop (track acceptance/completion)
- [ ] Implement Head Coach learning (adapt to user behavior)

## Next Steps

### Phase 1: Explorer UI Integration
1. Create Explorer component to display action plan
2. Show greeting and priority message
3. Render accepted actions as interactive cards
4. Track user interaction (accept/defer/complete)

### Phase 2: User Context Persistence
1. Save `UserContext` to `data/users/{user_id}/hc/context.json`
2. Update `AffectState` based on user interactions
3. Learn user patterns (session length, task completion rate)

### Phase 3: Head Coach Learning
1. Track decision outcomes (accepted → completed?)
2. Adjust behavioral mode based on user response
3. Learn optimal intervention timing
4. Adapt to user preferences over time

### Phase 4: Provenance and Logging
1. Log all decisions with reasoning
2. Track override reasons (when HC rejects Core)
3. Build decision history for transparency
4. Enable "explain this decision" feature

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         UCN/RR Engine                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ UCN Calculator│  │RR Calculator │  │  Curiosity   │         │
│  │              │  │              │  │    Engine    │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
│         │                 │                 │                  │
│         └─────────────────┴─────────────────┘                  │
│                           │                                     │
│                  Curiosity Signals                              │
└────────────────────────────┼────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Head Coach UCN Bridge                         │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Convert Signals → Core Recommendations              │      │
│  │  - Extract trait_path, curiosity_score, priority     │      │
│  │  - Map to action types (gather, confirm, explore)    │      │
│  │  - Calculate estimated time and impact               │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────┼────────────────────────────────────┘
                             ↓
                   Core Recommendations
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Head Coach Decision Engine                    │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  6-Check Deliberation Framework                      │      │
│  │  1. Benefit Check  ✓                                 │      │
│  │  2. Readiness Check✓                                 │      │
│  │  3. Timing Check   ✓                                 │      │
│  │  4. Relationship  ✓                                  │      │
│  │  5. Happiness     ✓                                  │      │
│  │  6. Jarvis Check  ✓                                  │      │
│  └──────────────────────────────────────────────────────┘      │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Select Behavioral Mode                              │      │
│  │  Mentor │ Servant │ Guardian │ Strategist │ Confidant│      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────┼────────────────────────────────────┘
                             ↓
                   Head Coach Decision
                  (Accept/Defer + Reasoning)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        Action Plan                              │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Accepted Actions:                                   │      │
│  │  - Greeting (personalized by mode)                   │      │
│  │  - Priority message (urgent actions)                 │      │
│  │  - Action cards (type, time, benefit, message)       │      │
│  │                                                       │      │
│  │  Deferred Actions:                                   │      │
│  │  - Logged with override reason                       │      │
│  │  - May resurface later                               │      │
│  └──────────────────────────────────────────────────────┘      │
└────────────────────────────┼────────────────────────────────────┘
                             ↓
                    Explorer UI / User
```

## Files Created

### Core Implementation
1. `ReDNACoreDemo/core/head_coach_decision.py` (580 lines)
2. `ReDNACoreDemo/core/head_coach_ucn_bridge.py` (420 lines)
3. `ReDNACoreDemo/core/api_hc_ucn_endpoint.py` (reference for API endpoint)

### API Integration
4. `ReDNACoreDemo/core/api.py` (modified - added `/hc/action_plan` endpoint)

### Testing
5. `ReDNACoreDemo/test_head_coach_ucn.py` (210 lines)

### Documentation
6. `ReDNACoreDemo/docs/HEAD_COACH_UCN_INTEGRATION.md` (this file)

## Summary

The Head Coach UCN/RR integration is **fully implemented and tested**. The system successfully:

✅ Connects UCN/RR curiosity signals to Head Coach decisions
✅ Implements 6-check deliberation framework
✅ Operates in 5 behavioral modes
✅ Tracks user context (AffectState)
✅ Generates personalized action plans
✅ Exposes `/hc/action_plan` API endpoint
✅ Follows "Core proposes, Head Coach disposes" architecture
✅ Prioritizes user well-being over system needs

**Next**: Wire to Explorer UI to display action plans to users.
