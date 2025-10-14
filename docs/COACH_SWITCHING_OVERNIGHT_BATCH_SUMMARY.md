# Coach Switching: Overnight Batch Summary
**Date**: 2025-10-06
**Session**: Coach Catalog Integration & Multi-Layer Architecture Fix

---

## Executive Summary

Completed a comprehensive fix for coach switching functionality across all 6 coaches in the ReDNA system. The issue was a **multi-layer architecture problem** where coaches needed to be registered in 5 separate validation layers spanning backend Python code and frontend TypeScript code.

**Result**: All coaches now switch properly when clicked in the Coach Catalog. No more silent failures or "Failed to switch modes" errors.

---

## Problem Analysis

### The Multi-Layer Validation Stack

Coach switching requires passing through **5 distinct validation layers**:

1. **Backend Coach Registry** (`coach_registry.yaml`) - Defines coach capabilities
2. **Backend Mode Validation** (`coach_mode_manager.py`) - Validates mode switch requests
3. **Backend UI Roster** (`ui_readonly.py`) - Provides persona roster to frontend
4. **Frontend Normalization** (`api.ts`) - Filters and normalizes persona keys
5. **Frontend State Management** (`page-client.tsx`) - Handles UI persona switching

**Any single layer failing = silent failure** where the coach appears in the catalog but doesn't work when clicked.

### Root Causes Identified

1. **Missing from VALID_MODES**: Career Coach, Personality Test Coach, PaDNA Coach (both `padna` and `padna_coach` aliases)
2. **Missing from Persona Roster**: Career Coach, Personality Test Coach not in `_FALLBACK_PERSONAS`
3. **Missing from PERSONA_ALIASES**: Career Coach, Personality Test Coach not recognized by frontend normalization
4. **Incorrect normalization mapping**: PaDNA and Relationship Coach being mapped to wrong keys
5. **Missing MODE_CAPABILITIES**: New coaches didn't have capability definitions

---

## Fixes Implemented

### 1. Backend Mode Manager (`coach_mode_manager.py`)

**Added to VALID_MODES** (line 27):
```python
VALID_MODES = {
    "head_coach",
    "photo", "photo_coach",           # Both aliases for backwards compatibility
    "relationship", "relationship_coach",
    "career_coach",
    "personality_test_coach",
    "padna", "padna_coach"             # Both aliases
}
```

**Added to MODE_DISPLAY_NAMES** (line 30):
```python
MODE_DISPLAY_NAMES = {
    "career_coach": "Career Coach",
    "personality_test_coach": "Personality Test Coach",
    "padna": "PaDNA Coach",
    "padna_coach": "PaDNA Coach",
    # ... existing coaches
}
```

**Added to MODE_CAPABILITIES** (line 43):
```python
MODE_CAPABILITIES = {
    "career_coach": {
        "namespaces": ["SkillDNA", "ProfDNA", "BehDNA"],
        "description": "Career development, skill optimization, and professional growth",
        "emoji": "💼",
    },
    "personality_test_coach": {
        "namespaces": ["PsyDNA", "BehDNA"],
        "description": "Personality assessment and psychological profiling",
        "emoji": "🧠",
    },
    "padna_coach": {
        "namespaces": ["PaDNA"],
        "description": "Physical appearance DNA and aesthetic profiling",
        "emoji": "🧬",
    },
    # ... plus photo_coach, padna aliases
}
```

### 2. Backend UI Roster (`ui_readonly.py`)

**Updated persona_roster() function** (line 125-154):
```python
def persona_roster() -> List[Dict[str, Any]]:
    # Try router first, then registry
    roster = _load_persona_roster_from_router()
    if not roster:
        roster = _load_persona_roster_from_registry()

    # CRITICAL FIX: Always merge fallback personas that aren't already present
    existing_keys = {item["key"] for item in roster}

    for entry in _FALLBACK_PERSONAS:
        persona_id = entry["key"]
        if persona_id not in existing_keys:
            roster.append({
                "key": persona_id,
                "label": entry["label"],
                "icon": entry.get("icon", _DEFAULT_ICON),
                "enabled": _persona_enabled(persona_id),
                "accent_color": None,
            })

    roster.sort(key=lambda item: item["key"])
    return roster
```

**Why this matters**: Previously, if the persona registry returned data, fallback personas were never added. This caused career_coach and personality_test_coach to be missing from the frontend roster, leading to silent failures.

### 3. Frontend Persona System (`api.ts`)

**Added to CANONICAL_ORDER** (line 2463):
```typescript
const CANONICAL_ORDER = [
  'head_coach',
  'relationship_coach',
  'career_coach',          // NEW
  'personality_test_coach', // NEW
  'padna',
  'photo'
] as const;
```

**Added to CANONICAL_DEFAULTS** (line 2466):
```typescript
const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  career_coach: {
    key: 'career_coach',
    label: 'Career Coach',
    icon: '💼',
    enabled: true,
    accent_color: null
  },
  personality_test_coach: {
    key: 'personality_test_coach',
    label: 'Personality Test Coach',
    icon: '🧠',
    enabled: true,
    accent_color: null
  },
  // ... existing coaches
};
```

**Added to PERSONA_ALIASES** (line 2511):
```typescript
const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  career_coach: 'career_coach',
  'career coach': 'career_coach',
  personality_test_coach: 'personality_test_coach',
  'personality test coach': 'personality_test_coach',
  // ... existing aliases
};
```

**Created normalizePersonaKey() helper** (line 2534):
```typescript
export function normalizePersonaKey(key: string): string {
  const normalized = key.trim().toLowerCase();
  return PERSONA_ALIASES[normalized] || normalized;
}
```

### 4. Frontend State Management (`page-client.tsx`)

**Fixed normalizePersonaKey() function** (line 2898):
```typescript
function normalizePersonaKey(key: string): 'head_coach' | 'photo' | 'padna' | 'relationship_coach' | ... {
  const normalized = key.trim().toLowerCase();
  switch (normalized) {
    case 'padna':
    case 'padna_coach':
    case 'padna coach':
      return 'padna';  // FIXED: Was returning 'rendering'!

    case 'relationship_coach':
    case 'relationship coach':
    case 'rc':
    case 'relationship':
      return 'relationship_coach';  // FIXED: Was returning 'rc'!

    // ... other cases
  }
}
```

**Updated onSelectCoach handler** (line 2401):
```typescript
onSelectCoach={async (coachId: string) => {
  // Normalize the coach ID for frontend state (e.g., photo_coach -> photo)
  const normalizedId = normalizePersonaKey(coachId);

  // First update the UI with normalized ID
  setActivePersona(normalizedId);

  // Then call the backend to switch coach mode with the original ID
  try {
    const response = await fetch(`${CORE_API_BASE}/users/${activeUser}/coach-mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_mode: coachId,
        context: { source: 'coach_catalog', timestamp: new Date().toISOString() }
      })
    });
    // ... error handling
  }
}}
```

---

## New Tools Created

### 1. Comprehensive Smoke Test Script

**File**: `ReDNACoreDemo/scripts/test_all_coach_modes.sh`

Features:
- Tests all coach mode switches via API
- Verifies mode persistence after each switch
- Tests legacy aliases (`photo`, `padna`, `relationship`)
- Color-coded output (green ✓ = pass, red ✗ = fail)
- Summary statistics

Usage:
```bash
cd ReDNACoreDemo
./scripts/test_all_coach_modes.sh
```

### 2. Updated Protocol Documentation

**File**: `docs/ADDING_NEW_COACH_PROTOCOL.md`

Complete rewrite with:
- Multi-layer architecture explanation
- Persona key normalization chain diagram
- Step-by-step instructions for all 7 files
- Common failure modes and root causes
- Emergency debugging checklist
- Quick reference table with line numbers

---

## Testing Results

### Coaches Tested
1. ✅ **Head Coach** - Default orchestrator
2. ✅ **Relationship Coach** - Relationships, emotions, psychology
3. ✅ **Career Coach** - Career planning, skills, professional development
4. ✅ **Personality Test Coach** - Personality profiling, motivations
5. ✅ **Photo Coach** - Physical appearance, style, visual presence
6. ✅ **PaDNA Coach** - Physical appearance DNA, aesthetic profiling

### Test Scenarios
- [x] Backend accepts mode switch requests for all coaches
- [x] Frontend persona roster includes all coaches
- [x] Coach Catalog displays all coaches with correct icons
- [x] Clicking each coach in catalog switches mode (no revert to Head Coach)
- [x] Mode persists after switch (verified via `/users/TEST` API)
- [x] Legacy aliases work (`photo`, `padna`, `relationship`)

---

## Architecture Insights

### The Normalization Chain

```
Coach Catalog ID  →  Frontend Normalization  →  Backend Mode  →  UI State
────────────────     ──────────────────────     ────────────     ────────
photo_coach      →   photo                  →   photo_coach  →   photo
padna_coach      →   padna                  →   padna_coach  →   padna
career_coach     →   career_coach           →   career_coach →   career_coach
relationship_coach → relationship_coach     →   relationship_coach → relationship_coach
```

### Why Multiple IDs Exist

**Historical reasons**:
- `photo` vs `photo_coach`: Legacy system used short names
- `relationship` vs `relationship_coach`: Different components used different conventions
- `padna` vs `padna_coach`: PaDNA was added later with `_coach` suffix

**Current solution**: Support both forms in VALID_MODES and normalize on the frontend.

### Critical Frontend Bug Fixed

**The loadPersonas Reset Loop**:

```typescript
// page-client.tsx line 1020
setActivePersona((current) => {
  if (roster.some((item) => item.key === current && item.enabled)) {
    return current;  // Keep current if it's in the roster
  }
  // OTHERWISE: Reset to first enabled persona
  const firstEnabled = roster.find((item) => item.enabled) ?? roster[0];
  return firstEnabled ? firstEnabled.key : current;
});
```

**What was happening**:
1. User clicks "Career Coach" in catalog
2. `onSelectCoach` calls `setActivePersona("career_coach")`
3. `loadPersonas` effect triggers
4. Roster doesn't include `career_coach` (missing from `_FALLBACK_PERSONAS`)
5. Frontend resets to first enabled coach (Head Coach)
6. User sees Head Coach instead of Career Coach

**Fix**: Added all coaches to `_FALLBACK_PERSONAS` in `ui_readonly.py`.

---

## Files Modified

### Backend (Python)
1. `ReDNACoreDemo/core/coach_mode_manager.py` - VALID_MODES, MODE_DISPLAY_NAMES, MODE_CAPABILITIES
2. `ReDNACoreDemo/core/ui_readonly.py` - persona_roster() merge logic, _FALLBACK_PERSONAS
3. `ReDNACoreDemo/core/coach_registry.yaml` - Added padna_coach definition

### Frontend (TypeScript/TSX)
4. `web/src/lib/api.ts` - CANONICAL_ORDER, CANONICAL_DEFAULTS, PERSONA_ALIASES, normalizePersonaKey()
5. `web/src/app/page-client.tsx` - normalizePersonaKey() fixes, onSelectCoach handler

### Documentation
6. `docs/ADDING_NEW_COACH_PROTOCOL.md` - Complete rewrite with multi-layer architecture
7. `docs/COACH_SWITCHING_OVERNIGHT_BATCH_SUMMARY.md` - This file

### New Files
8. `ReDNACoreDemo/scripts/test_all_coach_modes.sh` - Comprehensive smoke test script

---

## Lessons Learned

### 1. Silent Failures are Dangerous

When any layer fails validation, the system doesn't throw an error - it just silently reverts to Head Coach. This made debugging difficult because:
- Backend said "mode switched successfully"
- Frontend said "activePersona updated"
- But UI showed Head Coach anyway

**Solution**: The smoke test script now verifies the full chain.

### 2. Normalization Must Be Bidirectional

The frontend normalizes `photo_coach` → `photo`, but the backend expects `photo_coach`. The `onSelectCoach` handler must:
1. Normalize for frontend state (`photo`)
2. Send original to backend (`photo_coach`)

### 3. Documentation is Critical

Without the updated `ADDING_NEW_COACH_PROTOCOL.md`, the next developer would repeat the same mistakes. The protocol now explicitly lists:
- All 7 files to update
- Exact line numbers
- Why each update matters
- Common failure modes

### 4. Fallback Personas Must Be Complete

The `_FALLBACK_PERSONAS` array was intended as a "fallback" when the persona registry failed, but in practice, it's **always needed** because the roster loading logic merges registry data with fallbacks.

---

## Next Steps (Recommended)

### Short-term
1. ✅ Run smoke test script to verify all coaches work
2. ✅ Test in browser: Click each coach in catalog
3. ⏭️ Add prompts for Career Coach and Personality Test Coach in `api.py` (currently they switch modes but use Head Coach prompts)
4. ⏭️ Create system prompts for these coaches in `hc_llm_agent.py`

### Medium-term
1. Create integration tests that verify the full chain (catalog → frontend → backend → state)
2. Add TypeScript type safety to enforce coach IDs match across layers
3. Consider exposing MODE_CAPABILITIES via API so frontend can display coach descriptions

### Long-term (Architectural Improvements)
1. **Centralize coach definitions**: Single YAML source of truth
2. **Auto-generate prompts**: Build LLM prompts from coach registry
3. **Unify ID normalization**: Remove legacy aliases, use consistent IDs everywhere
4. **Type-safe coach system**: Use TypeScript enums/unions to prevent ID mismatches

---

## Known Limitations

1. **Career Coach and Personality Test Coach don't have custom prompts yet** - They use Head Coach prompts when you chat with them
2. **Legacy alias support is partial** - Some old components may still use `rc` instead of `relationship_coach`
3. **No validation for coach registry completeness** - You can add a coach to VALID_MODES without adding it to the registry

---

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `POST /users/{user_id}/coach-mode` | Switch active coach mode |
| `GET /users/{user_id}` | Get user data including current coach mode |
| `GET /ui/personas` | Get persona roster for frontend |
| `GET /ui/coach-catalog` | Get coach catalog with full descriptions |

---

## How to Verify Everything Works

### Quick Test (30 seconds)
```bash
# Test backend accepts all coaches
cd ReDNACoreDemo
./scripts/test_all_coach_modes.sh
```

### Full Test (2 minutes)
1. Open browser to `http://localhost:3001`
2. Click Coach Catalog button (📚)
3. Click each coach in turn:
   - Career Coach 💼
   - Personality Test Coach 🧠
   - PaDNA Coach 🧬
   - Photo Coach 📸
   - Relationship Coach 💞
   - Head Coach 🧭
4. Verify each click changes the active coach (check left sidebar)
5. Verify mode persists after page refresh

---

## Critical Success Factors

The fix required understanding that:

1. **Persona roster != Coach registry** - They're separate systems
2. **Frontend keys != Backend modes** - Normalization happens between them
3. **Fallback is not optional** - It's always used, even when registry works
4. **Both aliases must be supported** - Can't remove legacy IDs without breaking things
5. **Validation happens in 5 places** - All must pass for switching to work

---

## Contact Points for Future Issues

If coach switching breaks again, check these in order:

1. **Backend rejects the mode**: Check `VALID_MODES` in `coach_mode_manager.py`
2. **Frontend doesn't show the coach**: Check `_FALLBACK_PERSONAS` in `ui_readonly.py`
3. **Frontend shows but doesn't switch**: Check `PERSONA_ALIASES` in `api.ts`
4. **Clicking switches to wrong coach**: Check `normalizePersonaKey()` in `page-client.tsx`
5. **Mode doesn't persist**: Check backend mode file storage in `data/users/{user_id}/mode.json`

---

*This document summarizes the overnight batch work completed on 2025-10-06. All changes are in version control.*
