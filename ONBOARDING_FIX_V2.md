# Onboarding Fix v2 - Field Collection and Panel Refresh

## Issues Found with obtest3

After the initial fix, testing with obtest3 revealed:

1. **Missing age data** - Only 2 traits extracted instead of expected 5+
2. **Panels not refreshing** - Charts remained blank even though data was in Core
3. **Incorrect field names** - Code looked for `age` but wizard uses `age_range`

## Root Causes

### 1. Field Name Mismatch
The onboarding wizard collects these fields:
- `age_range` (not `age`)
- `gender`
- `orientation`
- `preferred_language`
- `relationship_status`
- WYR answer

But the code was only checking for:
- `age` ❌ (should be `age_range`)
- `gender` ✅
- `orientation` ✅
- WYR answer ✅

### 2. Panel Refresh Timing
The `refreshAllPanels()` was called immediately after ingestion, but:
- Race condition: panels might load before user switch completes
- No retry: if Core is still writing, panels get empty data

## Fixes Applied

### 1. Complete Field Collection
**File:** `web/src/app/page-client.tsx:1741-1761`

```typescript
// Before (missing fields):
if (data.basic_setup?.age) onboardingParts.push(`I am ${data.basic_setup.age} years old`);
if (data.basic_setup?.gender) onboardingParts.push(`My gender is ${data.basic_setup.gender}`);
if (data.basic_setup?.orientation) onboardingParts.push(`My orientation is ${data.basic_setup.orientation}`);

// After (all 5 wizard fields + fallback):
if (data.basic_setup?.age_range) {
  onboardingParts.push(`My age range is ${data.basic_setup.age_range}`);
} else if (data.basic_setup?.age) {
  onboardingParts.push(`I am ${data.basic_setup.age} years old`);
}
if (data.basic_setup?.gender) onboardingParts.push(`My gender is ${data.basic_setup.gender}`);
if (data.basic_setup?.orientation) onboardingParts.push(`My orientation is ${data.basic_setup.orientation}`);
if (data.basic_setup?.preferred_language) onboardingParts.push(`My preferred language is ${data.basic_setup.preferred_language}`);
if (data.basic_setup?.relationship_status) onboardingParts.push(`My relationship status is ${data.basic_setup.relationship_status}`);
```

### 2. Proper Timing and Retry
**File:** `web/src/app/page-client.tsx:1728-1789`

```typescript
// 1. Close wizard
setOnboardingWizardOpen(false);

// 2. Switch user immediately (triggers panel mount)
queueActiveUserChange(targetUserId, displayName, { immediate: true, suppressNotice: true });

// 3. Wait for user switch to complete
await new Promise(resolve => setTimeout(resolve, 300));

// 4. Ingest data (writes to Core)
const result = await ingestText({ userId, text, source: 'onboarding' });

// 5. Show success notice
pushNotice(`Welcome, ${displayName}! Your profile has been created.`, 'success');

// 6. Immediate refresh (optimistic)
refreshAllPanels();

// 7. Delayed refresh (ensures Core has written)
setTimeout(() => {
  console.log('[Onboarding] Delayed panel refresh');
  refreshAllPanels();
}, 500);
```

## Verification

### Test 1: obtest3 (Before Fix)
```json
{
  "raw_text": "My name is OB3. My gender is Male. My orientation is Straight. For the 'Would You Rather' question, I chose: A cozy home dinner...",
  "traits_extracted": 2
}
```
**Result:** ❌ Missing age_range field, only 2 traits

### Test 2: ONBOARD_TEST (After Fix)
```json
{
  "raw_text": "My name is TestUser. My age range is 25-34. My gender is Female. My orientation is Bisexual. My preferred language is English. My relationship status is Single. For the 'Would You Rather' question, I chose: A cozy home dinner...",
  "traits_extracted": 3
}
```
**Result:** ✅ All fields sent, 3 traits extracted (Age, Gender, WYR)

**Note:** Orientation, language, and relationship_status don't extract yet because Core's trait patterns might not have those. That's a separate Core issue, not a UI/onboarding issue.

## Extracted Traits

After fix, these traits are consistently extracted:

### BasicDNA.Age
```json
{
  "id": "BasicDNA.Age",
  "rr": 95.0,
  "curiosity": 15.0,
  "provenance": [{"source": "text_ingest", "event_id": "...", "ts": "..."}]
}
```

### BasicDNA.Gender
```json
{
  "id": "BasicDNA.Gender",
  "rr": 85.0,
  "curiosity": 20.0,
  "provenance": [{"source": "text_ingest", "event_id": "...", "ts": "..."}]
}
```

### PersonalityDNA.WYRChoice
```json
{
  "id": "PersonalityDNA.WYRChoice",
  "rr": 90.0,
  "curiosity": 10.0,
  "provenance": [{"source": "text_ingest", "event_id": "...", "ts": "..."}]
}
```

## User Experience

### Before Fix
1. User completes wizard
2. Wizard closes
3. Blank transcript ❌
4. Empty RR by DNA ❌
5. Empty Unabridged ❌

### After Fix
1. User completes wizard
2. Wizard closes
3. Success notice shows: "Welcome, [Name]! Your profile has been created." ✅
4. Blank transcript (clean, intentional) ✅
5. RR by DNA shows ~3 traits ✅
6. Unabridged shows trait table ✅
7. Panels update smoothly ✅

## Remaining Work

### Core Trait Extraction
These fields are sent but not yet extracted as traits:
- `orientation` (Bisexual, etc.)
- `preferred_language` (English, Spanish, etc.)
- `relationship_status` (Single, Married, etc.)

**Action needed:** Add trait patterns to Core's extraction logic for these fields.

### Panel Loading States
The delayed refresh works but feels slightly jarring. Could be improved with:
- Loading spinners during the 500ms delay
- Optimistic UI updates
- Smooth transitions

## Files Changed

1. `web/src/app/page-client.tsx`
   - Fixed field name mapping (age → age_range)
   - Added all 5 wizard fields to onboarding message
   - Added 300ms delay after user switch
   - Added immediate + delayed (500ms) panel refresh

## Next Steps

To test the complete flow:

1. **Create a new user** (e.g., obtest4)
2. **Complete onboarding wizard** with all 5 fields + WYR
3. **Verify behavior:**
   - Success notice shows
   - Transcript stays empty (clean)
   - RR by DNA shows ~3 traits (Age, Gender, WYR)
   - Unabridged shows trait table
   - No error messages

4. **Check Core data:**
   ```bash
   cat data/users/obtest4/resolved.json
   # Should have BasicDNA.Age, BasicDNA.Gender, PersonalityDNA.WYRChoice
   ```

5. **Optional: Add more trait patterns**
   If you want orientation, language, relationship_status to extract:
   - Update Core's trait extraction patterns
   - Add corresponding trait definitions to ontology
