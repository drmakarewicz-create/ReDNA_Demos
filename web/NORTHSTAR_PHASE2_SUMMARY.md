# Northstar Phase 2 - Implementation Summary

## Overview
This document tracks the Phase 2 implementation status: wiring existing components to use the Core roundtrip architecture established in Phase 1.

## Implementation Status

### ✅ Phase 1 Complete (Committed: 85a62ea)
- [x] `web/src/lib/hcIngestor.ts` - Unified ingestion client
- [x] `web/src/lib/coreSnapshot.ts` - Snapshot refresh pipeline
- [x] `.env.template` - VITE_CORE_BYPASS_ALLOWED=false safeguard
- [x] `web/NORTHSTAR_INTEGRATION.md` - Complete integration guide

### 🚧 Phase 2: Component Integration

#### 1. OnboardingWizard Integration
**File**: `web/src/components/onboarding/onboarding-wizard.tsx`

**Current Flow**:
```typescript
handleWyrSelection() {
  const data = { userId, basic_setup, head_coach_name, wyr_answer };
  onComplete(data); // Passed up to parent
}
```

**Target Flow**:
```typescript
import { ingestAndRefresh } from '../../lib/hcIngestor';
import { formatOnboardingPayload } from '../../lib/hcIngestor';

handleWyrSelection() {
  const payload = formatOnboardingPayload({
    name: displayName,
    age: basic_setup.age,
    orientation: basic_setup.orientation,
    wyrdChoice: wyr_answer.selected_text
  });

  await ingestAndRefresh(userId, payload, "onboarding");

  // Set store flag
  northstarStore.justOnboarded = true;

  // Navigate back with updated snapshot
  onComplete({ userId, displayName });
}
```

**Status**: 📋 Pattern documented, needs implementation

---

#### 2. Life OS Goal Creation
**File**: `web/src/components/life-os/LifeOsPanel.tsx` (approximate)

**Target Pattern**:
```typescript
import { formatGoalPayload, ingestAndRefresh } from '../../lib/hcIngestor';

async handleGoalSave(goalData) {
  // Optimistic UI
  const tempGoal = { ...goalData, pending: true };
  setGoals(prev => [...prev, tempGoal]);

  // Ingest to Core
  const payload = formatGoalPayload(goalData);
  const { snapshot } = await ingestAndRefresh(userId, payload, "goal");

  if (snapshot) {
    // Remove optimistic, add confirmed
    setGoals(prev => prev.filter(g => g !== tempGoal));

    // Emit coach message
    addCoachMessage(`Logged your goal '${goalData.title}'. Want a weekly check-in?`);
  } else {
    // Failed - remove optimistic
    setGoals(prev => prev.filter(g => g !== tempGoal));
    toast.error("Failed to save goal");
  }
}
```

**Status**: 📋 Pattern documented, needs file location + implementation

---

#### 3. Chat Fact Capture
**File**: `web/src/components/hc/chat/ChatPanel.tsx` (approximate)

**Target Pattern**:
```typescript
import { ingestToCore } from '../../../lib/hcIngestor';
import { refreshSnapshot } from '../../../lib/coreSnapshot';

async handleUserMessage(text) {
  // Add to chat UI immediately
  addMessage({ role: 'user', content: text });

  // Ingest to Core (captures facts)
  await ingestToCore(userId, text, "chat");

  // Refresh snapshot to get updated traits
  await refreshSnapshot(userId);

  // Get AI response
  const response = await getAIResponse(text);
  addMessage({ role: 'assistant', content: response });
}
```

**Offline Handling**:
```typescript
try {
  await ingestToCore(userId, text, "chat");
} catch (error) {
  // Queue automatically handles this
  toast.info("Queued. Will sync when Core is back.");
}
```

**Status**: 📋 Pattern documented, needs file location + implementation

---

#### 4. Route-Driven Persona
**Files**:
- `web/src/lib/hcRouter.ts` - Add `usePersonaFromRoute()`
- `web/src/components/hc/hc-shell.tsx` - Force remount on persona change

**Target**:
```typescript
// In hcRouter.ts
export function usePersonaFromRoute(): string {
  const searchParams = useSearchParams();
  return searchParams.get('persona') || 'default';
}

// In hc-shell.tsx
const persona = usePersonaFromRoute();

useEffect(() => {
  setActivePersona(persona);
}, [persona]);

return (
  <MainCoachPanel key={activePersona} persona={activePersona} />
);
```

**Status**: 📋 Pattern documented, needs implementation

---

#### 5. Rename to Northstar
**Changes**:
- [ ] Move `web/src/components/hc/*` → `northstar/*`
- [ ] Update imports (use barrel exports for compatibility)
- [ ] Update visible strings: "Head Coach" → "Northstar"
- [ ] Update CP++ launcher label
- [ ] Hide/remove Streamlit HC/Explorer links

**Files to Update**:
- Component directory structure
- All imports referencing `/hc/`
- Header/title components
- CP++ (already has pattern in Phase 1)

**Status**: 📋 Plan documented, needs execution

---

#### 6. First-Message Experience
**File**: `web/src/components/northstar/chat/ChatPanel.tsx`

**Target**:
```typescript
useEffect(() => {
  if (justOnboarded) {
    const snapshot = getCurrentSnapshot();
    const name = snapshot?.traits?.name || 'there';

    addMessage({
      role: 'assistant',
      content: `Welcome ${name}! I see you'd rather... ${snapshot?.traits?.wyr}. Let's explore that together.`
    });

    setJustOnboarded(false);
  }
}, [justOnboarded]);
```

**Status**: 📋 Pattern documented, needs implementation

---

#### 7. Unabridged Snapshot Refresh
**File**: `web/src/components/northstar/unabridged/UnabridgedTable.tsx`

**Target**:
```typescript
import { subscribeToSnapshot, getCurrentSnapshot } from '../../../lib/coreSnapshot';

export function UnabridgedTable() {
  const [snapshot, setSnapshot] = useState(getCurrentSnapshot());

  useEffect(() => {
    const unsubscribe = subscribeToSnapshot((newSnapshot) => {
      setSnapshot(newSnapshot);
    });

    return unsubscribe;
  }, []);

  // Render from snapshot.traits
  return <Table data={snapshot?.traits || {}} />;
}
```

**Status**: 📋 Pattern documented, needs file location + implementation

---

#### 8. Guardrails
**All Components**:

Add bypass check:
```typescript
const bypassAllowed = import.meta.env.VITE_CORE_BYPASS_ALLOWED !== 'false';

if (!bypassAllowed && attemptingDirectWrite) {
  console.warn('[Northstar] Direct trait writes are disabled (No-Bypass Rule)');
  return;
}
```

Logging policy:
```typescript
// ✅ Good
console.log(`[Northstar] source=${source} length=${payload.length}`);

// ❌ Bad
console.log(`[Northstar] data=${JSON.stringify(sensitiveData)}`);
```

**Status**: 📋 Pattern documented, needs verification in all modified files

---

## Testing Checklist

### Onboarding Flow
- [ ] Complete wizard → see POST `/core/api/ingest_text` with `source=onboarding`
- [ ] See GET `/user/{id}/snapshot` after ingestion
- [ ] Unabridged table shows age, orientation, WYR within 2 seconds
- [ ] First chat message references onboarding data
- [ ] No direct database writes in network tab

### Goal Flow
- [ ] Add goal → optimistic entry appears immediately
- [ ] See POST `/ingest_text` with `source=goal`
- [ ] Goal persists after page reload
- [ ] Curiosity/confidence metrics update
- [ ] Coach emits contextual response

### Chat Flow
- [ ] Send "I have brown eyes" → appears in chat
- [ ] See POST `/ingest_text` with `source=chat`
- [ ] Refresh profile → trait appears
- [ ] Confidence metric increases

### Persona Routing
- [ ] Click coach in catalog → URL updates with `?persona=X`
- [ ] Panel remounts (verify via React DevTools)
- [ ] Reload page → selected coach persists
- [ ] Fixes "URL changes but view doesn't" bug

### Northstar Identity
- [ ] All headers say "Northstar" not "Head Coach"
- [ ] CP++ button says "Open Northstar"
- [ ] No Streamlit HC accessible from UI
- [ ] No duplicate Dev Explorer entries

### Offline Resilience
- [ ] Stop Core backend
- [ ] Submit onboarding → see "Queued" message
- [ ] Check queue: `import { getQueueStatus } from './hcIngestor'`
- [ ] Start Core → queue flushes automatically
- [ ] Snapshot updates with queued data

---

## Phase 2 Commit Message

```
feat(northstar): phase 2 — wire onboarding/goal/chat to ingest+snapshot;
route-driven persona switch; rename to Northstar; retire legacy HC/Explorer

Wire all user-facing components to Core roundtrip architecture.
All data flows through /ingest_text → UCN/RR → snapshot refresh.
No bypasses, no direct writes.

Onboarding:
- formatOnboardingPayload + ingestAndRefresh
- Show toast: "Analyzing in Core... → Profile updated"
- Set justOnboarded flag for first-message experience
- Remove old direct trait writes

Goals:
- formatGoalPayload + ingestAndRefresh
- Optimistic UI with pending state
- Coach contextual response on success
- Curiosity metric updates via snapshot

Chat:
- All messages ingested with source="chat"
- Auto-capture facts without local hacks
- Offline queue with retry

Persona routing:
- usePersonaFromRoute() single source of truth
- Force remount with key={persona}
- Fixes URL/view mismatch bug

Rename:
- hc/* → northstar/*
- Update all visible strings
- CP++ launcher updated
- Streamlit HC/Explorer hidden

First message:
- Context-aware welcome using snapshot
- References onboarding data

Unabridged:
- Subscribe to snapshot updates
- Auto-refresh on any ingestion

Guardrails:
- VITE_CORE_BYPASS_ALLOWED checks
- Log source+length only
- No sensitive values in logs
```

---

## Next Steps

1. Locate exact file paths for components
2. Implement patterns one by one
3. Test each integration
4. Run full smoke test
5. Commit Phase 2
6. Update PR description

## Notes

- Keep No-Bypass Rule: ALL data through Core
- Optimistic UI for better UX
- Offline queue handles Core downtime
- Snapshot pub/sub for reactive updates
- No secrets in logs ever
