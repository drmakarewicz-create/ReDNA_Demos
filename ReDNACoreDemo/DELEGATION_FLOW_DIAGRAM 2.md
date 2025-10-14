# Delegation System - Visual Flow Diagrams

## Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER CONVERSING WITH HEAD COACH                       │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │  Head Coach detects high       │
                    │  curiosity in specific traits  │
                    │  (e.g., PaDNA.* = 85%+)       │
                    └────────────────┬───────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │  POST /delegation/analyze      │
                    │  → should_delegate: true       │
                    │  → recommended_coach: photo    │
                    └────────────────┬───────────────┘
                                     │
                                     ▼
                    ╔════════════════════════════════╗
                    ║   DELEGATION BANNER APPEARS    ║
                    ║   "📸 Photo Coach can help     ║
                    ║    with 3 items (Priority: 9)" ║
                    ╚════════════════┬═══════════════╝
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
           ┌─────────────────┐             ┌─────────────────┐
           │  User Dismisses │             │  User Accepts   │
           └─────────────────┘             └────────┬────────┘
                    │                               │
                    ▼                               ▼
           ┌─────────────────┐         ╔═══════════════════════╗
           │ Banner removed  │         ║  COACH SWITCHER MODAL ║
           │ Head Coach      │         ║  Shows: HC → Photo    ║
           │ continues       │         ╚═══════════┬═══════════╝
           └─────────────────┘                     │
                                                   ▼
                                      ┌────────────────────────┐
                                      │ Step 1: Create         │
                                      │ POST /delegation/create│
                                      │ → delegation_id        │
                                      └────────────┬───────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────┐
                                      │ Step 2: Switch Mode    │
                                      │ POST /users/.../mode   │
                                      │ → new_mode: photo      │
                                      └────────────┬───────────┘
                                                   │
                                                   ▼
                              ┌────────────────────────────────┐
                              │  PHOTO COACH INTERFACE LOADS   │
                              │  (Delegation context active)   │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │  User uploads photo            │
                              │  Photo Coach analyzes image    │
                              │  Extracts traits:              │
                              │  • PaDNA.HairDNA.Color         │
                              │  • PaDNA.EyeDNA.Color          │
                              │  Updates curiosity scores      │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ╔════════════════════════════════╗
                              ║ DELEGATION COMPLETE BUTTON     ║
                              ║ "✓ Mark Complete & Return"     ║
                              ║                                ║
                              ║ Preview:                       ║
                              ║ Traits: 2                      ║
                              ║ Satisfaction: ~88%             ║
                              ╚════════════════┬═══════════════╝
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │ POST /delegation/.../complete  │
                              │ • traits_collected             │
                              │ • curiosity_before/after       │
                              │ • auto_return: true            │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │ Backend calculates satisfaction│
                              │ Auto-switch to head_coach mode │
                              │ Returns summary & mode_switch  │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │  HEAD COACH INTERFACE LOADS    │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ╔════════════════════════════════╗
                              ║ DELEGATION ACKNOWLEDGMENT     ║
                              ║ "🎉 Fantastic work!"          ║
                              ║                                ║
                              ║ ✓ Traits Collected: 2          ║
                              ║ ↓ Curiosity Satisfied: 88%     ║
                              ║                                ║
                              ║ Explored: PaDNA (2)            ║
                              ╚════════════════┬═══════════════╝
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │ Head Coach continues with      │
                              │ enriched context about traits  │
                              │ Curiosity reduced in PaDNA     │
                              └────────────────────────────────┘
```

---

## API Call Sequence Diagram

```
User         UI Components           Backend API              Data Layer
 │               │                        │                        │
 │  1. Chat      │                        │                        │
 ├──────────────>│                        │                        │
 │               │ 2. Analyze Curiosity   │                        │
 │               ├───────────────────────>│                        │
 │               │                        │ 3. Check thresholds    │
 │               │                        ├───────────────────────>│
 │               │ 4. Recommendation      │                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
 │  5. Accept    │                        │                        │
 │  Delegation   │                        │                        │
 ├──────────────>│                        │                        │
 │               │ 6. Create Delegation   │                        │
 │               ├───────────────────────>│                        │
 │               │                        │ 7. Save record         │
 │               │                        ├───────────────────────>│
 │               │                        │    delegation.json     │
 │               │ 8. delegation_id       │                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
 │               │ 9. Switch Mode         │                        │
 │               ├───────────────────────>│                        │
 │               │                        │ 10. Update mode        │
 │               │                        ├───────────────────────>│
 │               │                        │    coach_mode.json     │
 │               │ 11. mode switched      │                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
 │  12. Navigate │                        │                        │
 │  to Photo     │                        │                        │
 │  Coach        │                        │                        │
 ├──────────────>│                        │                        │
 │               │                        │                        │
 │  13. Upload   │                        │                        │
 │  Photo        │                        │                        │
 ├──────────────>│ 14. Analyze Photo      │                        │
 │               ├───────────────────────>│                        │
 │               │                        │ 15. Extract traits     │
 │               │                        ├───────────────────────>│
 │               │ 16. Traits + Curiosity │                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
 │  17. Complete │                        │                        │
 │  Delegation   │                        │                        │
 ├──────────────>│ 18. Complete Request   │                        │
 │               ├───────────────────────>│                        │
 │               │                        │ 19. Calculate          │
 │               │                        │     satisfaction       │
 │               │                        │ 20. Update delegation  │
 │               │                        ├───────────────────────>│
 │               │                        │    status=completed    │
 │               │                        │ 21. Switch to HC       │
 │               │                        ├───────────────────────>│
 │               │                        │    mode=head_coach     │
 │               │ 22. Summary + Switch   │                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
 │  23. Navigate │                        │                        │
 │  to HC        │                        │                        │
 ├──────────────>│                        │                        │
 │               │ 24. Show Acknowledgment│                        │
 │               │<───────────────────────┤                        │
 │               │                        │                        │
```

---

## Component Interaction Map

```
┌──────────────────────────────────────────────────────────────────┐
│                        HEAD COACH CHAT                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Chat Transcript                                            │ │
│  │ • Messages                                                 │ │
│  │ • User input                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DelegationBanner (conditional)                             │ │
│  │ Props:                                                     │ │
│  │ • recommendation: {coach, targets, priority}               │ │
│  │ • onAccept: () => setShowSwitcher(true)                    │ │
│  │ • onDismiss: () => setBanner(null)                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ CoachSwitcher Modal (conditional)                          │ │
│  │ Props:                                                     │ │
│  │ • userId, currentCoach, targetCoach                        │ │
│  │ • curiosityTargets                                         │ │
│  │ • onSwitchComplete: (delegationId) => navigate()           │ │
│  │ • onCancel: () => setShowSwitcher(false)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DelegationReturnAcknowledgment (conditional)               │ │
│  │ Props:                                                     │ │
│  │ • delegationId, coachMode                                  │ │
│  │ • traitsCollected, curiositySatisfied                      │ │
│  │ • notes, timestamp                                         │ │
│  │ • onDismiss: () => clearAcknowledgment()                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     PHOTO COACH INTERFACE                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Header: "📸 Photo Coach"                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Chat Transcript                                            │ │
│  │ • Photo upload area                                        │ │
│  │ • Analysis results                                         │ │
│  │ • Trait collection display                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DelegationCompleteButton (sticky footer)                   │ │
│  │ Props:                                                     │ │
│  │ • userId, delegationId                                     │ │
│  │ • traitsCollected: string[]                                │ │
│  │ • curiosityBefore/After: Record<string, number>            │ │
│  │ • notes: string                                            │ │
│  │ • variant: "success"                                       │ │
│  │ • onComplete: (summary) => navigateToHC()                  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                         SIDEBAR (Global)                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ActiveDelegationsWidget                                    │ │
│  │ Props:                                                     │ │
│  │ • userId                                                   │ │
│  │ • onDelegationClick: (id) => navigate()                    │ │
│  │                                                            │ │
│  │ Features:                                                  │ │
│  │ • Real-time polling (30s)                                  │ │
│  │ • Shows active delegations                                 │ │
│  │ • Progress bars for satisfaction                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ DelegationHistoryPanel (expandable)                        │ │
│  │ Props:                                                     │ │
│  │ • userId                                                   │ │
│  │ • onClose: () => closePanel()                              │ │
│  │                                                            │ │
│  │ Features:                                                  │ │
│  │ • Stats summary                                            │ │
│  │ • Expandable delegation cards                              │ │
│  │ • Filter by coach                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## State Management Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DELEGATION STATE                          │
└─────────────────────────────────────────────────────────────┘

Local Component State:
┌──────────────────────────────────────────────────────────────┐
│ HeadCoachChat                                                │
│ • delegationRecommendation: DelegationRecommendation | null  │
│ • showCoachSwitcher: boolean                                 │
│ • completedDelegation: DelegationSummary | null              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ PhotoCoachChat                                               │
│ • delegationId: string                                       │
│ • traitsCollected: string[]                                  │
│ • curiosityBefore: Record<string, number>                    │
│ • curiosityAfter: Record<string, number>                     │
└──────────────────────────────────────────────────────────────┘

Backend Persistent State:
┌──────────────────────────────────────────────────────────────┐
│ data/users/{user_id}/                                        │
│                                                              │
│ ├─ coach_mode.json                                           │
│ │  {                                                         │
│ │    "active_mode": "photo",                                 │
│ │    "mode_history": [                                       │
│ │      {                                                     │
│ │        "from_mode": "head_coach",                          │
│ │        "to_mode": "photo",                                 │
│ │        "timestamp": "2025-10-06T12:34:56Z",                │
│ │        "context": {"delegation_id": "..."}                 │
│ │      }                                                     │
│ │    ]                                                       │
│ │  }                                                         │
│                                                              │
│ ├─ delegations/                                              │
│ │  └─ {delegation_id}.json                                   │
│ │     {                                                      │
│ │       "delegation_id": "550e8400-...",                     │
│ │       "coach": "photo_coach",                              │
│ │       "status": "completed",                               │
│ │       "curiosity_targets": ["PaDNA.HairDNA.Color"],        │
│ │       "traits_collected": ["PaDNA.HairDNA.Color"],         │
│ │       "curiosity_before": {"PaDNA.HairDNA.Color": 85.0},   │
│ │       "curiosity_after": {"PaDNA.HairDNA.Color": 12.0},    │
│ │       "curiosity_satisfied": 0.86,                         │
│ │       "notes": "...",                                      │
│ │       "created_at": "2025-10-06T12:34:56Z",                │
│ │       "completed_at": "2025-10-06T12:45:00Z"               │
│ │     }                                                      │
└──────────────────────────────────────────────────────────────┘
```

---

## Decision Tree: When to Delegate?

```
                    ┌────────────────────┐
                    │  User sends message│
                    │  to Head Coach     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │ Calculate curiosity│
                    │ for all traits     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ╔═════════════════════╗
                    ║ Any trait >= 60%    ║
                    ║ curiosity?          ║
                    ╚═════════┬═══════════╝
                              │
                  ┌───────────┴───────────┐
                  │                       │
                 NO                      YES
                  │                       │
                  ▼                       ▼
        ┌──────────────────┐    ┌──────────────────┐
        │ Continue normal  │    │ Group by namespace│
        │ conversation     │    │ Find best coach   │
        └──────────────────┘    └─────────┬─────────┘
                                          │
                                          ▼
                                ╔═════════════════════╗
                                ║ Check user          ║
                                ║ ToleranceForNudging ║
                                ╚═════════┬═══════════╝
                                          │
                        ┌─────────────────┼─────────────────┐
                        │                 │                 │
                    < 0.5             0.5-0.8            > 0.8
                        │                 │                 │
                        ▼                 ▼                 ▼
                ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                │ Low:        │   │ Balanced:   │   │ High:       │
                │ Only if     │   │ Suggest if  │   │ Proactively │
                │ user asks   │   │ appropriate │   │ suggest     │
                └─────────────┘   └──────┬──────┘   └──────┬──────┘
                                         │                 │
                                         └────────┬────────┘
                                                  │
                                                  ▼
                                        ┌──────────────────┐
                                        │ Show Delegation  │
                                        │ Banner with      │
                                        │ recommendation   │
                                        └──────────────────┘
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    ERROR SCENARIOS                           │
└─────────────────────────────────────────────────────────────┘

Scenario 1: Delegation Creation Fails
┌────────────────────────────────────────┐
│ User accepts delegation                │
│ CoachSwitcher: createDelegation()      │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ API Error     │
        │ (500, 404)    │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Show error UI │
        │ "Try Again"   │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Retry button  │
        │ OR Cancel     │
        └───────────────┘

Scenario 2: Mode Switch Fails After Delegation Created
┌────────────────────────────────────────┐
│ Delegation created successfully        │
│ delegation_id received                 │
│ Attempt mode switch...                 │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Mode switch   │
        │ API error     │
        └───────┬───────┘
                │
                ▼
        ┌───────────────────────────────┐
        │ Critical: Delegation exists   │
        │ but mode not switched         │
        └───────┬───────────────────────┘
                │
                ▼
        ┌───────────────────────────────┐
        │ Retry mode switch (3 attempts)│
        │ If all fail: Show error       │
        │ "Manual fix needed"           │
        └───────────────────────────────┘

Scenario 3: Completion Fails
┌────────────────────────────────────────┐
│ User clicks "Mark Complete"            │
│ Request sent to API...                 │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ API Error     │
        └───────┬───────┘
                │
                ▼
        ┌───────────────────────────────┐
        │ Keep traits & curiosity data  │
        │ Show "Retry" button           │
        │ Data preserved in state       │
        └───────┬───────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ User retries  │
        │ OR cancels    │
        └───────────────┘

Scenario 4: Network Timeout
┌────────────────────────────────────────┐
│ Any API call...                        │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Timeout       │
        │ (>10s)        │
        └───────┬───────┘
                │
                ▼
        ┌───────────────────────────────┐
        │ Show user-friendly message    │
        │ "Connection slow. Retry?"     │
        │ Preserve local state          │
        └───────────────────────────────┘
```

---

## Performance Considerations

```
┌─────────────────────────────────────────────────────────────┐
│                 OPTIMIZATION POINTS                          │
└─────────────────────────────────────────────────────────────┘

1. Curiosity Analysis
   • Cache recent analysis results (5 min TTL)
   • Debounce analysis calls (wait 2s after message)
   • Only analyze if traits changed

2. Active Delegations Widget
   • Poll every 30s (not real-time)
   • Only fetch if widget visible
   • Cache results client-side

3. Mode Switching
   • Optimistic UI updates
   • Switch UI immediately, confirm with API
   • Rollback if API fails

4. History & Stats
   • Lazy load history (only when panel opened)
   • Paginate history (10 items at a time)
   • Cache stats for 1 minute

5. Delegation Records
   • Store as individual JSON files (not one big file)
   • Index by user_id for fast lookup
   • Cap history at 100 transitions per user
```

This comprehensive diagram set provides a complete visual reference for understanding and implementing the delegation system!