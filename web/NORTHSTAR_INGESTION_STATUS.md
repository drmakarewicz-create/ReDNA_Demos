# Northstar Core Ingestion - Implementation Status

## Overview

Northstar Phase 2 implements unified Core ingestion for all user data (onboarding, goals, chat messages). This document tracks the implementation status.

## Architecture

```
User Action (Onboarding/Goal/Chat)
  ↓
Frontend: formatPayload()
  ↓
POST /core/api/ingest_text
  user_id, text, source
  ↓
Core: Store provenance event
  ↓
Core → UCN/RR: POST /api/rescore
  ↓
UCN/RR: Extract traits, calculate RR scores
  ↓
Core: Update resolved.json
  ↓
Frontend: GET /snapshot
  ↓
Frontend: Unabridged panel shows traits
```

## Implementation Status

### ✅ COMPLETE: Frontend Ingestion Layer

**Files:**
- `web/src/lib/hcIngestor.ts` - Ingestion functions
- `web/src/lib/coreSnapshot.ts` - Snapshot refresh
- `web/src/app/page-client.tsx` - Onboarding handler

**Functions:**
- ✅ `formatOnboardingPayload()` - Converts form data to natural language
- ✅ `formatGoalPayload()` - Converts goal to structured text
- ✅ `ingestToCore()` - POSTs to `/core/api/ingest_text`
- ✅ `refreshSnapshot()` - GETs latest resolved.json
- ✅ `ingestAndRefresh()` - Combined ingest + refresh

**Integration Points:**
- ✅ Onboarding: Calls `ingestAndRefresh()` on completion
- ✅ Goal Add: Calls `ingestAndRefresh()` when saving goal
- ✅ Chat: Calls `ingestToCore()` in background after sending message

**Fallback:**
- ✅ Falls back to legacy `submitOnboardingWizardData()` if Core fails
- ✅ Graceful degradation - user never sees infrastructure errors

### ✅ COMPLETE: Core API Endpoint

**File:** `ReDNACoreDemo/core/api.py` line 5243

**Endpoint:** `POST /core/api/ingest_text`

**Request:**
```json
{
  "user_id": "string",
  "text": "string",
  "source": "onboarding|chat|goal",
  "metadata": {}  // optional
}
```

**Response:**
```json
{
  "success": true,
  "event_id": "text_1697234567890",
  "user_id": "obtest",
  "rescore": {
    "ok": true|false,
    "traits_updated": 5
  }
}
```

**Implementation:**
- ✅ Endpoint exists and responds (HTTP 200)
- ✅ Stores provenance events in `data/users/{user_id}/events/`
- ✅ Calls UCN/RR `/api/rescore` endpoint
- ✅ Transforms response to Northstar format

**Testing:**
```bash
curl -X POST http://127.0.0.1:8000/core/api/ingest_text \
  -H "Content-Type: application/json" \
  -d '{"user_id":"TEST","text":"I am 25","source":"test"}'

# Returns: {"success":false,"error":"failed"}
# Core endpoint works (200 OK), UCN/RR returns 400
```

### ⚠️ BLOCKED: UCN/RR Integration

**Status:** UCN/RR `/api/rescore` returns 400 Bad Request

**Impact:**
- Provenance events are stored ✅
- Traits are NOT extracted ⚠️
- `resolved.json` is NOT updated ⚠️
- Unabridged panel stays empty ⚠️

**Root Cause:**
UCN/RR expects different payload format or has validation issues.

**Evidence:**
```
# Core log:
INFO: 127.0.0.1:51797 - "POST /core/api/ingest_text HTTP/1.1" 200 OK

# UCN/RR log:
INFO: 127.0.0.1:51798 - "POST /api/rescore HTTP/1.1" 400 Bad Request
```

**Next Step:**
Debug UCN/RR `/api/rescore` endpoint to understand expected payload format.

## Current Behavior

### What Works

1. **Onboarding Completes** ✅
   - User can complete onboarding wizard
   - Data is saved (fallback to legacy endpoint)
   - Welcome message shows
   - Can start chatting immediately

2. **Core Endpoint Responds** ✅
   - `/core/api/ingest_text` returns 200 OK
   - Provenance events are logged
   - Graceful error handling

3. **UI Works** ✅
   - No errors visible to user
   - Fallback prevents breakage
   - User experience is smooth

### What Doesn't Work

1. **Trait Extraction** ⚠️
   - UCN/RR doesn't process text
   - Traits don't populate from onboarding
   - Unabridged panel stays empty

2. **Immediate Profile Building** ⚠️
   - Profile doesn't build from onboarding answers
   - Requires chat interactions to populate
   - Slower initial experience

## Debugging UCN/RR Issue

### Check UCN/RR Directly

```bash
# Test UCN/RR endpoint directly
curl -X POST http://127.0.0.1:8011/api/rescore \
  -H "Content-Type: application/json" \
  -d '{"user_id":"TEST","text":"I am 25 years old"}' -v

# Check what payload Core is sending
tail -f /Users/davidmakarewicz/Documents/ReDNA_Demos/.run/core.log
```

### Expected UCN/RR Behavior

1. Receives: `{"user_id": "TEST", "text": "I am 25 years old"}`
2. Extracts traits: `[{"id": "age", "value": 25, ...}]`
3. Calculates RR scores for each trait
4. Returns: `{"ok": true, "rr_by_trait": {...}, "curiosity_by_trait": {...}}`

### Actual UCN/RR Behavior

Returns 400 Bad Request - payload validation failing or endpoint expects different format.

## Workaround (Current)

**Frontend Fallback:**
```typescript
// In page-client.tsx handleOnboardingComplete
try {
  const result = await ingestToCore(userId, payload, 'onboarding');
  if (result.success) {
    await refreshSnapshot(userId);
  } else {
    // Fall back to legacy endpoint
    await submitOnboardingWizardData(userId, data);
  }
} catch {
  // Fall back to legacy endpoint
  await submitOnboardingWizardData(userId, data);
}
```

This ensures onboarding always works, even if Core/UCN/RR has issues.

## TODO: Fix UCN/RR Integration

### Priority 1: Debug UCN/RR Payload

1. Check UCN/RR source code for `/api/rescore` expected format
2. Add detailed logging in Core before calling UCN/RR
3. Compare payload Core sends vs what UCN/RR expects
4. Fix payload format or UCN/RR validation

### Priority 2: Test Full Roundtrip

Once UCN/RR works:

1. Complete onboarding
2. Check `data/users/{user_id}/resolved.json` has traits
3. Verify Unabridged panel populates
4. Confirm snapshot API returns traits

### Priority 3: Remove Fallback

Once Core roundtrip is stable:

1. Remove fallback to `submitOnboardingWizardData()`
2. Update welcome message to reflect immediate trait extraction
3. Set `NEXT_PUBLIC_CORE_BYPASS_ALLOWED=false` in `.env`

## Commits

- `37e6a84` - Northstar Phase 2 main implementation
- `443f249` - Added fallback for missing Core endpoint
- `e6ed6d3` - Improved welcome message clarity
- `4182b66` - **Added /core/api/ingest_text endpoint** ⭐

## Summary

**Current State:**
- ✅ Frontend ingestion layer complete
- ✅ Core endpoint exists and works
- ⚠️ UCN/RR integration blocked (400 error)
- ✅ Fallback ensures onboarding works

**User Impact:**
- Onboarding works ✅
- Traits don't populate immediately ⚠️
- Acceptable for MVP - traits build through chat

**Next Step:**
Debug and fix UCN/RR `/api/rescore` endpoint payload validation.

---

**Last Updated:** October 13, 2025
**Status:** Core endpoint implemented, UCN/RR integration pending
