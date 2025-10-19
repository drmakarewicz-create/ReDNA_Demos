# Coach Switching Checklist - CRITICAL

## The Recurring Problem

**Coach switching breaks repeatedly.** Coaches appear in the catalog but clicking them does nothing - URL changes but UI stays on Head Coach.

**This happens because:**
1. Coaches must be registered in **7 DIFFERENT places**, and missing ANY of them causes silent failures
2. **ID normalization issues** - Backend sends `photo_coach`, frontend uses `photo` (inconsistent state causes PanelBoundary mismatches)

## The Normalization Rule (CHECK THIS FIRST!)

🚨 **CRITICAL INSIGHT from Oct 13, 2025:**

Backend sends IDs like `photo_coach` and `padna_coach`, but frontend must IMMEDIATELY normalize them to `photo` and `padna` when storing in `activePersona` state.

**Why:** `PanelBoundary` uses `resetKeys={[activePersona, ...]}` to trigger remounts. If `activePersona='photo_coach'` but components call `normalizePersonaKey('photo_coach')` which returns `'photo'`, the keys don't match and panels don't remount.

**The Fix:**
```typescript
// In handlePersonaChange() - MUST normalize before setting state
const normalizedPersona = normalizePersonaKey(newPersona);  // photo_coach -> photo
setActivePersona(normalizedPersona);  // Store normalized ID

// In URL sync effect - MUST normalize from URL params
const personaFromUrl = normalizePersonaParam(url.searchParams.get('persona'));
const normalizedPersona = normalizePersonaKey(personaFromUrl);  // Normalize!
setActivePersona(normalizedPersona);  // Store normalized ID
```

**Location:** `web/src/app/page-client.tsx` lines 1317-1329 and 1148-1155

**If Photo/PaDNA coaches don't work but others do → This is the issue.**

---

## The 7-Layer Checklist

When coaches appear in the catalog but won't switch, check THESE LAYERS IN ORDER:

### ✅ Layer 1: Backend Coach Catalog API
**Command:**
```bash
curl -s http://127.0.0.1:8015/ui/coach-catalog | python3 -c "import sys, json; data=json.load(sys.stdin); print('\\n'.join([f'{c[\"id\"]}' for c in data['coaches']]))"
```

**What to check:** List of all coach IDs returned by the backend.

**Example output:**
```
photo_coach
padna_coach
relationship_coach
head_coach
personality_test_coach
career_coach
chatdna_coach
beliefdna_coach
permission_coach
```

**What this tells you:** These are ALL the coaches the backend knows about. The frontend MUST have ALL of these in the next layers.

---

### ✅ Layer 2: Frontend CANONICAL_ORDER
**File:** `web/src/lib/api.ts`
**Line:** ~2482

**What to check:**
```typescript
const CANONICAL_ORDER = [
  'head_coach',
  'relationship_coach',
  'career_coach',        // ← Must include EVERY coach from Layer 1
  'personality_test_coach',
  'chatdna_coach',
  'beliefdna_coach',
  'padna',               // Note: backend sends padna_coach, frontend uses padna
  'photo',               // Note: backend sends photo_coach, frontend uses photo
  'permission_coach'
] as const;
```

**Critical Rule:** CANONICAL_ORDER must include EVERY coach from the backend catalog (Layer 1).

**Common mistake:** Backend adds a new coach but CANONICAL_ORDER isn't updated.

**Verification command:**
```bash
grep -A 20 "const CANONICAL_ORDER" web/src/lib/api.ts
```

---

### ✅ Layer 3: Frontend CANONICAL_DEFAULTS
**File:** `web/src/lib/api.ts`
**Line:** ~2495

**What to check:** Every coach in CANONICAL_ORDER must have an entry here:
```typescript
const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  head_coach: { key: 'head_coach', label: 'Head Coach', icon: '🧭', enabled: true },
  career_coach: { key: 'career_coach', label: 'Career Coach', icon: '💼', enabled: true },
  // ... MUST have entry for EVERY coach in CANONICAL_ORDER
};
```

**Critical Rule:** TypeScript will error if a coach is in CANONICAL_ORDER but missing from CANONICAL_DEFAULTS.

---

### ✅ Layer 4: Frontend PERSONA_ALIASES
**File:** `web/src/lib/api.ts`
**Line:** ~2561

**What to check:** All coach IDs and their variations must map to canonical keys:
```typescript
const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  career_coach: 'career_coach',      // Exact match
  'career coach': 'career_coach',    // Space variation
  career: 'career_coach',            // Short version
  // ... ALL variations for EVERY coach
};
```

**Critical Rule:** The backend sends IDs like `career_coach`. If `career_coach` isn't in PERSONA_ALIASES, the frontend will silently reject it.

**Common aliases needed:**
- `coach_name` → canonical
- `coach name` (with space) → canonical
- `shortname` → canonical
- Backend legacy ID → canonical (e.g., `photo_coach` → `photo`)

---

### ✅ Layer 5: normalizePersonaKey Return Type
**File:** `web/src/app/page-client.tsx`
**Line:** ~2684

**What to check:** TypeScript return type must include ALL coaches:
```typescript
function normalizePersonaKey(key: string):
  'head_coach' | 'relationship_coach' | 'career_coach' |
  'personality_test_coach' | 'chatdna_coach' | 'beliefdna_coach' |
  'padna' | 'photo' | 'permission_coach'
{
  // ...
}
```

**🚨 THIS IS THE #1 FAILURE MODE 🚨**

**Critical Rule:** If a coach is in CANONICAL_ORDER but NOT in this union type, TypeScript silently rejects it and falls back to `head_coach`.

**Why it's silent:** No compile error, no runtime error, just wrong behavior.

**Verification command:**
```bash
# Check CANONICAL_ORDER
grep "CANONICAL_ORDER = " web/src/lib/api.ts

# Check normalizePersonaKey return type
grep "function normalizePersonaKey" web/src/app/page-client.tsx

# They MUST match EXACTLY (accounting for padna_coach→padna, photo_coach→photo)
```

---

### ✅ Layer 6: normalizePersonaKey Switch Cases
**File:** `web/src/app/page-client.tsx`
**Line:** ~2686

**What to check:** Switch statement must handle ALL aliases:
```typescript
switch (normalized) {
  case 'career_coach':
  case 'career coach':
  case 'career':
    return 'career_coach';
  // ... cases for EVERY coach and EVERY alias
}
```

**Critical Rule:** Every coach must have a case for:
- Exact ID (`career_coach`)
- Space variation (`career coach`)
- Common abbreviations (`career`, `cc`)

---

### ✅ Layer 7: renderPersonaTools Cases
**File:** `web/src/app/page-client.tsx`
**Line:** ~2557

**What to check:** Switch must handle all coaches:
```typescript
switch (normalized) {
  case 'head_coach':
    return /* special tools */;
  case 'padna':
    return /* rendering tools */;
  case 'photo':
    return /* photo tools */;
  case 'relationship_coach':
  case 'career_coach':
  case 'personality_test_coach':
  case 'chatdna_coach':
  case 'beliefdna_coach':
  case 'permission_coach':
    return null;  // No special tools
  default:
    return null;
}
```

**Critical Rule:** EVERY coach must appear in this switch, even if returning `null`.

---

## Quick Diagnosis Flow

When coaches won't switch:

1. **Check backend** → `curl coach-catalog` → Get list of coach IDs
2. **Check CANONICAL_ORDER** → Does it include all backend coaches?
   - ❌ NO → **ADD THEM** (most common issue)
   - ✅ YES → Continue to step 3
3. **Check normalizePersonaKey return type** → Does union include all CANONICAL_ORDER coaches?
   - ❌ NO → **UPDATE RETURN TYPE** (second most common)
   - ✅ YES → Continue to step 4
4. **Check PERSONA_ALIASES** → Are all coach IDs mapped?
   - ❌ NO → **ADD ALIASES**
   - ✅ YES → Continue to step 5
5. **Check normalizePersonaKey switch** → Are all aliases handled?
   - ❌ NO → **ADD CASES**
   - ✅ YES → Continue to step 6
6. **Check CANONICAL_DEFAULTS** → Does every coach have an entry?
   - ❌ NO → **ADD ENTRY**
   - ✅ YES → Continue to step 7
7. **Check renderPersonaTools** → Does switch include coach?
   - ❌ NO → **ADD CASE**
   - ✅ YES → Check browser console for other errors

## The Pattern: Complete Example

When adding `new_coach`:

### 1. Backend returns `new_coach` in `/ui/coach-catalog`

### 2. Add to CANONICAL_ORDER:
```typescript
const CANONICAL_ORDER = [
  'head_coach',
  'new_coach',  // ← ADD HERE
  // ... other coaches
] as const;
```

### 3. Add to CANONICAL_DEFAULTS:
```typescript
const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  new_coach: {
    key: 'new_coach',
    label: 'New Coach',
    icon: '🎯',
    enabled: true,
    accent_color: null
  },
  // ... other coaches
};
```

### 4. Add to PERSONA_ALIASES:
```typescript
const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  new_coach: 'new_coach',
  'new coach': 'new_coach',
  newcoach: 'new_coach',
  nc: 'new_coach',
  // ... other coaches
};
```

### 5. Update normalizePersonaKey return type:
```typescript
function normalizePersonaKey(key: string):
  'head_coach' | 'new_coach' | /* ... other coaches */
{
```

### 6. Add to normalizePersonaKey switch:
```typescript
switch (normalized) {
  case 'new_coach':
  case 'new coach':
  case 'newcoach':
  case 'nc':
    return 'new_coach';
  // ... other cases
}
```

### 7. Add to renderPersonaTools:
```typescript
switch (normalized) {
  case 'new_coach':
    return null;  // or return specialized tools
  // ... other cases
}
```

## Automated Verification Script

Create `web/scripts/verify-coaches.sh`:

```bash
#!/bin/bash

echo "=== Backend Coaches ==="
curl -s http://127.0.0.1:8015/ui/coach-catalog | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print('\\n'.join([c['id'] for c in data['coaches']]))"

echo ""
echo "=== Frontend CANONICAL_ORDER ==="
grep -A 20 "const CANONICAL_ORDER" web/src/lib/api.ts | grep "'" | sed "s/.*'\\([^']*\\)'.*/\\1/"

echo ""
echo "=== normalizePersonaKey Return Type ==="
grep "function normalizePersonaKey" web/src/app/page-client.tsx | \
  sed "s/.*): //;s/ {//" | tr '|' '\n' | sed "s/[' ]//g" | sort

echo ""
echo "⚠️  Compare these three lists - they MUST match (accounting for aliases)"
```

Run: `bash web/scripts/verify-coaches.sh`

## Why This Keeps Breaking

1. **7 disconnected layers** - No single source of truth
2. **Silent failures** - TypeScript doesn't error when types mismatch at runtime
3. **Backend/frontend drift** - Backend adds coaches, frontend isn't updated
4. **Normalization complexity** - `photo_coach` (backend) vs `photo` (frontend)

## The Real Fix (Future Work)

1. **Generate frontend config from backend** - Single source of truth
2. **Type-safe coach registry** - Shared TypeScript types between backend/frontend
3. **Runtime validation** - Error if coach in catalog but not in frontend config
4. **Automated sync check** - CI fails if backend/frontend coach lists diverge

## Last Resort: Full Reset

If all else fails, regenerate the entire coach config:

```bash
# 1. Get backend coaches
curl -s http://127.0.0.1:8015/ui/coach-catalog > /tmp/coaches.json

# 2. Manually update all 7 layers using this checklist

# 3. Verify
bash web/scripts/verify-coaches.sh

# 4. Test in browser
# - Open Coach Catalog
# - Click each coach
# - Verify URL updates: ?persona=coach_id
# - Verify chat panel clears (indicates remount)
# - Reload page → should stay on coach
```

## Emergency Contacts

- **Pattern docs:** `web/NORTHSTAR_PERSONA_SWITCHING_PATTERN.md`
- **Protocol:** `docs/ADDING_NEW_COACH_PROTOCOL.md`
- **This checklist:** `web/COACH_SWITCHING_CHECKLIST.md`

---

**Last updated:** October 2025
**Last broken:** October 13, 2025 (fixed in commit 911eddb)
**Times this has broken:** At least 4 times in 3 days

**For next time this breaks:** Follow this checklist layer by layer. DO NOT skip layers thinking "that's probably fine."
