# CRITICAL BUG: Trait Resolution Not Triggered from Chat

## The Problem

**Evidence is extracted but never converted to resolved traits with RR scores.**

### What's Broken

When a user sends a chat message:
1. ✅ Message is analyzed by `conversation_analyzer` and `preference_extractor`
2. ✅ Observations are extracted (age, gender, eye_color, etc.)
3. ✅ Evidence is stored via `hc_trait_bridge.store_observations()`
4. ✅ Evidence saved to `evidence.json`
5. ❌ **`resolve_traits()` is NEVER called**
6. ❌ `resolved.json` stays empty (only profile metadata)
7. ❌ RR scores never calculated
8. ❌ UI panels stay blank (no data to display)

### Evidence Found

**obtest5 evidence.json:**
```json
{
  "trait_id": "attributes.age",
  "value": 90,
  "confidence": 90,
  "fact_value": "45-54"
},
{
  "trait_id": "attributes.gender",
  "value": 90,
  "confidence": 100,
  "fact_value": "Male"
},
{
  "trait_id": "attributes.physical.eye_color",
  "value": 90,
  "confidence": 100,
  "fact_value": "blue"
}
```

**obtest5 resolved.json:**
```json
{
  "profile": {
    "label": "OB5",
    "created_ts": "2025-10-14T01:39:15..."
  }
  // ❌ NO TRAITS
}
```

## Root Cause Analysis

### The Missing Step

**File:** `ReDNACoreDemo/core/api.py`

**Chat endpoint (`/ui/chat/send`)** at line 2722:
```python
# Lines 2789-2823: Extract observations
all_observations = keyword_observations + llm_observations

# Store as evidence
items_stored = hc_trait_bridge.store_observations(
    user_id=user_id,
    observations=all_observations,
    timestamp=user_ts_iso,
    message_text=text
)

# ❌ resolve_traits() is NEVER called
# Chat endpoint ends without resolving evidence → traits
```

**Ingestion endpoint (`/ingest_bundle`)** at line 6148:
```python
# Lines 6172-6174: DOES call resolve_traits
(out, evidence, observations) = resolve_traits(
    prior_resolved, prior_evidence, prior_obs, new_obs
)

# ✅ This endpoint works correctly
# But onboarding uses chat endpoint, not ingest_bundle
```

### Why This Happened

The chat endpoint was designed to:
1. Extract observations
2. Store them as evidence
3. **Assume** resolve_traits() would be called later (batch job?)

But there's **no batch job** or automatic trigger. Evidence just sits there forever.

## Impact

### Affects All Chat-Based Ingestion

- ❌ Onboarding data (sent via chat)
- ❌ Regular chat messages ("I have blue eyes")
- ❌ Any trait extraction via conversation
- ❌ Life OS entries (if sent via chat)

### Works Only For

- ✅ `/core/api/ingest_text` endpoint (direct ingestion)
- ✅ `/ingest_bundle` endpoint (bundle imports)

## The Fix

Add `resolve_traits()` call to the chat endpoint immediately after storing evidence.

### Option 1: Synchronous Resolution (Recommended)

**Add to `/ui/chat/send` endpoint after line 2823:**

```python
# After storing observations as evidence
if all_observations:
    logger.info(f"Total extracted {len(all_observations)} observations")
    try:
        items_stored = hc_trait_bridge.store_observations(...)
        logger.info(f"Stored {items_stored} observations as evidence")

        # ✅ ADD THIS: Resolve evidence → traits with RR scores
        prior_resolved, prior_evidence, prior_obs = read_user_state(user_id)
        new_obs = build_observations(all_observations)
        (out, evidence, observations) = resolve_traits(
            prior_resolved, prior_evidence, prior_obs, new_obs
        )

        # Save resolved traits
        write_user_state(user_id, out["resolved"], evidence, observations)
        logger.info(f"Resolved {len(out['resolved'])} traits for user {user_id}")

    except Exception as e:
        logger.error(f"Failed to resolve traits: {e}", exc_info=True)
```

### Option 2: Async Background Resolution

- Pro: Chat response faster (doesn't wait for resolution)
- Con: Slight delay before traits appear in UI
- Con: More complex error handling

### Option 3: Separate Rescore Endpoint

- UI calls `/api/rescore` after each chat
- Pro: Decoupled, more flexible
- Con: Extra HTTP round-trip
- Con: UI has to remember to call it

## Recommendation

**Option 1 (Synchronous)** is best because:
1. Simple, reliable
2. Traits available immediately
3. No race conditions
4. Consistent with `/ingest_bundle` behavior
5. User sees instant feedback in panels

## Testing Plan

### Before Fix
```bash
# Create user, send chat
curl -X POST '/ui/chat/send' -d '{
  "user_id":"test_fix",
  "persona":"head_coach",
  "text":"I am 30 years old and have green eyes"
}'

# Check resolved.json
cat data/users/test_fix/resolved.json
# ❌ Only has profile, no traits
```

### After Fix
```bash
# Same test
curl -X POST '/ui/chat/send' -d '{
  "user_id":"test_fix",
  "persona":"head_coach",
  "text":"I am 30 years old and have green eyes"
}'

# Check resolved.json
cat data/users/test_fix/resolved.json
# ✅ Has Age and EyeColor traits with RR scores
```

### Full Integration Test
```bash
# Complete onboarding
# User: obtest6

# After onboarding:
cat data/users/obtest6/evidence.json
# Should have age, gender, orientation, relationship_status, eye_color

cat data/users/obtest6/resolved.json
# ✅ Should have BasicDNA.Age, BasicDNA.Gender, etc. with RR scores

# Check UI
curl '/ui/unabridged?user_id=obtest6'
# ✅ Should return traits list with RR scores

# RR by DNA panel should populate
# Unabridged table should show rows
```

## Files to Modify

1. **ReDNACoreDemo/core/api.py**
   - `/ui/chat/send` endpoint (line 2722)
   - Add resolve_traits() call after storing observations
   - Add write_user_state() to persist resolved traits

## Implementation Steps

1. Back up current ReDNACoreDemo/core/api.py
2. Add resolve_traits() call in chat endpoint
3. Test with new user
4. Verify evidence → resolved flow
5. Check UI panels populate
6. Test with "I have blue eyes" statement
7. Verify eye color trait appears in resolved.json

## Timeline

- **Complexity:** Medium (20-30 lines of code)
- **Risk:** Low (same pattern as /ingest_bundle)
- **Testing:** 15-20 minutes
- **Total:** ~1 hour to implement and verify

## Notes

This bug has been present since chat-based trait extraction was added. The `/ingest_text` endpoint works correctly, which is why our initial tests (using curl directly to `/core/api/ingest_text`) showed traits being created.

The switch from silent ingestion → conversational chat exposed this bug because chat endpoint doesn't call resolve_traits().

**Bottom line:** Evidence extraction works perfectly. The pipeline just stops one step too early. Adding resolve_traits() call will fix everything.
