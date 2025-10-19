# Developer Mode Architecture

**Status:** ✅ IMPLEMENTED
**Date:** 2025-10-06
**Version:** 1.0.0

---

## 🎯 Overview

The ReDNA system now supports **two distinct operating modes**:

### 👤 User Mode (Default)
- Pristine, production-ready interface
- Only shows features actual end users would see
- Clean, minimal, focused on coaching experience
- Relies on Head Coach delegation for coach switching
- No debugging tools, raw metrics, or development panels

### 🛠️ Developer Mode
- Additional debugging tools, metrics, and controls
- Manual coach switching buttons (PersonaRail)
- Performance metrics, feature flags, raw data views
- Development-only panels and diagnostics
- Full access to all system internals

---

## 🏗️ Architecture

### Core Components

#### 1. Developer Mode Context

**File:** `web/src/lib/developer-mode.tsx`

Provides global state management for developer mode:

```typescript
import { useDeveloperMode, DevOnly, UserOnly } from '@/lib/developer-mode';

// Hook to access mode state
const { isDeveloperMode, toggleDeveloperMode, setDeveloperMode } = useDeveloperMode();

// Components for conditional rendering
<DevOnly>
  <DebugPanel />
</DevOnly>

<UserOnly>
  <CleanCoachInterface />
</UserOnly>
```

**Key Features:**
- State persisted in localStorage (`redna_developer_mode`)
- React Context for global access across components
- SSR-safe hydration
- Automatic logging of mode changes

#### 2. Conditional Rendering Components

**DevOnly Component:**
```typescript
<DevOnly fallback={<UserModeAlternative />}>
  <PersonaRail />
</DevOnly>
```

**UserOnly Component:**
```typescript
<UserOnly fallback={<DeveloperModeAlternative />}>
  <CleanDelegationUI />
</UserOnly>
```

**HOC Wrappers:**
```typescript
const DevOnlyComponent = withDevOnly(DebugPanel);
const UserOnlyComponent = withUserOnly(CleanInterface);
```

#### 3. Settings Toggle

**File:** `web/src/components/settings-modal.tsx`

Developer Mode toggle added to Settings modal:
- Prominently displayed with orange styling
- Shows ON/OFF badge
- Explains User vs Developer mode differences
- Persists across sessions

---

## 🔒 Left Pane Sanctity Rule

**CRITICAL:** Developer Mode changes MUST NOT affect the Left Pane (chat/transcript/composer) in User Mode.

### Protected Areas (User Mode)
- Transcript panel
- Chat composer
- Message history
- Head Coach conversation interface

### Safe Areas (Developer Mode Only)
- PersonaRail (manual coach switching)
- Right sidebar debugging panels
- Performance HUD
- Feature flag toggles
- Raw data inspectors

---

## 📝 Usage Guidelines

### Adding Dev-Only Features

When adding a feature that should ONLY appear in Developer Mode:

```typescript
import { DevOnly } from '@/lib/developer-mode';

function MyComponent() {
  return (
    <>
      {/* This always shows */}
      <UserFacingFeature />

      {/* This only shows in Developer Mode */}
      <DevOnly>
        <DebugMetrics />
        <RawDataView />
      </DevOnly>
    </>
  );
}
```

### Adding User-Only Features

When adding a feature that should ONLY appear in User Mode:

```typescript
import { UserOnly } from '@/lib/developer-mode';

function MyComponent() {
  return (
    <>
      {/* This only shows in User Mode */}
      <UserOnly>
        <CleanDelegationPrompt />
      </UserOnly>

      {/* This always shows */}
      <SharedFeature />
    </>
  );
}
```

### Mode-Aware Components

Components that need to adapt their behavior based on mode:

```typescript
import { useDeveloperMode } from '@/lib/developer-mode';

function AdaptiveComponent() {
  const { isDeveloperMode } = useDeveloperMode();

  return (
    <div className={isDeveloperMode ? 'debug-mode' : 'clean-mode'}>
      {isDeveloperMode ? (
        <DetailedMetrics />
      ) : (
        <SimplifiedView />
      )}
    </div>
  );
}
```

---

## 🎨 Current Implementation

### Developer Mode Only (Hidden in User Mode)

#### PersonaRail
**Location:** `web/src/app/page-client.tsx` (lines 2256-2263, 2290-2297)

Manual coach switching buttons wrapped in `<DevOnly>`:
- Head Coach
- Photo Coach
- Relationship Coach
- Future coaches (PaDNA Coach, etc.)

**User Mode Alternative:** Delegation banner powered by Head Coach recommendations

#### Observation Summary (Conversation Metrics)
**Location:** `web/src/app/page-client.tsx` (lines 2815-2827)

Technical conversation metrics wrapped in `<DevOnly>`:
- Message counts
- Turn-taking statistics
- Session duration
- Window selection (1h/24h/session)

**Reasoning:** Raw technical metrics are not actionable for end users. Users don't need to know "I've sent 42 messages" - they just want coaching help.

**User Mode Alternative:** None needed - this is purely diagnostic data

#### RR/DNA Panel
**Location:** `web/src/app/page-client.tsx` (lines 2264-2273)

Complete RR metrics panel wrapped in `<DevOnly>`:
- Average RR per container
- Average UCN per container
- Curiosity scores (derived from RR)
- Top 10 traits by curiosity per container
- RR bands (High/Medium/Low/Early)

**Reasoning:** RR (Resolution Rate) and UCN (Uniqueness/Commonality/Novelty) are internal scoring mechanisms. End users don't need to understand these technical metrics - they just want to explore their traits.

**User Mode Alternative:** Unabridged panel (simplified view)

#### UCN and Curiosity Columns (Unabridged Panel)
**Location:** `web/src/components/unabridged-panel.tsx` (lines 259-296, 451-461)

Developer-only columns and filters:
- UCN column (hidden in User Mode)
- Curiosity column (hidden in User Mode)
- "High curiosity ≥60%" filter checkbox (hidden in User Mode)

**Reasoning:** UCN scores and curiosity metrics are internal prioritization mechanisms. Users don't need to see these - they just want to see their trait values.

**User Mode View:** Shows Container, Trait, Value, RR, Governance, Why?, Timeline columns only

#### Future Dev-Only Features
- Performance metrics dashboard
- Feature flag panel
- API request inspector
- Trait editing tools (enhanced)
- Container explosion controls
- Ontology browser

### Shared Features (Both Modes)

- Chat transcript
- Message composer
- Coach Asks panel (proactive questions from coach)
- Nudge Inbox (actionable recommendations)
- **Unabridged panel** (simplified in User Mode - no UCN/Curiosity)
- Settings modal

---

## 🔄 Migration Strategy

### Phase 1: ✅ COMPLETE
- [x] Create developer mode context
- [x] Add settings toggle
- [x] Wrap PersonaRail in DevOnly
- [x] Document architecture

### Phase 2: Audit Existing Features
- [ ] Identify all dev-only elements in current UI
- [ ] Wrap performance HUD in DevOnly
- [ ] Wrap feature flag displays in DevOnly
- [ ] Create User Mode versions of coach switching

### Phase 3: Clean User Mode
- [ ] Design delegation-based coach switching
- [ ] Remove all debugging artifacts from User Mode
- [ ] Polish User Mode for production readiness

### Phase 4: Enhance Developer Mode
- [ ] Add comprehensive debugging panels
- [ ] Add ontology browser (container explosion viewer)
- [ ] Add trait editing tools
- [ ] Add API request inspector

---

## 📊 Example Scenarios

### Scenario 1: Coach Switching

**User Mode:**
```
User sees delegation banner:
"I think Photo Coach could help with 4 high-curiosity PaDNA traits"
[Accept] [Dismiss]

User clicks Accept → seamlessly delegated to Photo Coach
```

**Developer Mode:**
```
User sees PersonaRail sidebar:
[Head Coach] ← currently active
[Photo Coach]
[Relationship Coach]

User clicks Photo Coach → immediately switches
```

### Scenario 2: Performance Issues

**User Mode:**
```
Clean interface with no performance metrics.
If lag occurs, user reports issue via feedback.
```

**Developer Mode:**
```
Performance HUD shows:
- FPS: 58
- Commit time: 18ms
- Virtualizer stats
- API latency graph

Developer diagnoses issue immediately.
```

### Scenario 3: Trait Exploration

**User Mode:**
```
User sees Unabridged panel with:
- Trait names
- Values
- Curiosity scores (simplified)

Clean, digestible view.
```

**Developer Mode:**
```
Developer sees Unabridged panel with:
- Trait names
- Values
- UCN (raw scores)
- RR (raw percentiles)
- Governance badges
- Container paths
- Edit/delete controls
```

---

## 🚨 Important Rules

### DO:
✅ Use `<DevOnly>` for debugging tools
✅ Use `<UserOnly>` for production-clean alternatives
✅ Test both modes before committing
✅ Document which mode a feature belongs to
✅ Keep User Mode pristine and focused

### DON'T:
❌ Add dev features to User Mode
❌ Break User Mode when adding dev features
❌ Modify left pane without extreme caution
❌ Show raw metrics/flags in User Mode
❌ Assume users understand technical jargon

---

## 🔧 Testing Checklist

Before merging changes that affect mode-specific features:

- [ ] Toggle Developer Mode ON
  - [ ] Verify dev features appear
  - [ ] Verify PersonaRail shows
  - [ ] Verify debugging panels render

- [ ] Toggle Developer Mode OFF
  - [ ] Verify dev features disappear
  - [ ] Verify PersonaRail hides
  - [ ] Verify User Mode is clean and focused

- [ ] Test with localStorage cleared
  - [ ] Verify defaults to User Mode
  - [ ] Verify hydration works correctly

- [ ] Test across page refreshes
  - [ ] Verify mode persists
  - [ ] Verify no console errors

---

## 📦 Files Changed

| File | Purpose | Changes |
|------|---------|---------|
| `web/src/lib/developer-mode.tsx` | Core context | NEW - Context, hooks, components |
| `web/src/components/settings-modal.tsx` | Settings UI | Added Developer Mode toggle |
| `web/src/app/page-client.tsx` | Main app | Added DeveloperModeProvider, wrapped PersonaRail |

---

## 🎯 Future Enhancements

### User Mode Improvements
- Delegation-based coach recommendations
- Simplified trait exploration
- Guided onboarding flow
- Context-aware help system

### Developer Mode Additions
- Ontology browser (DNA tree visualization)
- Container explosion controls
- Trait batch editing
- RR/UCN distribution visualizations
- API request/response inspector
- Performance profiling dashboard
- Feature flag management panel
- User data import/export tools

---

## 📚 Related Documentation

- [Left Pane Sanctity Rule](LEFT_PANE_SANCTITY_RULE.md)
- [Delegation System Guide](../ReDNACoreDemo/DELEGATION_SYSTEM_GUIDE.md)
- [Focused Chat Layout Solution](FOCUSED_CHAT_LAYOUT_SOLUTION.md)

---

**Last Updated:** 2025-10-06
**Author:** Claude Code
**Status:** ✅ IMPLEMENTED AND READY FOR USE
