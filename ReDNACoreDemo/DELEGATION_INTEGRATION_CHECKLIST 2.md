# Delegation System - Integration Checklist

This checklist guides you through integrating the delegation system into your application. Complete each section in order.

---

## ✅ Prerequisites (Completed)

- [x] Backend API endpoints implemented (9 endpoints)
- [x] Frontend components created (6 components)
- [x] TypeScript type definitions added
- [x] All tests passing (26/26 tests)
- [x] Documentation complete

---

## 🔧 Phase 1: API Integration

### 1.1 Verify API is Running

- [ ] Start the API server
  ```bash
  cd ReDNACoreDemo
  ../.venv/bin/python -m uvicorn core.api:app --reload
  ```

- [ ] Run smoke test to verify all endpoints
  ```bash
  ./scripts/smoke_test_delegation_api.sh
  ```

- [ ] Verify health endpoint: `curl http://localhost:8000/health`

**Expected Result:** All 9 delegation/mode endpoints responding with 200 OK

---

### 1.2 Test API with Script

- [ ] Run the complete flow test
  ```bash
  python scripts/test_delegation_flow.py
  ```

- [ ] Verify output shows:
  - ✅ Curiosity analyzed
  - ✅ Delegation created
  - ✅ Mode switched to specialized coach
  - ✅ Delegation completed
  - ✅ Returned to Head Coach

**Expected Result:** Complete flow executes without errors, delegation marked as completed

---

## 🎨 Phase 2: Frontend Component Integration

### 2.1 Import TypeScript Types

- [ ] Copy `web/src/types/delegation.ts` to your project
- [ ] Verify import works:
  ```typescript
  import { DelegationAPI, CoachModeAPI } from '@/types/delegation'
  ```

**Location:** `web/src/types/delegation.ts`

---

### 2.2 Add Components to Your UI

#### Option A: Import Existing Components

- [ ] Copy all 6 components from `web/src/components/`:
  - `delegation-banner.tsx`
  - `coach-switcher.tsx`
  - `active-delegations-widget.tsx`
  - `delegation-complete-button.tsx`
  - `delegation-return-acknowledgment.tsx`
  - `delegation-history-panel.tsx`

#### Option B: Build Custom Components

- [ ] Use type definitions from `delegation.ts`
- [ ] Follow prop interfaces documented in types
- [ ] Refer to [DELEGATION_SYSTEM_GUIDE.md](DELEGATION_SYSTEM_GUIDE.md) for examples

---

### 2.3 Integrate into Head Coach Chat

**File to modify:** Your Head Coach chat component

- [ ] Add curiosity analysis hook
  ```typescript
  const [delegation, setDelegation] = useState<DelegationRecommendation | null>(null)

  useEffect(() => {
    async function analyzeCuriosity() {
      const response = await DelegationAPI.analyzeCuriosity({
        user_id: userId,
        curiosity_data: currentCuriosityScores,
        tolerance: userTolerance
      })

      if (!isAPIError(response) && response.should_delegate) {
        setDelegation({
          coach: response.recommended_coach,
          // ... map response to DelegationRecommendation
        })
      }
    }

    analyzeCuriosity()
  }, [curiosityData])
  ```

- [ ] Add DelegationBanner component
  ```tsx
  {delegation && (
    <DelegationBanner
      recommendation={delegation}
      onAccept={() => setShowSwitcher(true)}
      onDismiss={() => setDelegation(null)}
    />
  )}
  ```

- [ ] Add CoachSwitcher modal
  ```tsx
  {showSwitcher && (
    <CoachSwitcher
      userId={userId}
      currentCoach="head_coach"
      targetCoach={delegation.coach}
      curiosityTargets={delegation.curiosityTargets}
      onSwitchComplete={(delegationId) => {
        // Navigate to specialized coach
        router.push(`/chat/${delegation.coach}?delegation_id=${delegationId}`)
      }}
      onCancel={() => setShowSwitcher(false)}
    />
  )}
  ```

- [ ] Add return acknowledgment
  ```tsx
  {completedDelegation && (
    <DelegationReturnAcknowledgment
      delegationId={completedDelegation.delegationId}
      coachMode={completedDelegation.coachMode}
      traitsCollected={completedDelegation.traitsCollected}
      curiositySatisfied={completedDelegation.curiositySatisfied}
      notes={completedDelegation.notes}
      onDismiss={() => setCompletedDelegation(null)}
    />
  )}
  ```

**Test:**
- [ ] Delegation banner appears when curiosity is high
- [ ] Clicking "Accept" opens CoachSwitcher modal
- [ ] Modal shows correct transition (HC → Photo Coach)

---

### 2.4 Integrate into Specialized Coach (Photo Coach)

**File to modify:** Your Photo Coach chat component

- [ ] Get delegation ID from URL/props
  ```typescript
  const searchParams = useSearchParams()
  const delegationId = searchParams.get('delegation_id')
  ```

- [ ] Track trait collection
  ```typescript
  const [traitsCollected, setTraitsCollected] = useState<string[]>([])
  const [curiosityBefore, setCuriosityBefore] = useState<Record<string, number>>({})
  const [curiosityAfter, setCuriosityAfter] = useState<Record<string, number>>({})

  // When photo is analyzed
  function handlePhotoAnalyzed(traits) {
    setTraitsCollected(Object.keys(traits))
    // Update curiosity before/after
  }
  ```

- [ ] Add DelegationCompleteButton
  ```tsx
  {traitsCollected.length > 0 && delegationId && (
    <div className="sticky bottom-0 p-4 border-t bg-white">
      <DelegationCompleteButton
        userId={userId}
        delegationId={delegationId}
        traitsCollected={traitsCollected}
        curiosityBefore={curiosityBefore}
        curiosityAfter={curiosityAfter}
        notes={`Analyzed ${traitsCollected.length} visual traits`}
        variant="success"
        onComplete={(summary) => {
          // Navigate back to Head Coach
          router.push(`/chat/head_coach?delegation_complete=${delegationId}`)
        }}
      />
    </div>
  )}
  ```

**Test:**
- [ ] Button appears after traits are collected
- [ ] Button shows correct preview stats
- [ ] Clicking button completes delegation
- [ ] User is redirected to Head Coach
- [ ] Acknowledgment appears in Head Coach

---

### 2.5 Add Sidebar Widget (Optional)

**File to modify:** Your app sidebar/layout component

- [ ] Add ActiveDelegationsWidget
  ```tsx
  <aside className="w-64 border-l">
    <ActiveDelegationsWidget
      userId={userId}
      onDelegationClick={(delegationId) => {
        // Navigate to delegation details
      }}
    />
  </aside>
  ```

**Test:**
- [ ] Widget shows active delegations
- [ ] Polls every 30 seconds
- [ ] Shows progress bars correctly
- [ ] Click handlers work

---

## 🧪 Phase 3: Testing

### 3.1 Unit Tests (Backend)

- [ ] Run coach mode switching tests
  ```bash
  pytest tests/test_coach_mode_switching.py -v
  ```
  **Expected:** 13/13 passing

---

### 3.2 Integration Tests (Backend)

- [ ] Run delegation mode integration tests
  ```bash
  pytest tests/test_delegation_mode_integration.py -v
  ```
  **Expected:** 8/8 passing

---

### 3.3 End-to-End Lifecycle Tests (Backend)

- [ ] Run delegation lifecycle tests
  ```bash
  pytest tests/test_delegation_lifecycle.py -v
  ```
  **Expected:** 5/5 passing

---

### 3.4 Run All Tests

- [ ] Run complete test suite
  ```bash
  pytest tests/test_*delegation*.py tests/test_coach_mode*.py -v
  ```
  **Expected:** 26/26 passing

---

### 3.5 Manual UI Testing

**Test Case 1: Complete Flow (Photo Coach)**

- [ ] Start in Head Coach with high PaDNA curiosity (85%+)
- [ ] Verify delegation banner appears
- [ ] Click "Accept"
- [ ] Verify CoachSwitcher modal opens
- [ ] Verify mode switches to Photo Coach
- [ ] Upload a photo in Photo Coach
- [ ] Verify traits are extracted
- [ ] Click "Mark Complete"
- [ ] Verify completion button shows celebration
- [ ] Verify redirect to Head Coach
- [ ] Verify acknowledgment appears
- [ ] Verify curiosity scores reduced in profile

**Test Case 2: Dismiss Delegation**

- [ ] Delegation banner appears
- [ ] Click "Dismiss"
- [ ] Verify banner disappears
- [ ] Verify no delegation created
- [ ] Verify Head Coach continues normally

**Test Case 3: Multiple Delegations**

- [ ] Complete one delegation (Photo Coach)
- [ ] Return to Head Coach
- [ ] Trigger another delegation (Relationship Coach)
- [ ] Complete second delegation
- [ ] Verify both in delegation history
- [ ] Verify mode stats show multiple transitions

---

## 📊 Phase 4: Monitoring & Analytics

### 4.1 Add Logging

- [ ] Log delegation creations
- [ ] Log mode switches
- [ ] Log delegation completions
- [ ] Log curiosity satisfaction scores

---

### 4.2 Add Analytics Events

- [ ] Track delegation acceptance rate
- [ ] Track delegation completion rate
- [ ] Track average satisfaction scores
- [ ] Track time spent in each coach mode

**Recommended Events:**
- `delegation_recommended`
- `delegation_accepted`
- `delegation_dismissed`
- `delegation_completed`
- `mode_switched`

---

## 🚀 Phase 5: Production Readiness

### 5.1 Error Handling

- [ ] Add error boundaries around delegation components
- [ ] Handle API timeout gracefully (show retry button)
- [ ] Handle network errors (offline mode?)
- [ ] Add sentry/error tracking for delegation failures

---

### 5.2 Performance Optimization

- [ ] Debounce curiosity analysis (2s after user message)
- [ ] Cache delegation recommendations (5 min TTL)
- [ ] Lazy load DelegationHistoryPanel
- [ ] Optimize ActiveDelegationsWidget polling (only when visible)

---

### 5.3 User Experience Polish

- [ ] Add loading skeletons for delegation components
- [ ] Add smooth transitions between coaches
- [ ] Add haptic feedback on completion (mobile)
- [ ] Add sound effects for high satisfaction (optional)
- [ ] Ensure accessibility (keyboard navigation, screen readers)

---

### 5.4 Documentation for Team

- [ ] Add delegation system to onboarding docs
- [ ] Document when/how to trigger delegations
- [ ] Document how to add new specialized coaches
- [ ] Create troubleshooting guide for common issues

---

## 🔮 Phase 6: Future Enhancements (Optional)

### 6.1 Advanced Features

- [ ] Multi-delegation: Allow multiple active delegations
- [ ] Delegation cancellation: User can cancel before completion
- [ ] Partial completion: Mark traits collected incrementally
- [ ] Coach suggestions: Specialized coaches suggest other coaches
- [ ] Delegation scheduling: Schedule delegation for later
- [ ] Delegation templates: Pre-defined curiosity target sets

---

### 6.2 CReDNA Integration

- [ ] Add `credna_profile_id` to delegation records
- [ ] Load CReDNA personality for specialized coaches
- [ ] Apply personality overlays to coach prompts
- [ ] Track delegation performance per CReDNA profile

---

## 📋 Final Checklist

Before marking delegation system as "production ready":

- [ ] All 26 tests passing
- [ ] API smoke test passes
- [ ] Manual testing complete (all 3 test cases)
- [ ] Error handling in place
- [ ] Analytics events tracked
- [ ] Performance optimizations applied
- [ ] Documentation complete
- [ ] Team trained on delegation system

---

## 📞 Support

If you encounter issues during integration:

1. Check [DELEGATION_SYSTEM_GUIDE.md](DELEGATION_SYSTEM_GUIDE.md) for examples
2. Review [DELEGATION_FLOW_DIAGRAM.md](DELEGATION_FLOW_DIAGRAM.md) for visual reference
3. Run `pytest tests/test_*delegation*.py -v` to verify backend
4. Run `./scripts/smoke_test_delegation_api.sh` to verify API
5. Check browser console for frontend errors
6. Review delegation records in `data/users/{user_id}/delegations/`

---

## 🎯 Success Criteria

The delegation system is successfully integrated when:

✅ Users see delegation recommendations at appropriate times
✅ Users can accept and switch to specialized coaches seamlessly
✅ Specialized coaches collect traits and update curiosity
✅ Completion flow returns users to Head Coach with acknowledgment
✅ All delegation data is persisted and retrievable
✅ No errors in console or logs during normal operation
✅ Performance is smooth (no lag or jank)
✅ User feedback is positive ("this feels natural and helpful")

---

**Current Status:** All implementation complete, ready for integration

**Estimated Integration Time:** 4-8 hours for full integration (depends on existing codebase complexity)

**Last Updated:** October 6, 2025
