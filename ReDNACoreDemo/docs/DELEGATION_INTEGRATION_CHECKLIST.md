# Delegation System - Integration Checklist

This checklist guides you through integrating the delegation system into your application.

## ✅ Prerequisites (All Complete)

- [x] Backend API endpoints (9 endpoints)
- [x] Coach mode manager (280 lines)
- [x] Frontend components (6 components)
- [x] TypeScript types (500+ lines)
- [x] Test suite (26/26 passing)
- [x] Documentation (800+ lines)

---

## 🔧 Integration Steps

### Phase 1: Head Coach - Delegation Triggers

**Goal:** Head Coach can detect high curiosity and recommend delegation.

#### 1.1 Add Curiosity Analysis to Head Coach

**File to modify:** Your Head Coach conversation handler

```typescript
// Example: components/head-coach-chat.tsx

import { DelegationAPI, isAPIError } from "@/types/delegation"

async function analyzeForDelegation(
  userId: string,
  curiosityData: Record<string, number>
) {
  const response = await DelegationAPI.analyzeCuriosity({
    user_id: userId,
    curiosity_data: curiosityData,
    tolerance: userTolerance, // From user settings
  })

  if (isAPIError(response)) {
    console.error("Delegation analysis failed:", response.message)
    return null
  }

  return response.should_delegate ? response : null
}
```

**Checklist:**
- [ ] Import delegation types and API client
- [ ] Add `analyzeForDelegation` function
- [ ] Call after each HC message that updates curiosity
- [ ] Store recommendation in component state

---

#### 1.2 Display Delegation Banner

**File to modify:** Your Head Coach UI

```typescript
import { DelegationBanner } from "@/components/delegation-banner"

function HeadCoachChat() {
  const [delegationRec, setDelegationRec] = useState(null)
  const [showSwitcher, setShowSwitcher] = useState(false)

  return (
    <div>
      {/* Existing chat UI */}
      <ChatTranscript messages={messages} />

      {/* Add delegation banner */}
      {delegationRec && (
        <DelegationBanner
          recommendation={{
            coach: delegationRec.recommended_coach,
            coachName: getCoachName(delegationRec.recommended_coach),
            coachEmoji: getCoachEmoji(delegationRec.recommended_coach),
            itemCount: delegationRec.priority_items.length,
            priorityScore: Math.max(...delegationRec.priority_items.map(i => i.curiosity / 10)),
            curiosityTargets: delegationRec.priority_items.map(i => i.path),
          }}
          onAccept={() => setShowSwitcher(true)}
          onDismiss={() => setDelegationRec(null)}
        />
      )}
    </div>
  )
}
```

**Checklist:**
- [ ] Import `DelegationBanner` component
- [ ] Add state for delegation recommendation
- [ ] Add state for showing coach switcher
- [ ] Render banner conditionally when recommendation exists
- [ ] Wire up onAccept to show switcher modal
- [ ] Wire up onDismiss to clear recommendation

---

#### 1.3 Add Coach Switcher Modal

**File to modify:** Your Head Coach UI

```typescript
import { CoachSwitcher } from "@/components/coach-switcher"
import { useRouter } from "next/navigation"

function HeadCoachChat() {
  const router = useRouter()

  return (
    <div>
      {/* Existing UI */}

      {/* Add coach switcher modal */}
      {showSwitcher && delegationRec && (
        <CoachSwitcher
          userId={userId}
          currentCoach="head_coach"
          targetCoach={delegationRec.recommended_coach}
          curiosityTargets={delegationRec.priority_items.map(i => i.path)}
          onSwitchComplete={(delegationId) => {
            console.log("Delegation created:", delegationId)
            setShowSwitcher(false)
            // Navigate to specialized coach
            router.push(`/coach/${delegationRec.recommended_coach}?delegation=${delegationId}`)
          }}
          onCancel={() => setShowSwitcher(false)}
        />
      )}
    </div>
  )
}
```

**Checklist:**
- [ ] Import `CoachSwitcher` component
- [ ] Import router for navigation
- [ ] Render switcher modal conditionally
- [ ] Pass user ID and coach details
- [ ] Wire up onSwitchComplete to navigate to specialized coach
- [ ] Wire up onCancel to close modal

---

### Phase 2: Specialized Coaches - Trait Collection

**Goal:** Photo Coach and Relationship Coach can collect traits within delegation context.

#### 2.1 Create Photo Coach Page/Component

**File to create:** `pages/coach/photo-coach.tsx` or similar

```typescript
import { DelegationCompleteButton } from "@/components/delegation-complete-button"
import { useSearchParams, useRouter } from "next/navigation"
import { useState, useEffect } from "react"

export default function PhotoCoachPage() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const userId = searchParams.get("user")
  const delegationId = searchParams.get("delegation")

  const [traitsCollected, setTraitsCollected] = useState<string[]>([])
  const [curiosityBefore, setCuriosityBefore] = useState<Record<string, number>>({})
  const [curiosityAfter, setCuriosityAfter] = useState<Record<string, number>>({})

  // Load delegation context on mount
  useEffect(() => {
    if (delegationId) {
      loadDelegationContext()
    }
  }, [delegationId])

  async function loadDelegationContext() {
    const response = await fetch(`/api/delegation/${userId}/status/${delegationId}`)
    const data = await response.json()

    // Initialize curiosity_before from delegation targets
    const before = {}
    for (const target of data.curiosity_targets) {
      before[target] = getCuriosityValue(target) // Fetch from your data
    }
    setCuriosityBefore(before)
  }

  // Called when photo is analyzed
  function handlePhotoAnalyzed(extractedTraits: Record<string, any>) {
    const traitPaths = Object.keys(extractedTraits)
    setTraitsCollected(traitPaths)

    // Update curiosity after values
    const after = {}
    for (const trait of traitPaths) {
      after[trait] = calculateNewCuriosity(trait, extractedTraits[trait])
    }
    setCuriosityAfter(after)
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="p-4 border-b">
        <h1>📸 Photo Coach</h1>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-auto p-4">
        {/* Your photo coach chat UI */}
        <PhotoAnalysisInterface onAnalyzed={handlePhotoAnalyzed} />
      </div>

      {/* Completion Button (sticky footer) */}
      {traitsCollected.length > 0 && (
        <div className="p-4 border-t bg-white">
          <DelegationCompleteButton
            userId={userId}
            delegationId={delegationId}
            traitsCollected={traitsCollected}
            curiosityBefore={curiosityBefore}
            curiosityAfter={curiosityAfter}
            notes={`Analyzed photo and collected ${traitsCollected.length} visual traits`}
            variant="success"
            onComplete={(summary) => {
              console.log("Delegation complete:", summary)
              // Redirect back to Head Coach
              router.push(`/coach/head-coach?delegation_complete=${delegationId}`)
            }}
          />
        </div>
      )}
    </div>
  )
}
```

**Checklist:**
- [ ] Create Photo Coach page/component
- [ ] Parse delegation ID from URL params
- [ ] Load delegation context on mount
- [ ] Track traits collected during conversation
- [ ] Track before/after curiosity values
- [ ] Import and render `DelegationCompleteButton`
- [ ] Wire up completion callback to navigate back to HC

---

#### 2.2 Create Relationship Coach Page/Component

**File to create:** `pages/coach/relationship-coach.tsx` or similar

```typescript
// Similar structure to Photo Coach
// Key differences:
// - RC collects ReDNA, EmDNA traits instead of PaDNA
// - May use conversation turns instead of photo upload
// - Same completion flow with DelegationCompleteButton
```

**Checklist:**
- [ ] Create Relationship Coach page/component
- [ ] Parse delegation ID from URL params
- [ ] Load delegation context on mount
- [ ] Track traits from conversation (ReDNA, EmDNA)
- [ ] Track before/after curiosity values
- [ ] Import and render `DelegationCompleteButton`
- [ ] Wire up completion callback

---

### Phase 3: Head Coach - Return Flow

**Goal:** Head Coach acknowledges completed delegations with context.

#### 3.1 Detect Delegation Completion

**File to modify:** Your Head Coach component

```typescript
import { DelegationReturnAcknowledgment } from "@/components/delegation-return-acknowledgment"
import { useSearchParams } from "next/navigation"

function HeadCoachChat() {
  const searchParams = useSearchParams()
  const [completedDelegation, setCompletedDelegation] = useState(null)

  useEffect(() => {
    // Check if returning from completed delegation
    const delegationId = searchParams.get("delegation_complete")
    if (delegationId) {
      loadDelegationResults(delegationId)
    }
  }, [searchParams])

  async function loadDelegationResults(delegationId: string) {
    const response = await fetch(`/api/delegation/${userId}/status/${delegationId}`)
    const data = await response.json()

    setCompletedDelegation({
      delegationId: data.status.delegation_id,
      coachMode: data.status.coach,
      traitsCollected: data.status.traits_collected,
      curiositySatisfied: data.status.curiosity_satisfied,
      notes: data.status.notes,
    })
  }

  return (
    <div>
      {/* Show acknowledgment at top of chat */}
      {completedDelegation && (
        <DelegationReturnAcknowledgment
          {...completedDelegation}
          onDismiss={() => {
            setCompletedDelegation(null)
            // Clear URL parameter
            window.history.replaceState({}, "", "/coach/head-coach")
          }}
        />
      )}

      {/* Regular chat UI */}
      <ChatTranscript messages={messages} />
    </div>
  )
}
```

**Checklist:**
- [ ] Import `DelegationReturnAcknowledgment`
- [ ] Add state for completed delegation
- [ ] Check URL params on mount for `delegation_complete`
- [ ] Load delegation results if param exists
- [ ] Render acknowledgment component
- [ ] Wire up onDismiss to clear state and URL param

---

#### 3.2 Update Head Coach Context with Results

**File to modify:** Your Head Coach LLM prompt builder

```typescript
function buildHeadCoachPrompt(
  basePrompt: string,
  userContext: any,
  recentDelegation?: any
): string {
  let prompt = basePrompt

  // Add delegation completion context
  if (recentDelegation && recentDelegation.status === "completed") {
    prompt += `

RECENT DELEGATION COMPLETE:
- Coach: ${recentDelegation.coach}
- Traits collected: ${recentDelegation.traits_collected.join(", ")}
- Curiosity satisfied: ${Math.round(recentDelegation.curiosity_satisfied * 100)}%
- Notes: ${recentDelegation.notes}

Acknowledge this delegation completion naturally in your next response.
Reference the specific traits collected and express appropriate enthusiasm
based on the satisfaction level.
`
  }

  return prompt
}
```

**Checklist:**
- [ ] Add delegation context parameter to prompt builder
- [ ] Check for recent completed delegations
- [ ] Inject completion details into system prompt
- [ ] Instruct HC to acknowledge naturally
- [ ] Test HC responses reference delegation results

---

### Phase 4: Sidebar & History

**Goal:** Users can monitor active delegations and view history.

#### 4.1 Add Active Delegations Widget

**File to modify:** Your sidebar/layout component

```typescript
import { ActiveDelegationsWidget } from "@/components/active-delegations-widget"

function AppSidebar({ userId }: { userId: string }) {
  return (
    <aside className="w-64 border-r p-4">
      {/* Existing sidebar content */}

      {/* Add active delegations widget */}
      <div className="mt-4">
        <ActiveDelegationsWidget
          userId={userId}
          onDelegationClick={(delegationId) => {
            // Navigate to delegation details or continue conversation
            router.push(`/coach/current?delegation=${delegationId}`)
          }}
        />
      </div>
    </aside>
  )
}
```

**Checklist:**
- [ ] Import `ActiveDelegationsWidget`
- [ ] Add to sidebar in appropriate location
- [ ] Pass user ID
- [ ] Wire up click handler for navigation
- [ ] Test real-time polling updates

---

#### 4.2 Add Delegation History Panel

**File to create:** Add to settings or profile page

```typescript
import { DelegationHistoryPanel } from "@/components/delegation-history-panel"

function UserSettingsPage() {
  const [showHistory, setShowHistory] = useState(false)

  return (
    <div>
      {/* Existing settings */}

      {/* Delegation history button */}
      <button onClick={() => setShowHistory(true)}>
        View Delegation History
      </button>

      {/* History panel modal/drawer */}
      {showHistory && (
        <DelegationHistoryPanel
          userId={userId}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  )
}
```

**Checklist:**
- [ ] Import `DelegationHistoryPanel`
- [ ] Add trigger button in settings/profile
- [ ] Render panel as modal or drawer
- [ ] Wire up close handler
- [ ] Test filtering and sorting

---

## 🧪 Testing Your Integration

### Automated Tests

```bash
# Run all delegation tests
pytest tests/test_*delegation*.py -v

# Run smoke test
./scripts/smoke_test_delegation_api.sh

# Run flow test
python scripts/test_delegation_flow.py
```

**Checklist:**
- [ ] All pytest tests pass (26/26)
- [ ] Smoke test passes (9 endpoints)
- [ ] Flow test completes successfully

---

### Manual Testing

#### Test 1: Complete Photo Coach Delegation

1. [ ] Start in Head Coach mode
2. [ ] Trigger high curiosity (manually set PaDNA traits to 85+)
3. [ ] Verify delegation banner appears
4. [ ] Click "Accept" and verify switcher modal
5. [ ] Verify delegation created and mode switched to photo
6. [ ] Upload photo in Photo Coach
7. [ ] Verify traits extracted and curiosity updated
8. [ ] Click "Mark Complete & Return"
9. [ ] Verify auto-return to Head Coach
10. [ ] Verify acknowledgment appears with correct stats
11. [ ] Verify delegation marked as "completed" in API

---

#### Test 2: Relationship Coach Delegation

1. [ ] Start in Head Coach mode
2. [ ] Trigger high curiosity (set ReDNA traits to 70+)
3. [ ] Accept delegation to Relationship Coach
4. [ ] Have conversation about relationships
5. [ ] Collect 2-3 ReDNA/EmDNA traits
6. [ ] Complete delegation
7. [ ] Verify return to Head Coach with acknowledgment

---

#### Test 3: Delegation Without Auto-Return

1. [ ] Accept delegation to Photo Coach
2. [ ] Collect traits
3. [ ] Complete with `auto_return: false` (modify button)
4. [ ] Verify stays in Photo Coach mode
5. [ ] Manually switch back to Head Coach
6. [ ] Verify no acknowledgment shown (no URL param)

---

#### Test 4: Multiple Sequential Delegations

1. [ ] Complete Photo Coach delegation
2. [ ] Return to Head Coach
3. [ ] Immediately trigger RC delegation
4. [ ] Complete RC delegation
5. [ ] Verify mode history shows 4 transitions
6. [ ] Verify both delegations marked complete

---

### Edge Cases

#### Test 5: Network Errors

1. [ ] Stop API server
2. [ ] Try to create delegation
3. [ ] Verify error message shown
4. [ ] Verify stays in Head Coach mode
5. [ ] Restart API
6. [ ] Retry delegation - should work

---

#### Test 6: Incomplete Data

1. [ ] Accept delegation
2. [ ] Try to complete with 0 traits collected
3. [ ] Verify button disabled or shows warning
4. [ ] Collect at least 1 trait
5. [ ] Verify button enabled

---

## 📊 Integration Metrics

Track these metrics to verify successful integration:

### Backend Metrics

- [ ] Delegation creation success rate > 99%
- [ ] Mode switch success rate > 99%
- [ ] Completion success rate > 99%
- [ ] Average delegation duration < 5 minutes
- [ ] Average traits collected per delegation > 2

### Frontend Metrics

- [ ] Banner shown within 2 seconds of high curiosity
- [ ] Switcher modal opens in < 500ms
- [ ] Completion button shows preview accurately
- [ ] Acknowledgment renders immediately on return
- [ ] Active delegations widget polls successfully every 30s

### User Experience Metrics

- [ ] User accepts delegation recommendation > 60% of time
- [ ] Users complete delegations > 90% of time
- [ ] Average curiosity satisfaction > 70%
- [ ] No user-reported confusion about mode switches

---

## 🐛 Troubleshooting

### Issue: Banner doesn't show

**Possible causes:**
- Curiosity values not high enough (need ≥60)
- Analysis endpoint not called
- Tolerance setting too high

**Debug:**
```typescript
console.log("Curiosity data:", curiosityData)
console.log("Analysis result:", analysisResult)
```

---

### Issue: Mode doesn't switch

**Possible causes:**
- Second API call not made (check CoachSwitcher)
- Invalid target mode
- Network error

**Debug:**
```bash
# Check API logs
tail -f api.log | grep "coach-mode"

# Verify mode file created
cat data/users/{user_id}/coach_mode.json
```

---

### Issue: Doesn't return to Head Coach

**Possible causes:**
- `auto_return: false` in completion request
- Completion endpoint failed
- Frontend not navigating back

**Debug:**
```typescript
console.log("Completion response:", completionData)
console.log("Mode switch:", completionData.mode_switch)
```

---

### Issue: Acknowledgment doesn't show

**Possible causes:**
- URL parameter not set
- Delegation status fetch failed
- Component not checking URL params

**Debug:**
```typescript
console.log("Search params:", searchParams.get("delegation_complete"))
console.log("Delegation results:", completedDelegation)
```

---

## ✅ Integration Complete Checklist

### Phase 1: Head Coach
- [ ] Curiosity analysis integrated
- [ ] Delegation banner shows on high curiosity
- [ ] Coach switcher modal functional
- [ ] Navigation to specialized coaches works

### Phase 2: Specialized Coaches
- [ ] Photo Coach page created
- [ ] Relationship Coach page created
- [ ] Delegation context loaded
- [ ] Traits tracked during conversation
- [ ] Completion button integrated
- [ ] Auto-return functional

### Phase 3: Return Flow
- [ ] Completion detection works
- [ ] Acknowledgment shows with correct data
- [ ] HC prompt updated with delegation context
- [ ] Natural acknowledgment in HC responses

### Phase 4: Sidebar & History
- [ ] Active delegations widget in sidebar
- [ ] Real-time polling works
- [ ] History panel accessible
- [ ] History filtering/sorting works

### Testing
- [ ] All automated tests pass
- [ ] Manual test scenarios complete
- [ ] Edge cases handled gracefully
- [ ] Metrics tracked and healthy

---

## 🚀 Post-Integration

### Documentation Updates

- [ ] Update README with delegation features
- [ ] Add screenshots to user guide
- [ ] Update API documentation
- [ ] Create video walkthrough (optional)

### Monitoring

- [ ] Add delegation metrics to dashboard
- [ ] Set up alerts for high failure rates
- [ ] Log delegation events for analytics
- [ ] Track user satisfaction trends

### Future Enhancements

- [ ] Multi-delegation support
- [ ] Delegation scheduling
- [ ] Coach suggestions from specialized coaches
- [ ] Partial completion tracking
- [ ] Delegation templates
- [ ] CReDNA integration (when ready)

---

**Estimated Integration Time:** 2-4 hours for experienced developers

**Support:** Refer to [DELEGATION_SYSTEM_GUIDE.md](DELEGATION_SYSTEM_GUIDE.md) for detailed API and component documentation.
