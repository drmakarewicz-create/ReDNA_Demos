# Coach Switching Complete Fix - October 13, 2025

## Problem Summary

Coach switching in the Northstar UI was completely broken. Coaches appeared in the catalog but clicking them did nothing - URL would change but UI stayed on Head Coach.

## Root Causes (Two Separate Issues)

### Issue 1: Missing Coach Registrations
**Problem:** Backend had 9 coaches, frontend only registered 4.

**Why it broke:** Coaches must be registered in **7 different disconnected layers** in the frontend. Missing ANY layer causes silent failures.

### Issue 2: ID Normalization Inconsistency
**Problem:** Backend sends `photo_coach` and `padna_coach`, but frontend normalizes to `photo` and `padna`. Un-normalized IDs were stored in `activePersona` state.

**Why it broke:** `PanelBoundary` uses `resetKeys={[activePersona, ...]}` to detect changes and trigger remounts. When state held `"photo_coach"` but components used `normalizePersonaKey()` which returned `"photo"`, the keys didn't match, preventing panel remounts.

## Complete Solution

### Part 1: Register All 9 Coaches in 7 Frontend Layers

#### Layer 1: CANONICAL_ORDER (web/src/lib/api.ts ~line 2482)
```typescript
const CANONICAL_ORDER = [
  'head_coach',
  'relationship_coach',
  'career_coach',
  'personality_test_coach',
  'chatdna_coach',
  'beliefdna_coach',
  'padna',
  'photo',
  'permission_coach'
] as const;
```

#### Layer 2: CANONICAL_DEFAULTS (web/src/lib/api.ts ~line 2495)
```typescript
const CANONICAL_DEFAULTS: Record<CanonicalKey, PersonaRosterEntry> = {
  head_coach: { key: 'head_coach', label: 'Head Coach', icon: '🧭', enabled: true, accent_color: null },
  relationship_coach: { key: 'relationship_coach', label: 'Relationship Coach', icon: '💞', enabled: true, accent_color: null },
  career_coach: { key: 'career_coach', label: 'Career Coach', icon: '💼', enabled: true, accent_color: null },
  personality_test_coach: { key: 'personality_test_coach', label: 'Personality Test Coach', icon: '🧠', enabled: true, accent_color: null },
  chatdna_coach: { key: 'chatdna_coach', label: 'ChatDNA Coach', icon: '💬', enabled: true, accent_color: null },
  beliefdna_coach: { key: 'beliefdna_coach', label: 'BeliefDNA Coach', icon: '🔮', enabled: true, accent_color: null },
  padna: { key: 'padna', label: 'PaDNA Coach', icon: '🧬', enabled: true, accent_color: null },
  photo: { key: 'photo', label: 'Photo Coach', icon: '📸', enabled: true, accent_color: null },
  permission_coach: { key: 'permission_coach', label: 'Permission Coach', icon: '🔐', enabled: true, accent_color: null }
};
```

#### Layer 3: PERSONA_ALIASES (web/src/lib/api.ts ~line 2561)
```typescript
const PERSONA_ALIASES: Record<string, CanonicalKey> = {
  head_coach: 'head_coach',
  'head coach': 'head_coach',
  hc: 'head_coach',
  relationship_coach: 'relationship_coach',
  'relationship coach': 'relationship_coach',
  rc: 'relationship_coach',
  relationship: 'relationship_coach',
  career_coach: 'career_coach',
  'career coach': 'career_coach',
  career: 'career_coach',
  personality_test_coach: 'personality_test_coach',
  'personality test coach': 'personality_test_coach',
  ptc: 'personality_test_coach',
  chatdna_coach: 'chatdna_coach',
  'chatdna coach': 'chatdna_coach',
  chatdna: 'chatdna_coach',
  beliefdna_coach: 'beliefdna_coach',
  'beliefdna coach': 'beliefdna_coach',
  beliefdna: 'beliefdna_coach',
  padna: 'padna',
  padna_coach: 'padna',
  'padna coach': 'padna',
  rendering: 'padna',
  avatar: 'padna',
  photo: 'photo',
  photo_coach: 'photo',
  'photo coach': 'photo',
  permission_coach: 'permission_coach',
  'permission coach': 'permission_coach',
  permissions: 'permission_coach'
};
```

#### Layer 4: normalizePersonaKey Return Type (web/src/app/page-client.tsx ~line 2684)
```typescript
function normalizePersonaKey(key: string):
  'head_coach' | 'relationship_coach' | 'career_coach' |
  'personality_test_coach' | 'chatdna_coach' | 'beliefdna_coach' |
  'padna' | 'photo' | 'permission_coach'
{
  // Must include EVERY coach from CANONICAL_ORDER
```

⚠️ **This is the #1 failure mode.** If return type doesn't match CANONICAL_ORDER, TypeScript silently rejects coaches.

#### Layer 5: normalizePersonaKey Switch Cases (web/src/app/page-client.tsx ~line 2686)
```typescript
switch (normalized) {
  case 'head_coach':
  case 'head coach':
  case 'hc':
    return 'head_coach';
  case 'relationship_coach':
  case 'relationship coach':
  case 'rc':
    return 'relationship_coach';
  case 'career_coach':
  case 'career coach':
  case 'career':
    return 'career_coach';
  case 'personality_test_coach':
  case 'personality test coach':
  case 'ptc':
    return 'personality_test_coach';
  case 'chatdna_coach':
  case 'chatdna coach':
  case 'chatdna':
    return 'chatdna_coach';
  case 'beliefdna_coach':
  case 'beliefdna coach':
  case 'beliefdna':
    return 'beliefdna_coach';
  case 'padna':
  case 'padna_coach':
  case 'padna coach':
  case 'rendering':
  case 'avatar':
    return 'padna';
  case 'photo':
  case 'photo_coach':
  case 'photo coach':
    return 'photo';
  case 'permission_coach':
  case 'permission coach':
  case 'permissions':
    return 'permission_coach';
  default:
    return 'head_coach';
}
```

#### Layer 6: renderPersonaTools Switch (web/src/app/page-client.tsx ~line 2557)
```typescript
switch (normalized) {
  case 'head_coach':
    return /* head coach tools */;
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
    return null;  // No specialized tools
  default:
    return null;
}
```

#### Layer 7: PanelBoundary resetKeys (web/src/app/page-client.tsx ~line 2630)
```typescript
<PanelBoundary resetKeys={[context.activePersona, context.activeUser]} onRetry={...}>
  <TranscriptPanel ... />
</PanelBoundary>
```

Must include `activePersona` in resetKeys to trigger remount on coach change.

### Part 2: Normalize IDs Consistently in State

#### Issue: Photo/PaDNA Coaches Still Broken After Part 1

Even with all 7 layers configured, Photo Coach and PaDNA Coach didn't work.

**Root cause:** Backend sends `photo_coach`/`padna_coach`, but components expect normalized `photo`/`padna`. The `activePersona` state was storing un-normalized IDs, causing `PanelBoundary` resetKeys mismatch.

#### Solution: Normalize BEFORE Setting State

**handlePersonaChange (web/src/app/page-client.tsx ~line 1317):**
```typescript
const handlePersonaChange = useCallback((newPersona: string) => {
  // ✅ CRITICAL: Normalize BEFORE setting state
  const normalizedPersona = normalizePersonaKey(newPersona);  // photo_coach → photo

  // Update URL with normalized ID
  const url = new URL(window.location.href);
  url.searchParams.set('persona', normalizedPersona);
  const href = (url.pathname + url.search + url.hash) as Route;
  router.push(href, { scroll: false });

  // Update state with normalized ID
  setActivePersona(normalizedPersona);  // ✅ Stores "photo" not "photo_coach"
}, [router]);
```

**URL Sync Effect (web/src/app/page-client.tsx ~line 1148):**
```typescript
const personaFromUrl = normalizePersonaParam(url.searchParams.get('persona'));
if (personaFromUrl) {
  // ✅ CRITICAL: Normalize from URL before setting state
  const normalizedPersona = normalizePersonaKey(personaFromUrl);
  if (normalizedPersona !== activePersona) {
    setActivePersona(normalizedPersona);  // ✅ Stores normalized ID
  }
}
```

### Why Normalization Matters

**Before (broken):**
```
1. Backend sends: "photo_coach"
2. handlePersonaChange sets: activePersona = "photo_coach"
3. URL becomes: ?persona=photo_coach
4. PanelBoundary resetKeys: ["photo_coach", "user123"]
5. normalizePersonaKey("photo_coach") returns: "photo"
6. Component expects resetKeys: ["photo", "user123"]
7. Keys don't match → no remount → BROKEN
```

**After (fixed):**
```
1. Backend sends: "photo_coach"
2. normalizePersonaKey("photo_coach") returns: "photo"
3. handlePersonaChange sets: activePersona = "photo"
4. URL becomes: ?persona=photo
5. PanelBoundary resetKeys: ["photo", "user123"]
6. Component expects resetKeys: ["photo", "user123"]
7. Keys match → remount works → FIXED ✅
```

## Verification

### Automated Check
```bash
bash web/scripts/verify-coaches.sh
```

Expected output:
```
✅ Core API is running
=== BACKEND COACHES ===
[Lists 9 coaches]

=== FRONTEND CANONICAL_ORDER ===
[Lists 9 coaches]

=== normalizePersonaKey RETURN TYPE ===
[Lists 9 types]

✅ ALL CHECKS PASSED
```

### Manual Testing Checklist

Test **ALL 9 coaches**:

1. **Head Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=head_coach`
   - Coach Catalog button visible
   - Life OS panel visible

2. **Relationship Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=relationship_coach`
   - Chat clears (panel remount)

3. **Career Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=career_coach`

4. **Personality Test Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=personality_test_coach`

5. **ChatDNA Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=chatdna_coach`

6. **BeliefDNA Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=beliefdna_coach`

7. **Photo Coach** ✅ (Was broken, now fixed)
   - Click in catalog → Switches
   - URL: `?persona=photo` (NOT photo_coach)
   - Photo panel visible

8. **PaDNA Coach** ✅ (Was broken, now fixed)
   - Click in catalog → Switches
   - URL: `?persona=padna` (NOT padna_coach)
   - Rendering panels visible

9. **Permission Coach** ✅
   - Click in catalog → Switches
   - URL: `?persona=permission_coach`

### Reload Test
- Switch to any coach
- Reload page
- Should stay on that coach ✅

### Browser Navigation Test
- Switch between coaches
- Use browser Back button
- Should navigate between coaches correctly ✅

## Quick Fix Reference

**If coach switching breaks again:**

### Diagnosis
1. Run: `bash web/scripts/verify-coaches.sh`
2. Open: `web/COACH_SWITCHING_CHECKLIST.md`
3. Check normalization section FIRST
4. Follow 7-layer checklist systematically

### Common Issues

**Most coaches don't work:**
- Missing from CANONICAL_ORDER (Layer 1)
- Missing from normalizePersonaKey return type (Layer 4)

**Only Photo/PaDNA don't work:**
- Normalization issue in handlePersonaChange or URL sync

**One specific coach doesn't work:**
- Missing from PERSONA_ALIASES (Layer 3)
- Missing switch case in normalizePersonaKey (Layer 5)

## Files Modified

1. `web/src/lib/api.ts` - CANONICAL_ORDER, DEFAULTS, ALIASES
2. `web/src/app/page-client.tsx` - normalizePersonaKey, handlePersonaChange, URL sync

## Commits

1. `911eddb` - Added all 9 coaches to frontend config
2. `68f16c9` - Fixed normalization for Photo/PaDNA coaches
3. `355ba92` - Created comprehensive checklist
4. `05cd3a1` - Automated verification script
5. `3225ab8` - Updated checklist with normalization insights

## Documentation

- **[COACH_SWITCHING_CHECKLIST.md](web/COACH_SWITCHING_CHECKLIST.md)** - Diagnosis guide ⭐ Start here
- **[verify-coaches.sh](web/scripts/verify-coaches.sh)** - Automated verification
- **[NORTHSTAR_PERSONA_SWITCHING_PATTERN.md](web/NORTHSTAR_PERSONA_SWITCHING_PATTERN.md)** - State management
- **[ADDING_NEW_COACH_PROTOCOL.md](docs/ADDING_NEW_COACH_PROTOCOL.md)** - Backend protocol
- **This file** - Complete fix reference

## Summary

**Problem:** Coach switching completely broken (4+ times in 3 days)

**Root Cause:**
1. Missing registrations in 7 frontend layers
2. ID normalization inconsistency (photo_coach vs photo)

**Solution:**
1. Register all 9 coaches in all 7 layers
2. Normalize IDs immediately when setting state

**Result:** ✅ All 9 coaches now work reliably

**Prevention:** Comprehensive documentation + automated verification

---

**Last Updated:** October 13, 2025
**Status:** ✅ WORKING - All 9 coaches functional
**Next Time This Breaks:** Read `COACH_SWITCHING_CHECKLIST.md` first!
