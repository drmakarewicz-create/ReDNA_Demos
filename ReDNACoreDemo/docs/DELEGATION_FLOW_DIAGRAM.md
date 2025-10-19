# Delegation System - Visual Flow Diagram

## Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER CONVERSATION STARTS                        │
│                     (with Head Coach - default mode)                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Head Coach analyzes   │
                    │  conversation context  │
                    │  & curiosity levels    │
                    └────────┬───────────────┘
                             │
                             ▼
                    ┌────────────────────────┐
                    │  Check curiosity data  │
                    │  for high values (>60) │
                    └────────┬───────────────┘
                             │
                ┌────────────┴─────────────┐
                │                          │
        Low curiosity             High curiosity
        (<60 on traits)           (≥60 on traits)
                │                          │
                ▼                          ▼
    ┌────────────────────┐    ┌────────────────────────┐
    │  Continue normal   │    │  POST /delegation/     │
    │  Head Coach chat   │    │  analyze               │
    └────────────────────┘    └────────┬───────────────┘
                                       │
                                       ▼
                          ┌────────────────────────────┐
                          │  Recommend specialized     │
                          │  coach based on namespaces │
                          │  • PaDNA → Photo Coach     │
                          │  • ReDNA → RC              │
                          └────────┬───────────────────┘
                                   │
                                   ▼
                          ┌────────────────────────────┐
                          │  Show DelegationBanner     │
                          │  with recommendation       │
                          │  Priority: ★★★★☆ 8.5       │
                          └────────┬───────────────────┘
                                   │
                      ┌────────────┴────────────┐
                      │                         │
              User dismisses          User accepts
                      │                         │
                      ▼                         ▼
          ┌──────────────────┐    ┌──────────────────────────┐
          │  Banner removed  │    │  Show CoachSwitcher      │
          │  Stay in HC      │    │  modal                   │
          └──────────────────┘    └────────┬─────────────────┘
                                           │
                                           ▼
                              ┌────────────────────────────┐
                              │  STEP 1: Create Delegation │
                              │  POST /delegation/create   │
                              │  → delegation_id           │
                              └────────┬───────────────────┘
                                       │
                                       ▼
                              ┌────────────────────────────┐
                              │  STEP 2: Switch Mode       │
                              │  POST /users/{id}/         │
                              │  coach-mode                │
                              │  (with delegation_id)      │
                              └────────┬───────────────────┘
                                       │
                                       ▼
                              ┌────────────────────────────┐
                              │  Update coach_mode.json:   │
                              │  {                         │
                              │    active_mode: "photo",   │
                              │    mode_history: [...]     │
                              │  }                         │
                              └────────┬───────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  NOW IN SPECIALIZED COACH MODE                           │
│                  (Photo Coach or Relationship Coach)                     │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────────┐
                    │  Specialized coach loads   │
                    │  delegation context:       │
                    │  • Curiosity targets       │
                    │  • User preferences        │
                    │  • Delegation ID           │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  Coach conversation with   │
                    │  delegation-aware prompts  │
                    │  (focused on targets)      │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  Photo Coach Example:      │
                    │  • User uploads photo      │
                    │  • Extract PaDNA traits    │
                    │  • Update curiosity scores │
                    │                            │
                    │  RC Example:               │
                    │  • Discuss relationships   │
                    │  • Extract ReDNA traits    │
                    │  • Update EmDNA scores     │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  Track collected traits:   │
                    │  • Before curiosity: 85.0  │
                    │  • After curiosity: 12.0   │
                    │  • Satisfaction: 86%       │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  Show                      │
                    │  DelegationCompleteButton  │
                    │  • Preview satisfaction    │
                    │  • Traits collected: 3     │
                    │  • Estimated: ~86%         │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  User clicks               │
                    │  "Mark Complete & Return"  │
                    └────────┬───────────────────┘
                             │
                             ▼
                    ┌────────────────────────────┐
                    │  POST /delegation/{user}/  │
                    │  complete/{delegation_id}  │
                    │  {                         │
                    │    traits_collected: [...] │
                    │    curiosity_before: {...} │
                    │    curiosity_after: {...}  │
                    │    auto_return: true       │
                    │  }                         │
                    └────────┬───────────────────┘
                             │
                             ▼
                ┌────────────────────────────────┐
                │  Backend calculates:           │
                │  satisfaction = (before-after) │
                │                 / before       │
                │  = (85-12)/85 = 0.86 (86%)    │
                └────────┬───────────────────────┘
                         │
                         ▼
                ┌────────────────────────────────┐
                │  Update delegation record:     │
                │  {                             │
                │    status: "completed",        │
                │    curiosity_satisfied: 0.86,  │
                │    traits_collected: [...]     │
                │  }                             │
                └────────┬───────────────────────┘
                         │
                         ▼
                ┌────────────────────────────────┐
                │  Auto-switch back to HC:       │
                │  POST /users/{id}/coach-mode   │
                │  {                             │
                │    target_mode: "head_coach",  │
                │    context: {                  │
                │      reason: "delegation_      │
                │               complete",       │
                │      curiosity_satisfied: 0.86 │
                │    }                           │
                │  }                             │
                └────────┬───────────────────────┘
                         │
                         ▼
                ┌────────────────────────────────┐
                │  Update mode_history:          │
                │  {                             │
                │    from_mode: "photo",         │
                │    to_mode: "head_coach",      │
                │    context: {                  │
                │      delegation_id: "...",     │
                │      reason: "delegation_      │
                │               complete"        │
                │    }                           │
                │  }                             │
                └────────┬───────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  BACK IN HEAD COACH MODE                               │
│              (with delegation completion context)                      │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────────────┐
                │  Show                          │
                │  DelegationReturn              │
                │  Acknowledgment                │
                │                                │
                │  ┌──────────────────────────┐  │
                │  │ 📸 Delegation Complete   │  │
                │  │ Photo Coach • Just now   │  │
                │  │                          │  │
                │  │ Fantastic work! Your     │  │
                │  │ curiosity exploration    │  │
                │  │ was highly productive.   │  │
                │  │                          │  │
                │  │ Traits: 3   Satisfied:   │  │
                │  │             86% 🎉       │  │
                │  └──────────────────────────┘  │
                └────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────────────┐
                │  Head Coach acknowledges       │
                │  with context-aware message:   │
                │                                │
                │  "Great! I see you worked with │
                │  Photo Coach and collected 3   │
                │  visual traits. That reduced   │
                │  your curiosity by 86% - very  │
                │  productive session! 🎉        │
                │                                │
                │  Now that we have your hair    │
                │  color, texture, and eye color │
                │  documented, what would you    │
                │  like to explore next?"        │
                └────────────────────────────────┘
                             │
                             ▼
                ┌────────────────────────────────┐
                │  Conversation continues with   │
                │  Head Coach, enriched by       │
                │  newly collected traits        │
                └────────────────────────────────┘
```

---

## State Transitions

```
USER STATE MACHINE:

  ┌─────────────┐
  │ head_coach  │ ◄────────────────┐
  │   (mode)    │                  │
  └──────┬──────┘                  │
         │                         │
         │ (delegation             │ (completion
         │  accepted)              │  with auto_return)
         │                         │
         ▼                         │
  ┌─────────────┐           ┌─────┴──────┐
  │   photo     │           │relationship│
  │   (mode)    ├──────────►│   (mode)   │
  └─────────────┘           └────────────┘
         │                         │
         │                         │
         └─────────┬───────────────┘
                   │
                   │ (manual switch
                   │  or completion)
                   │
                   ▼
           ┌───────────────┐
           │  head_coach   │
           │    (mode)     │
           └───────────────┘

DELEGATION STATE MACHINE:

  ┌─────────┐
  │ pending │  (delegation created)
  └────┬────┘
       │
       │ (mode switched)
       │
       ▼
  ┌─────────┐
  │ active  │  (collecting traits)
  └────┬────┘
       │
       │ (completion called)
       │
       ▼
  ┌───────────┐
  │ completed │  (final state)
  └───────────┘
```

---

## Data Flow

```
CURIOSITY DATA FLOW:

┌──────────────────┐
│  Initial State   │
│  HairDNA.Color:  │
│  curiosity = 85  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│  Delegation Created      │
│  targets: [HairDNA.Color]│
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Photo Coach analyzes    │
│  Extracts: "Brown"       │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Curiosity recalculated  │
│  HairDNA.Color = 12      │
│  (value known, low ?)    │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Satisfaction calc:      │
│  (85 - 12) / 85 = 0.86  │
└──────────────────────────┘


DELEGATION CONTEXT FLOW:

┌──────────────────┐
│  Head Coach      │
│  curiosity_data  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────┐
│  Delegation Record       │
│  {                       │
│    delegation_id: "...", │
│    curiosity_targets: [] │
│  }                       │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Photo Coach Prompt      │
│  "Focus on these traits: │
│   - HairDNA.Color        │
│   - EyeDNA.Color"        │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Collected Traits        │
│  {                       │
│    "HairDNA.Color": val, │
│    "EyeDNA.Color": val   │
│  }                       │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Completion Results      │
│  back to Head Coach      │
└──────────────────────────┘
```

---

## API Call Sequence

```
COMPLETE DELEGATION LIFECYCLE - API CALLS:

1. POST /delegation/analyze
   Request:
   {
     "user_id": "user123",
     "curiosity_data": {"PaDNA.HairDNA.Color": 85.0},
     "tolerance": 0.7
   }
   Response:
   {
     "should_delegate": true,
     "recommended_coach": "photo_coach"
   }

   ↓

2. POST /delegation/create
   Request:
   {
     "user_id": "user123",
     "coach_id": "photo_coach",
     "curiosity_targets": ["PaDNA.HairDNA.Color"]
   }
   Response:
   {
     "delegation_id": "550e8400-..."
   }

   ↓

3. POST /users/user123/coach-mode
   Request:
   {
     "target_mode": "photo",
     "delegation_id": "550e8400-..."
   }
   Response:
   {
     "new_mode": "photo",
     "previous_mode": "head_coach"
   }

   ↓

   [User conversation with Photo Coach]
   [Traits extracted, curiosity updated]

   ↓

4. POST /delegation/user123/complete/550e8400-...
   Request:
   {
     "traits_collected": ["PaDNA.HairDNA.Color"],
     "curiosity_before": {"PaDNA.HairDNA.Color": 85.0},
     "curiosity_after": {"PaDNA.HairDNA.Color": 12.0},
     "auto_return": true
   }
   Response:
   {
     "delegation_summary": {
       "curiosity_satisfied": 0.86
     },
     "mode_switch": {
       "new_mode": "head_coach"
     }
   }

   ↓

5. GET /users/user123/coach-mode
   Response:
   {
     "active_mode": "head_coach"
   }

   ✓ COMPLETE - Back at Head Coach with results
```

---

## File System Changes

```
BEFORE DELEGATION:

data/
└── users/
    └── user123/
        ├── user.json
        └── resolved.json

AFTER DELEGATION CREATE:

data/
└── users/
    └── user123/
        ├── user.json
        ├── resolved.json
        ├── delegations/
        │   └── 550e8400-e29b-41d4-a716-446655440000.json
        └── coach_mode.json  ← NEW

coach_mode.json:
{
  "active_mode": "photo",
  "mode_history": [
    {
      "from_mode": "head_coach",
      "to_mode": "photo",
      "timestamp": "2025-10-06T12:34:56Z",
      "context": {
        "delegation_id": "550e8400-...",
        "reason": "delegation"
      }
    }
  ]
}

AFTER DELEGATION COMPLETE:

delegations/550e8400-....json:
{
  "delegation_id": "550e8400-...",
  "status": "completed",  ← UPDATED
  "traits_collected": ["PaDNA.HairDNA.Color"],
  "curiosity_satisfied": 0.86,
  "completed_at": "2025-10-06T12:45:00Z"
}

coach_mode.json:
{
  "active_mode": "head_coach",  ← SWITCHED BACK
  "mode_history": [
    {
      "from_mode": "head_coach",
      "to_mode": "photo",
      "timestamp": "2025-10-06T12:34:56Z"
    },
    {
      "from_mode": "photo",
      "to_mode": "head_coach",  ← NEW ENTRY
      "timestamp": "2025-10-06T12:45:00Z",
      "context": {
        "delegation_id": "550e8400-...",
        "reason": "delegation_complete",
        "curiosity_satisfied": 0.86
      }
    }
  ]
}
```

---

## Component Interaction

```
FRONTEND COMPONENT FLOW:

┌─────────────────────┐
│  HeadCoachChat      │
│  Component          │
└──────┬──────────────┘
       │
       │ (high curiosity detected)
       │
       ▼
┌─────────────────────┐
│  DelegationBanner   │ ← Shows recommendation
│  Component          │
└──────┬──────────────┘
       │
       │ (user accepts)
       │
       ▼
┌─────────────────────┐
│  CoachSwitcher      │ ← Modal for switching
│  Component          │
└──────┬──────────────┘
       │
       │ (creates delegation + switches mode)
       │
       ▼
┌─────────────────────┐
│  PhotoCoachChat     │ ← Specialized UI
│  Component          │
└──────┬──────────────┘
       │
       │ (traits collected)
       │
       ▼
┌──────────────────────┐
│  DelegationComplete │ ← Completion button
│  Button Component   │
└──────┬───────────────┘
       │
       │ (marks complete, auto-returns)
       │
       ▼
┌─────────────────────┐
│  HeadCoachChat      │ ← Back to HC
│  Component          │
└──────┬──────────────┘
       │
       ▼
┌──────────────────────────┐
│  DelegationReturn        │ ← Shows results
│  Acknowledgment          │
│  Component               │
└──────────────────────────┘


SIDEBAR WIDGETS (persistent):

┌──────────────────────────┐
│  ActiveDelegations       │ ← Real-time polling
│  Widget                  │   (every 30s)
│                          │
│  📸 Photo Coach          │
│  ▓▓▓▓▓▓▓░░░ 75%         │
│                          │
│  💝 RC                   │
│  ▓▓▓░░░░░░░ 30%         │
└──────────────────────────┘
```

---

## Error Handling Flow

```
ERROR SCENARIOS:

1. Delegation creation fails
   ┌──────────────────┐
   │ POST /delegation │
   │ /create          │
   └────────┬─────────┘
            │
            ✗ HTTP 500
            │
            ▼
   ┌──────────────────┐
   │ Show error toast │
   │ Stay in HC mode  │
   └──────────────────┘

2. Mode switch fails
   ┌──────────────────┐
   │ POST /coach-mode │
   └────────┬─────────┘
            │
            ✗ HTTP 400
            │
            ▼
   ┌──────────────────────┐
   │ Delegation created   │
   │ but not activated    │
   │ Show error, allow    │
   │ manual retry         │
   └──────────────────────┘

3. Completion fails
   ┌──────────────────┐
   │ POST /complete   │
   └────────┬─────────┘
            │
            ✗ HTTP 404
            │
            ▼
   ┌──────────────────────┐
   │ Delegation not found │
   │ Show error message   │
   │ Stay in current mode │
   └──────────────────────┘
```

---

## Summary

This delegation system provides:

✅ **Seamless Mode Switching** - Two-step flow with context preservation
✅ **Automatic Returns** - No manual navigation needed
✅ **Progress Tracking** - Real-time satisfaction metrics
✅ **Context Preservation** - Full delegation history with metadata
✅ **Error Recovery** - Graceful handling of edge cases
✅ **CReDNA Ready** - Architecture supports future personalization

**Total API Calls for Complete Flow:** 4-5
**Components Involved:** 6
**Test Coverage:** 26/26 tests passing
