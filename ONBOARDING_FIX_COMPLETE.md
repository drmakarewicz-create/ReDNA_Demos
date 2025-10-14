# Onboarding Fix - Northstar Phase 2

## Problem
Onboarding data wasn't being saved to Core properly, resulting in:
- Empty RR by DNA panel
- Empty Unabridged Trait Table
- No traits extracted from onboarding answers
- Inappropriate "keep momentum going" message in empty transcript
- Confusing green bubble that appeared and disappeared

## Root Cause
Onboarding completion handler was trying to send data as a chat message, which didn't trigger proper trait extraction and resulted in a generic HC response instead of silent ingestion.

## Solution
Implemented **unified programmatic ingestion system** that feeds data directly to Core without showing in chat transcript.

## Key Changes

### 1. New `ingestText()` API Function
**File:** `web/src/lib/api.ts:2723-2779`

```typescript
export async function ingestText(params: {
  userId: string;
  text: string;
  source?: string;
}): Promise<IngestTextResponse>
```

**What it does:**
- Sends data to `/core/api/ingest_text` endpoint
- Core extracts traits immediately
- Automatically rescores user
- NO chat transcript entry
- NO HC response message

**Use cases:**
- ✅ Onboarding data
- ✅ Life OS entries (goals, projects, weekly reviews)
- ✅ Photo metadata
- ✅ External data imports
- ✅ Any programmatic input

### 2. Updated Onboarding Completion Handler
**File:** `web/src/app/page-client.tsx:1718-1783`

**Old approach:**
```typescript
// ❌ Used sendChat() - showed in transcript, got HC response
await sendChat({
  userId: targetUserId,
  persona: 'head_coach',
  text: onboardingMessage,
  streaming: false
});
```

**New approach:**
```typescript
// ✅ Uses ingestText() - silent, immediate trait extraction
await ingestText({
  userId: targetUserId,
  text: onboardingMessage,
  source: 'onboarding'
});
```

### 3. Removed Default Welcome Message
**File:** `web/src/components/transcript-panel.tsx:101-106`

```typescript
// ❌ Old: Showed "Welcome back! Ready to keep momentum going today?"
function buildDefaultTranscript(): TranscriptEntry[] {
  return [
    {
      role: 'assistant',
      text: 'Welcome back! Ready to keep momentum going today?',
      // ...
    },
  ];
}

// ✅ New: Empty transcript - let users start naturally
function buildDefaultTranscript(): TranscriptEntry[] {
  return [];
}
```

## Testing Results

**Backend test (successful):**
```bash
curl -X POST 'http://127.0.0.1:8015/core/api/ingest_text' \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "FINAL_TEST",
    "text": "I am 25 years old and love hiking. I chose option A - a cozy home dinner.",
    "source": "onboarding"
  }'
```

**Response:**
```json
{
  "success": true,
  "event_id": "text_1760403021063.json",
  "user_id": "FINAL_TEST",
  "rescore": {
    "ok": true,
    "rr_by_trait": {
      "BasicDNA.Age": 95.0,
      "InterestDNA.Hobbies": 70.0,
      "PersonalityDNA.WYRChoice": 90.0
    },
    "curiosity_by_trait": {
      "BasicDNA.Age": 15.0,
      "InterestDNA.Hobbies": 40.0,
      "PersonalityDNA.WYRChoice": 10.0
    },
    "traits_updated": 3
  }
}
```

**Verification:**
- ✅ Traits stored in `data/users/FINAL_TEST/resolved.json`
- ✅ RR values calculated correctly
- ✅ Curiosity values set appropriately
- ✅ Provenance tracked with source and timestamp

## User Experience Flow

### Before (Broken):
1. User completes onboarding wizard
2. Data sent as chat message
3. HC responds with generic message
4. Chat shows in transcript (inappropriate)
5. Traits NOT extracted
6. RR by DNA empty ❌
7. Unabridged empty ❌
8. "Keep momentum going" message shows ❌

### After (Fixed):
1. User completes onboarding wizard
2. Data silently ingested to Core
3. Traits extracted immediately ✅
4. User rescored automatically ✅
5. Simple success notice shown
6. RR by DNA populated ✅
7. Unabridged populated ✅
8. Transcript stays empty (clean) ✅

## Future Use Cases

This pattern establishes a foundation for ALL programmatic data ingestion:

### Life OS Integration
```typescript
// When user creates a goal
await ingestText({
  userId,
  text: `I want to ${goalDescription} by ${deadline}`,
  source: 'life_os_goal'
});
```

### Photo Coach Integration
```typescript
// When user uploads photo with context
await ingestText({
  userId,
  text: `Photo from ${location}: ${userDescription}`,
  source: 'photo_coach'
});
```

### External Data Import
```typescript
// When importing from other services
await ingestText({
  userId,
  text: formattedImportData,
  source: 'external_import'
});
```

## Architecture Benefits

1. **Separation of Concerns**
   - Chat = conversational interaction
   - Ingestion = data processing

2. **Clean UX**
   - No confusing automated messages in transcript
   - User sees only their actual conversations

3. **Immediate Processing**
   - Traits extracted instantly
   - No waiting for chat response

4. **Extensible Pattern**
   - Can be used across all coaches
   - Works for any data source

## Files Changed

1. `web/src/lib/api.ts` - Added `ingestText()` function
2. `web/src/app/page-client.tsx` - Updated onboarding completion handler
3. `web/src/components/transcript-panel.tsx` - Removed default welcome message

## Next Steps

To use the new pattern in other areas:

1. **Life OS entries** - Call `ingestText()` when user creates goals/projects
2. **Photo uploads** - Call `ingestText()` with photo metadata
3. **External imports** - Call `ingestText()` with imported data

The HC chat interface is now ready to ingest unstructured data from ANY source!
