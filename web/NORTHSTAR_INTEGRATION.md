# Northstar Integration - Core Roundtrip Architecture

## Overview

This document describes the Northstar (React Head Coach) integration with the Core roundtrip architecture, ensuring all user data flows through a unified ingestion pipeline.

## Architecture Principles

### No Bypass Rule
**All user-origin data must flow through Core → UCN/RR → Core pipeline.**

- ❌ NO direct trait writes
- ❌ NO shortcut APIs for onboarding/goals/preferences
- ❌ NO local-only mutations
- ✅ Single ingestion path for consistency
- ✅ Core handles normalization and scoring
- ✅ Northstar refreshes from Core snapshot

### Data Flow

```
User Input (Northstar)
  ↓
Format as structured payload
  ↓
POST to Core /ingest_text
  ↓
Core logs provenance
  ↓
Core routes to UCN/RR for scoring
  ↓
Core stores normalized traits
  ↓
Core returns updated snapshot
  ↓
Northstar refreshes UI from snapshot
```

## Implementation

### Core Files Created

#### 1. `web/src/lib/hcIngestor.ts`
Unified ingestion client for all user data.

**Functions:**
- `ingestToCore(userId, payload, source, metadata)` - Main ingestion function
- `formatOnboardingPayload(data)` - Format onboarding data
- `formatGoalPayload(goal)` - Format goal data
- `queueForRetry(payload)` - Offline queue for resilience

**Sources:**
- `"onboarding"` - Initial user setup
- `"goal"` - Life OS goals
- `"chat"` - Conversational facts
- `"preference"` - User preferences
- `"upload"` - File uploads

#### 2. `web/src/lib/coreSnapshot.ts`
Snapshot refresh pipeline.

**Functions:**
- `refreshSnapshot(userId, options)` - Fetch latest from Core
- `getCurrentSnapshot()` - Get cached snapshot
- `subscribeToSnapshot(callback)` - React to updates
- `ingestAndRefresh()` - Combined ingest + refresh
- `getSnapshotMetrics()` - Get confidence/curiosity

### Components Requiring Updates

#### OnboardingWizard.tsx
**Current:** Direct trait writes
**Target:** Use Core ingestion

```typescript
// Before
await saveTraitsDirectly(traits);

// After
const payload = formatOnboardingPayload(formData);
const { snapshot } = await ingestAndRefresh(
  user.id,
  payload,
  "onboarding"
);
updateUIFromSnapshot(snapshot);
```

#### LifeOsPanel.tsx
**Current:** Direct goal creation API
**Target:** Use Core ingestion

```typescript
// Before
await createGoal({ title, targetDate });

// After
const payload = formatGoalPayload({ title, targetDate });
await ingestAndRefresh(user.id, payload, "goal");
```

#### ChatPanel.tsx
**Current:** Direct message storage
**Target:** Auto-capture facts through ingestion

```typescript
// When AI extracts facts from conversation
if (detectedFacts.length > 0) {
  await ingestToCore(user.id, factsText, "chat");
  await refreshSnapshot(user.id);
}
```

### Naming Migration

#### File Renames
```
web/src/components/hc/ → web/src/components/northstar/
web/src/store/hcStore.ts → web/src/store/northstarStore.ts
web/src/lib/hcRouter.ts → web/src/lib/northstarRouter.ts
```

#### Component Renames
- Head Coach → Northstar
- HC Panel → Northstar Panel
- hc-* CSS classes → northstar-*

#### Keep Backward Compatibility (Temporary)
```typescript
// In renamed files
export * from '../northstar/...'; // Re-export from new location
```

### Control Panel Plus Plus Integration

Update CP++ to launch Northstar:

```python
# control_panel_plus_plus.py
st.sidebar.markdown("### 🧭 Northstar")
st.sidebar.write("React-based user experience orchestrator")

if st.sidebar.button("🚀 Open Northstar"):
    webbrowser.open("http://localhost:3001")
```

### Environment Configuration

Added to `.env.template`:
```bash
# === Northstar (React Head Coach) Safeguards ===
# Prevent direct trait writes - all data must flow through Core ingestion
VITE_CORE_BYPASS_ALLOWED=false
```

## Safeguards

### 1. Core Bypass Prevention
```typescript
const bypassAllowed = import.meta.env.VITE_CORE_BYPASS_ALLOWED !== 'false';
if (!bypassAllowed) {
  console.warn('[Northstar] Direct trait writes are disabled');
}
```

### 2. Ingestion Logging
```typescript
// Log source + length only (no sensitive values)
console.log(`[Northstar Ingestion] source=${source} length=${payload.length}`);
```

### 3. Offline Queue
When Core is unavailable, payloads queue in memory and retry automatically.

## Testing Checklist

### Onboarding Flow
- [ ] Submit onboarding form
- [ ] Verify payload sent to Core `/ingest_text`
- [ ] Check Core response includes snapshot
- [ ] Verify Unabridged view shows new traits
- [ ] Confirm no direct database writes

### Goal Creation
- [ ] Add new goal in Life OS
- [ ] Verify ingestion to Core
- [ ] Check UCN/RR updates curiosity metric
- [ ] Verify goal appears in UI after refresh
- [ ] Confirm snapshot updated

### Chat Facts
- [ ] Send message: "I have brown eyes"
- [ ] Verify fact extracted and ingested
- [ ] Check trait propagates to profile
- [ ] Confirm confidence metric updated

### Roundtrip Verification
- [ ] Network tab shows `/ingest_text` → `/snapshot` chain
- [ ] Snapshot version increments after each ingestion
- [ ] All subscribers notified of updates
- [ ] UI components re-render with fresh data

### Northstar Identity
- [ ] CP++ shows "Northstar" not "Head Coach"
- [ ] No Streamlit HC visible in menus
- [ ] All docs reference Northstar
- [ ] README updated

### Safety
- [ ] `VITE_CORE_BYPASS_ALLOWED=false` prevents direct writes
- [ ] Console shows warnings on bypass attempts
- [ ] No API keys in logs
- [ ] Queue handles offline gracefully

## Migration Status

### ✅ Completed
- [x] Core ingestion client (`hcIngestor.ts`)
- [x] Snapshot refresh pipeline (`coreSnapshot.ts`)
- [x] Environment safeguards
- [x] Documentation

### 🚧 In Progress
- [ ] OnboardingWizard integration
- [ ] LifeOsPanel goal flow
- [ ] ChatPanel fact extraction
- [ ] File/component renames

### 📋 Pending
- [ ] CP++ launcher updates
- [ ] README/docs updates
- [ ] End-to-end testing
- [ ] Legacy component removal

## API Reference

### Core Endpoints

#### POST /core/api/ingest_text
```json
{
  "user_id": "string",
  "text": "string",
  "source": "onboarding|goal|chat|preference|upload",
  "metadata": {}
}
```

**Response:**
```json
{
  "success": true,
  "message": "Ingested successfully",
  "snapshot": { ... }
}
```

#### GET /core/api/user/{id}/snapshot
**Response:**
```json
{
  "user_id": "string",
  "traits": {},
  "dnas": {},
  "metrics": {
    "confidence": 0.75,
    "curiosity": 0.42
  },
  "timestamp": "2025-10-13T...",
  "version": 123
}
```

## Future Enhancements

1. **Persistent Queue**: IndexedDB for offline ingestion queue
2. **Optimistic Updates**: Show pending changes before Core confirms
3. **Delta Updates**: Only refresh changed traits instead of full snapshot
4. **WebSocket**: Real-time snapshot push from Core
5. **Conflict Resolution**: Handle concurrent ingestions gracefully

## Support

See also:
- `web/src/lib/hcIngestor.ts` - Implementation details
- `web/src/lib/coreSnapshot.ts` - Snapshot management
- Core API documentation
- UCN/RR scoring pipeline docs
