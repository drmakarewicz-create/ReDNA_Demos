# Head Coach UI Improvements - Analysis & Plan

## Issues Identified

### 1. **Curiosity Still Disabled**
**Current State**: Status badge shows "Curiosity: Disabled"
**Root Cause**: Core API `/curiosity` endpoint requires `CURIOSITY_ON=true` flag
**Location**: `ReDNACoreDemo/core/api.py` line ~6000

**Fix**: Enable curiosity in Core API configuration

### 2. **Head Coach Quick Actions Taking Up Real Estate**
**Current State**: Large panel at top with 3 buttons (Generate demo ask, Approve, Rescore Now)
**Location**: `web/src/components/head-coach/head-coach-toolbar.tsx`

**Purpose Analysis**:
- **Generate demo ask**: Creates placeholder tasks for demo/testing (not needed in production)
- **Approve ask**: Approves planner asks (could be moved inline to the asks panel)
- **Rescore Now**: Ingests composer text and updates RR scores (useful, but could be in composer)

**Recommendation**: **YES, safe to move** this panel. It's primarily for development/testing.

**Options**:
A. **Hide entirely** (best for production)
B. **Move to settings/developer panel** (collapsible)
C. **Integrate into chat composer** (Rescore button only)

### 3. **Reorganize Top Navigation**
**Current Layout**:
```
[Workspace]  [Active User]  [Import user] [Import bulk] [Settings] [Open snapshots]
                                                    [Core: Online] [UCN/RR: Online] [Curiosity: Disabled]
```

**Proposed Layout**:
```
[Workspace]  [Core●] [UCN/RR●] [Curiosity●]  [Active User]  [Import] [Bulk] [Settings] [Snapshots]
```

**Benefits**:
- More compact status indicators
- Actions grouped on right
- More space for transcript

### 4. **Head Coach Still Giving Rote Responses**
**Current State**: Head Coach uses template responses ("I logged that for the Head Coach board...")
**Root Cause**: Not wired to LLM - using hardcoded responses

**Location**: Need to find where Head Coach chat responses are generated

**Fix Required**: Wire to actual LLM (llama3_client or OpenAI)

---

## Implementation Plan

### Phase 1: Enable Curiosity ✅
**Files to modify**:
- `ReDNACoreDemo/core/api.py` - Set `CURIOSITY_ON = True`

### Phase 2: Hide/Move Quick Actions Panel
**Files to modify**:
- `web/src/app/page-client.tsx` - Conditionally render or move toolbar

**Options**:
1. Add feature flag to hide in production
2. Move to collapsed developer panel
3. Integrate "Rescore" into composer (keep useful functionality)

### Phase 3: Reorganize Top Nav
**Files to modify**:
- `web/src/app/page-client.tsx` - Reorder status badges and action buttons

**Changes**:
1. Make status badges more compact (icon + dot indicator)
2. Move to left side next to workspace
3. Group action buttons on right

### Phase 4: Wire Head Coach to AI
**Files to find/modify**:
- Head Coach chat handler (likely in ExplorerFinal or web/src)
- Replace template responses with LLM calls

**Architecture**:
```
User message → Head Coach runtime → LLM call → Contextualized response
```

---

## Detailed Fixes

### Fix 1: Enable Curiosity

**File**: `ReDNACoreDemo/core/api.py`
**Line**: ~87

Change:
```python
# Before
CURIOSITY_ON = False

# After
CURIOSITY_ON = True
```

### Fix 2: Hide Quick Actions (Option A - Recommended)

**File**: `web/src/app/page-client.tsx`

Add environment variable:
```typescript
const SHOW_DEV_TOOLBAR = process.env.NEXT_PUBLIC_SHOW_DEV_TOOLBAR === 'true';
```

Then conditionally render:
```typescript
{SHOW_DEV_TOOLBAR && (
  <HeadCoachToolbar ... />
)}
```

### Fix 3: Reorganize Top Nav

**Changes to status badges**:
```typescript
// Make compact - just colored dot + text
<StatusBadge tone={coreBadgeTone} label="Core" tooltip={coreBadgeTooltip} compact />
```

**Reorder layout**:
```typescript
<header className="flex items-center justify-between">
  <div className="flex items-center gap-4">
    {/* Workspace */}
    <div>...</div>

    {/* Status badges - compact */}
    <div className="flex items-center gap-2">
      <StatusBadge ... />
      <StatusBadge ... />
      <StatusBadge ... />
    </div>

    {/* User switcher */}
    <UserSwitcher ... />
  </div>

  <div className="flex items-center gap-2">
    {/* Actions */}
    <button>Import</button>
    <button>Bulk</button>
    <button>Settings</button>
    <button>Snapshots</button>
  </div>
</header>
```

### Fix 4: Wire Head Coach to AI

**Step 1**: Find chat handler
**Step 2**: Replace template logic with LLM call
**Step 3**: Add context from user profile/observations
**Step 4**: Use behavioral modes from decision framework

---

## Priority Order

1. **Enable Curiosity** (5 min) - Simple flag change
2. **Hide Quick Actions** (10 min) - Add feature flag
3. **Reorganize Nav** (30 min) - Layout restructuring
4. **Wire to AI** (2 hours) - Requires investigation + implementation

---

## Next Steps

Would you like me to:
1. Start with enabling Curiosity?
2. Implement all 4 fixes in sequence?
3. Focus on a specific issue first?

Let me know your preference and I'll proceed!
