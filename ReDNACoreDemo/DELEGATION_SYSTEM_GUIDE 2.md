# Coach Delegation System - Complete Integration Guide

## Overview

The Coach Delegation System enables the Head Coach to orchestrate specialized coaches (Photo Coach, Relationship Coach) for curiosity-driven trait exploration. This guide covers the complete implementation across three phases.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [API Endpoints](#api-endpoints)
3. [Frontend Components](#frontend-components)
4. [Complete Flow](#complete-flow)
5. [Integration Examples](#integration-examples)
6. [Testing](#testing)

---

## Architecture Overview

### Key Concepts

- **Coach Modes**: Functional specializations (head_coach, photo, relationship)
- **Delegation**: Head Coach assigns curiosity targets to specialized coach
- **Two-Step Flow**: Create delegation → Switch coach mode
- **Auto-Return**: Specialized coach completes delegation → returns to Head Coach
- **Curiosity Satisfaction**: Calculated as `(before - after) / before` for collected traits

### Data Flow

```
┌─────────────┐
│ Head Coach  │ Detects high curiosity (>60)
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ DelegationBanner    │ User accepts recommendation
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ CoachSwitcher       │ 1. Create delegation
└──────┬──────────────┘ 2. Switch to specialized mode
       │
       ▼
┌─────────────────────┐
│ Specialized Coach   │ Collects traits with delegation context
└──────┬──────────────┘
       │
       ▼
┌──────────────────────────┐
│ DelegationCompleteButton │ User marks complete
└──────┬───────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Auto-return to Head Coach   │ With results & satisfaction
└──────┬──────────────────────┘
       │
       ▼
┌───────────────────────────────────┐
│ DelegationReturnAcknowledgment   │ Celebration & summary
└───────────────────────────────────┘
```

---

## API Endpoints

### Base URL

```
http://localhost:8000
```

### 1. Analyze Curiosity for Delegation

**POST** `/delegation/analyze`

Analyzes which traits have high curiosity and recommends a coach.

**Request:**
```json
{
  "user_id": "user123",
  "curiosity_data": {
    "PaDNA.HairDNA.Color": 85.0,
    "PaDNA.EyeDNA.Color": 92.0,
    "ReDNA.AttachmentStyle.Type": 78.0
  },
  "tolerance": 0.7
}
```

**Response:**
```json
{
  "ok": true,
  "should_delegate": true,
  "recommended_coach": "photo_coach",
  "priority_items": [
    {
      "path": "PaDNA.EyeDNA.Color",
      "curiosity": 92.0,
      "namespace": "PaDNA"
    }
  ],
  "message": "I think Photo Coach could help explore these areas."
}
```

---

### 2. Create Delegation

**POST** `/delegation/create`

Creates a delegation record and returns delegation ID.

**Request:**
```json
{
  "user_id": "user123",
  "coach_id": "photo_coach",
  "curiosity_targets": [
    "PaDNA.HairDNA.Color",
    "PaDNA.EyeDNA.Color"
  ],
  "context": {
    "delegation_reason": "user_accepted_recommendation",
    "priority": 8.5
  }
}
```

**Response:**
```json
{
  "ok": true,
  "delegation": {
    "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
    "coach": "photo_coach",
    "status": "pending",
    "curiosity_targets": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
    "created_at": "2025-10-06T12:34:56Z"
  },
  "message": "I think Photo Coach could help explore these areas. Want to chat with them?"
}
```

---

### 3. Switch Coach Mode

**POST** `/users/{user_id}/coach-mode`

Switches user's active coach mode with delegation context.

**Request:**
```json
{
  "target_mode": "photo",
  "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {
    "curiosity_targets": ["PaDNA.HairDNA.Color"]
  }
}
```

**Response:**
```json
{
  "ok": true,
  "success": true,
  "previous_mode": "head_coach",
  "new_mode": "photo",
  "mode_info": {
    "display_name": "Photo Coach",
    "emoji": "📸",
    "description": "Visual trait specialist",
    "namespaces": ["PaDNA"]
  },
  "message": "Switched to Photo Coach mode"
}
```

---

### 4. Get Active Coach Mode

**GET** `/users/{user_id}/coach-mode`

Returns user's current active coach mode.

**Response:**
```json
{
  "ok": true,
  "active_mode": "photo",
  "mode_info": {
    "display_name": "Photo Coach",
    "emoji": "📸",
    "description": "Visual trait specialist",
    "namespaces": ["PaDNA"]
  }
}
```

---

### 5. Complete Delegation

**POST** `/delegation/{user_id}/complete/{delegation_id}`

Marks delegation complete, calculates satisfaction, and auto-returns to Head Coach.

**Request:**
```json
{
  "traits_collected": [
    "PaDNA.HairDNA.Color",
    "PaDNA.EyeDNA.Color"
  ],
  "curiosity_before": {
    "PaDNA.HairDNA.Color": 85.0,
    "PaDNA.EyeDNA.Color": 92.0
  },
  "curiosity_after": {
    "PaDNA.HairDNA.Color": 12.0,
    "PaDNA.EyeDNA.Color": 8.0
  },
  "notes": "Analyzed user photo, collected hair and eye traits",
  "auto_return": true
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Delegation completed successfully",
  "delegation_summary": {
    "traits_collected_count": 2,
    "curiosity_satisfied": 0.887,
    "notes": "Analyzed user photo, collected hair and eye traits"
  },
  "mode_switch": {
    "success": true,
    "previous_mode": "photo",
    "new_mode": "head_coach",
    "message": "Returned to Head Coach mode"
  }
}
```

---

### 6. Get Delegation Status

**GET** `/delegation/{user_id}/status/{delegation_id}`

Returns current status of a delegation.

**Response:**
```json
{
  "ok": true,
  "status": {
    "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
    "coach": "photo_coach",
    "status": "completed",
    "traits_collected": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
    "curiosity_satisfied": 0.887,
    "timestamp": "2025-10-06T12:45:00Z",
    "notes": "Analyzed user photo"
  }
}
```

---

### 7. Get Active Delegations

**GET** `/delegation/{user_id}/active`

Returns all active (pending/in-progress) delegations for a user.

**Response:**
```json
{
  "ok": true,
  "count": 1,
  "delegations": [
    {
      "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
      "coach": "photo_coach",
      "status": "active",
      "traits_collected": ["PaDNA.HairDNA.Color"],
      "curiosity_satisfied": 0.5,
      "timestamp": "2025-10-06T12:34:56Z"
    }
  ]
}
```

---

### 8. Get Mode History

**GET** `/users/{user_id}/coach-mode/history?limit=10`

Returns user's coach mode switching history.

**Response:**
```json
{
  "ok": true,
  "history": [
    {
      "from_mode": "head_coach",
      "to_mode": "photo",
      "timestamp": "2025-10-06T12:34:56Z",
      "context": {
        "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
        "reason": "delegation"
      }
    },
    {
      "from_mode": "photo",
      "to_mode": "head_coach",
      "timestamp": "2025-10-06T12:45:00Z",
      "context": {
        "delegation_id": "550e8400-e29b-41d4-a716-446655440000",
        "reason": "delegation_complete",
        "curiosity_satisfied": 0.887
      }
    }
  ]
}
```

---

### 9. Get Mode Statistics

**GET** `/users/{user_id}/coach-mode/stats`

Returns statistics about user's coach mode usage.

**Response:**
```json
{
  "ok": true,
  "stats": {
    "total_transitions": 15,
    "mode_counts": {
      "head_coach": 8,
      "photo": 5,
      "relationship": 2
    },
    "current_mode": "head_coach",
    "most_used_mode": "head_coach"
  }
}
```

---

## Frontend Components

### 1. DelegationBanner

Shows when Head Coach recommends delegation.

**Location:** `web/src/components/delegation-banner.tsx`

**Usage:**
```tsx
import { DelegationBanner } from "@/components/delegation-banner"

<DelegationBanner
  recommendation={{
    coach: "photo_coach",
    coachName: "Photo Coach",
    coachEmoji: "📸",
    itemCount: 3,
    priorityScore: 8.5,
    curiosityTargets: ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]
  }}
  onAccept={() => {
    // Handle delegation acceptance
    // Show CoachSwitcher modal
  }}
  onDismiss={() => {
    // User declined delegation
  }}
/>
```

**Features:**
- Orange gradient with priority bar
- Coach emoji and item count
- Sparkle animations
- Accept/dismiss actions

---

### 2. CoachSwitcher

Modal for switching between coaches with delegation context.

**Location:** `web/src/components/coach-switcher.tsx`

**Usage:**
```tsx
import { CoachSwitcher } from "@/components/coach-switcher"

<CoachSwitcher
  userId="user123"
  currentCoach="head_coach"
  targetCoach="photo_coach"
  curiosityTargets={["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]}
  onSwitchComplete={(delegationId) => {
    console.log("Switched with delegation:", delegationId)
    // Update UI to show Photo Coach interface
  }}
  onCancel={() => {
    // User cancelled switch
  }}
/>
```

**Features:**
- Two-step API flow (create delegation → switch mode)
- Visual transition animation
- Error handling with retry
- Coach emoji and tagline display

---

### 3. ActiveDelegationsWidget

Sidebar widget showing active delegations.

**Location:** `web/src/components/active-delegations-widget.tsx`

**Usage:**
```tsx
import { ActiveDelegationsWidget } from "@/components/active-delegations-widget"

<ActiveDelegationsWidget
  userId="user123"
  onDelegationClick={(delegationId) => {
    // Navigate to delegation details or continue conversation
  }}
/>
```

**Features:**
- Real-time polling (30s interval)
- Status icons (⏳ pending, 🔄 active, ✅ completed)
- Curiosity satisfaction progress bars
- Click to view details

---

### 4. DelegationCompleteButton

Button for specialized coaches to mark delegation complete.

**Location:** `web/src/components/delegation-complete-button.tsx`

**Usage:**
```tsx
import { DelegationCompleteButton } from "@/components/delegation-complete-button"

<DelegationCompleteButton
  userId="user123"
  delegationId="550e8400-e29b-41d4-a716-446655440000"
  traitsCollected={["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]}
  curiosityBefore={{
    "PaDNA.HairDNA.Color": 85.0,
    "PaDNA.EyeDNA.Color": 92.0
  }}
  curiosityAfter={{
    "PaDNA.HairDNA.Color": 12.0,
    "PaDNA.EyeDNA.Color": 8.0
  }}
  notes="Analyzed user photo, collected hair and eye traits"
  variant="success"
  onComplete={(summary) => {
    console.log("Delegation complete:", summary)
    // Navigate back to Head Coach or show acknowledgment
  }}
/>
```

**Props:**
- `variant`: "default" | "success" | "celebration"
- Auto-calculates curiosity satisfaction
- Preview stats before completion
- Celebration UI for high satisfaction (≥70%)

---

### 5. DelegationReturnAcknowledgment

Head Coach acknowledgment when delegation completes.

**Location:** `web/src/components/delegation-return-acknowledgment.tsx`

**Usage:**
```tsx
import { DelegationReturnAcknowledgment } from "@/components/delegation-return-acknowledgment"

<DelegationReturnAcknowledgment
  delegationId="550e8400-e29b-41d4-a716-446655440000"
  coachMode="photo_coach"
  traitsCollected={["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]}
  curiositySatisfied={0.887}
  notes="Analyzed user photo, collected hair and eye traits"
  timestamp="2025-10-06T12:45:00Z"
  onDismiss={() => {
    // User dismissed acknowledgment
  }}
/>
```

**Features:**
- Tiered messaging based on satisfaction:
  - 80%+: "Fantastic work!" with award icon
  - 60-79%: "Great progress!"
  - 40-59%: "Good session!"
  - <40%: "Welcome back!"
- Traits grouped by namespace
- Sparkle animations for excellent results

---

### 6. DelegationHistoryPanel

Complete delegation history view.

**Location:** `web/src/components/delegation-history-panel.tsx`

**Usage:**
```tsx
import { DelegationHistoryPanel } from "@/components/delegation-history-panel"

<DelegationHistoryPanel
  userId="user123"
  onClose={() => {
    // User closed panel
  }}
/>
```

**Features:**
- Stats summary (completed count, avg satisfaction, traits collected)
- Expandable delegation cards
- Filter by coach type
- Sort by date/satisfaction

---

## Complete Flow

### End-to-End Example

Here's how to implement the complete delegation flow in your application:

```tsx
// 1. HEAD COACH DETECTS HIGH CURIOSITY
import { useState, useEffect } from "react"

function HeadCoachChat({ userId, curiosityData }) {
  const [delegation, setDelegation] = useState(null)
  const [showSwitcher, setShowSwitcher] = useState(false)

  useEffect(() => {
    // Analyze curiosity after each message
    analyzeCuriosity()
  }, [curiosityData])

  async function analyzeCuriosity() {
    const response = await fetch(`${API_BASE}/delegation/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        curiosity_data: curiosityData,
        tolerance: 0.7
      })
    })

    const data = await response.json()

    if (data.should_delegate) {
      setDelegation({
        coach: data.recommended_coach,
        coachName: getCoachName(data.recommended_coach),
        coachEmoji: getCoachEmoji(data.recommended_coach),
        itemCount: data.priority_items.length,
        priorityScore: Math.max(...data.priority_items.map(i => i.curiosity / 10)),
        curiosityTargets: data.priority_items.map(i => i.path)
      })
    }
  }

  return (
    <div>
      {/* Chat messages */}
      <ChatTranscript messages={messages} />

      {/* 2. SHOW DELEGATION BANNER */}
      {delegation && (
        <DelegationBanner
          recommendation={delegation}
          onAccept={() => setShowSwitcher(true)}
          onDismiss={() => setDelegation(null)}
        />
      )}

      {/* 3. COACH SWITCHER MODAL */}
      {showSwitcher && (
        <CoachSwitcher
          userId={userId}
          currentCoach="head_coach"
          targetCoach={delegation.coach}
          curiosityTargets={delegation.curiosityTargets}
          onSwitchComplete={(delegationId) => {
            console.log("Switched to", delegation.coach, "with delegation:", delegationId)
            setShowSwitcher(false)
            // Navigate to specialized coach interface
            window.location.href = `/chat/${delegation.coach}`
          }}
          onCancel={() => setShowSwitcher(false)}
        />
      )}
    </div>
  )
}
```

```tsx
// 4. SPECIALIZED COACH COLLECTS TRAITS
function PhotoCoachChat({ userId, delegationId }) {
  const [traitsCollected, setTraitsCollected] = useState([])
  const [curiosityBefore, setCuriosityBefore] = useState({})
  const [curiosityAfter, setCuriosityAfter] = useState({})

  // When user uploads photo and traits are extracted
  function handleTraitExtracted(traitPath, value, curiosityBefore, curiosityAfter) {
    setTraitsCollected(prev => [...prev, traitPath])
    setCuriosityBefore(prev => ({ ...prev, [traitPath]: curiosityBefore }))
    setCuriosityAfter(prev => ({ ...prev, [traitPath]: curiosityAfter }))
  }

  return (
    <div>
      {/* Photo Coach chat interface */}
      <ChatTranscript messages={messages} />

      {/* 5. COMPLETION BUTTON */}
      {traitsCollected.length > 0 && (
        <DelegationCompleteButton
          userId={userId}
          delegationId={delegationId}
          traitsCollected={traitsCollected}
          curiosityBefore={curiosityBefore}
          curiosityAfter={curiosityAfter}
          notes="Analyzed user photo and collected visual traits"
          variant="success"
          onComplete={(summary) => {
            console.log("Delegation complete:", summary)
            // Navigate back to Head Coach
            window.location.href = `/chat/head_coach?delegation_complete=${delegationId}`
          }}
        />
      )}
    </div>
  )
}
```

```tsx
// 6. HEAD COACH SHOWS ACKNOWLEDGMENT
function HeadCoachChat({ userId }) {
  const [completedDelegation, setCompletedDelegation] = useState(null)

  useEffect(() => {
    // Check if returning from completed delegation
    const params = new URLSearchParams(window.location.search)
    const delegationId = params.get("delegation_complete")

    if (delegationId) {
      loadDelegationResults(delegationId)
    }
  }, [])

  async function loadDelegationResults(delegationId) {
    const response = await fetch(`${API_BASE}/delegation/${userId}/status/${delegationId}`)
    const data = await response.json()

    setCompletedDelegation(data.status)
  }

  return (
    <div>
      {/* 7. ACKNOWLEDGMENT UI */}
      {completedDelegation && (
        <DelegationReturnAcknowledgment
          delegationId={completedDelegation.delegation_id}
          coachMode={completedDelegation.coach}
          traitsCollected={completedDelegation.traits_collected}
          curiositySatisfied={completedDelegation.curiosity_satisfied}
          notes={completedDelegation.notes}
          onDismiss={() => setCompletedDelegation(null)}
        />
      )}

      {/* Chat continues */}
      <ChatTranscript messages={messages} />
    </div>
  )
}
```

---

## Integration Examples

### Example 1: Add Completion Button to Photo Coach

```tsx
// web/src/pages/photo-coach.tsx
import { DelegationCompleteButton } from "@/components/delegation-complete-button"
import { useParams, useRouter } from "next/navigation"
import { useState, useEffect } from "react"

export default function PhotoCoachPage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.userId
  const delegationId = params.delegationId

  const [traitsCollected, setTraitsCollected] = useState<string[]>([])
  const [curiosityBefore, setCuriosityBefore] = useState<Record<string, number>>({})
  const [curiosityAfter, setCuriosityAfter] = useState<Record<string, number>>({})

  // Load delegation context
  useEffect(() => {
    if (delegationId) {
      loadDelegationContext()
    }
  }, [delegationId])

  async function loadDelegationContext() {
    const response = await fetch(`/api/delegation/${userId}/status/${delegationId}`)
    const data = await response.json()

    // Set initial curiosity values from delegation targets
    const initialCuriosity = {}
    for (const target of data.status.curiosity_targets) {
      initialCuriosity[target] = 80 // Default high curiosity
    }
    setCuriosityBefore(initialCuriosity)
  }

  // When photo is analyzed and traits extracted
  function handlePhotoAnalyzed(analysis) {
    const newTraits = Object.keys(analysis.traits)
    setTraitsCollected(newTraits)

    // Update curiosity after values
    const afterCuriosity = {}
    for (const trait of newTraits) {
      afterCuriosity[trait] = analysis.curiosity_after[trait] || 10
    }
    setCuriosityAfter(afterCuriosity)
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Photo Coach Header */}
      <header className="p-4 border-b">
        <h1>📸 Photo Coach</h1>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-auto">
        {/* Chat messages and photo upload */}
      </div>

      {/* Completion Button (sticky footer) */}
      {traitsCollected.length > 0 && (
        <div className="p-4 border-t bg-white sticky bottom-0">
          <DelegationCompleteButton
            userId={userId}
            delegationId={delegationId}
            traitsCollected={traitsCollected}
            curiosityBefore={curiosityBefore}
            curiosityAfter={curiosityAfter}
            notes={`Analyzed ${traitsCollected.length} visual traits from photo`}
            variant="success"
            onComplete={(summary) => {
              // Redirect to Head Coach
              router.push(`/chat/head_coach?delegation_complete=${delegationId}`)
            }}
          />
        </div>
      )}
    </div>
  )
}
```

---

### Example 2: Integrate Acknowledgment in Head Coach

```tsx
// web/src/components/head-coach-chat.tsx
import { DelegationReturnAcknowledgment } from "@/components/delegation-return-acknowledgment"
import { useSearchParams } from "next/navigation"
import { useState, useEffect } from "react"

export function HeadCoachChat({ userId }) {
  const searchParams = useSearchParams()
  const [acknowledgment, setAcknowledgment] = useState(null)

  useEffect(() => {
    const delegationId = searchParams.get("delegation_complete")
    if (delegationId) {
      loadAcknowledgment(delegationId)
    }
  }, [searchParams])

  async function loadAcknowledgment(delegationId) {
    const response = await fetch(`/api/delegation/${userId}/status/${delegationId}`)
    const data = await response.json()

    setAcknowledgment({
      delegationId: data.status.delegation_id,
      coachMode: data.status.coach,
      traitsCollected: data.status.traits_collected,
      curiositySatisfied: data.status.curiosity_satisfied,
      notes: data.status.notes,
    })
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Show acknowledgment at top of chat */}
      {acknowledgment && (
        <DelegationReturnAcknowledgment
          {...acknowledgment}
          onDismiss={() => {
            setAcknowledgment(null)
            // Clear URL parameter
            window.history.replaceState({}, "", "/chat/head_coach")
          }}
        />
      )}

      {/* Regular chat transcript */}
      <ChatTranscript messages={messages} />
    </div>
  )
}
```

---

## Testing

### Running Tests

```bash
# Unit tests (coach mode switching)
pytest tests/test_coach_mode_switching.py -v

# Integration tests (delegation + mode)
pytest tests/test_delegation_mode_integration.py -v

# End-to-end lifecycle tests
pytest tests/test_delegation_lifecycle.py -v

# Run all delegation tests
pytest tests/test_coach_mode_switching.py tests/test_delegation_mode_integration.py tests/test_delegation_lifecycle.py -v
```

### Test Coverage

- **26 total tests, all passing**
- Unit tests: 13/13 ✅
- Integration tests: 8/8 ✅
- Lifecycle tests: 5/5 ✅

### Key Test Scenarios

1. ✅ Complete Photo Coach delegation with high satisfaction
2. ✅ Complete Relationship Coach delegation with moderate satisfaction
3. ✅ Delegation without auto-return (stay in coach mode)
4. ✅ Mode history includes completion context
5. ✅ Multiple sequential delegations
6. ✅ Concurrent delegations to different coaches
7. ✅ Invalid mode handling
8. ✅ Mode statistics tracking

---

## CReDNA Compatibility

The delegation system is designed to be compatible with future CReDNA (Coach ReDNA) implementation:

### Current Design Decisions

1. **User-scoped state**: All delegation and mode data is per-user
2. **Extensible metadata**: Delegation records can be extended with `credna_profile_id`
3. **Modular prompts**: Specialized coaches use prompt builders that accept personality overlays
4. **Coach registry**: Already supports per-coach metadata for CReDNA keys

### Future CReDNA Integration Points

```python
# Example: How CReDNA will integrate

# Delegation creation with CReDNA
delegation_record = {
    "delegation_id": "...",
    "coach": "photo_coach",
    "user_id": "user123",
    "credna_profile_id": "BSTest_photo_coach",  # Future field
    "context": {...}
}

# Prompt building with CReDNA personality
def build_photo_coach_prompt(
    delegation_id: str,
    curiosity_targets: List[str],
    credna_personality: Optional[Dict] = None  # Future parameter
):
    prompt = BASE_PHOTO_COACH_PROMPT

    # Apply CReDNA personality overlay
    if credna_personality:
        prompt = apply_personality_overlay(prompt, credna_personality)

    # Add delegation context
    if delegation_id:
        prompt += build_delegation_context(curiosity_targets)

    return prompt
```

---

## Troubleshooting

### Common Issues

#### 1. Mode doesn't switch after delegation creation

**Problem:** Delegation created but user stays in Head Coach mode.

**Solution:** Ensure you're calling BOTH endpoints:
```tsx
// Step 1: Create delegation
const delegationResponse = await fetch("/delegation/create", {...})
const { delegation_id } = delegationResponse.json()

// Step 2: Switch mode (don't forget this!)
await fetch(`/users/${userId}/coach-mode`, {
  method: "POST",
  body: JSON.stringify({
    target_mode: "photo",
    delegation_id: delegation_id
  })
})
```

#### 2. Completion doesn't return to Head Coach

**Problem:** Delegation completes but stays in specialized coach mode.

**Solution:** Check `auto_return` flag in completion request:
```json
{
  "traits_collected": [...],
  "curiosity_before": {...},
  "curiosity_after": {...},
  "auto_return": true  // Make sure this is true!
}
```

#### 3. Curiosity satisfaction always 0

**Problem:** Satisfaction calculation returns 0.

**Solution:** Ensure `curiosity_before` values are non-zero and `curiosity_after` is lower:
```json
{
  "curiosity_before": {"PaDNA.HairDNA.Color": 85.0},  // Must be > 0
  "curiosity_after": {"PaDNA.HairDNA.Color": 12.0}     // Should be < before
}
```

Formula: `satisfaction = (before - after) / before`

---

## Next Steps

### Recommended Integration Order

1. **Add completion button to Photo Coach UI** (easiest win)
2. **Add acknowledgment to Head Coach chat** (complete the loop)
3. **Wire up delegation triggers in HC conversation flow** (automation)
4. **Test with real LLM conversations** (validation)
5. **Add ActiveDelegationsWidget to sidebar** (monitoring)
6. **Implement DelegationHistoryPanel** (analytics)

### Future Enhancements

- [ ] Multi-delegation: User can have multiple active delegations
- [ ] Delegation cancellation: User can cancel before completion
- [ ] Partial completion: Mark traits collected incrementally
- [ ] Coach suggestions: Specialized coaches suggest other coaches
- [ ] Delegation scheduling: Schedule delegation for later
- [ ] Delegation templates: Pre-defined curiosity target sets

---

## Support

For questions or issues with the delegation system:

1. Check test files for usage examples
2. Review component source code (well-commented)
3. Check API endpoint documentation above
4. Run tests to verify system health

---

**Version:** 1.0
**Last Updated:** October 6, 2025
**Status:** Complete and tested (26/26 tests passing)
