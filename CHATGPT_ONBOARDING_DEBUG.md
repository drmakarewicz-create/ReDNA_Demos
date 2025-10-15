# ChatGPT Debug Prompt: Next.js Onboarding Chat Connection Issue

## Problem Summary
I have a Next.js frontend (port 3000) that connects to a FastAPI backend (port 8001). After completing user onboarding, the frontend tries to send the onboarding data as a chat message to the backend, but it's failing with "There was an issue connecting to your coach."

## System Architecture
- **Frontend**: Next.js 14 (http://localhost:3000)
- **Backend**: FastAPI/Uvicorn (http://127.0.0.1:8001)
- **LLM**: Ollama with Llama 3.1 8B (local, can be slow)
- **Environment**: macOS, Python 3.13

## What's Working
✅ Backend health check: `curl http://127.0.0.1:8001/health` returns 200
✅ Frontend health check: `curl http://localhost:3000/api/health` returns `{"base":"http://127.0.0.1:8001","core":true}`
✅ Direct chat API test works:
```bash
curl -X POST http://127.0.0.1:8001/ui/chat/send \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","persona":"head_coach","text":"Hello","client_ts":1760600000000}' \
  --max-time 90
# Returns: {"message_id":"...", "text":"...", "ts":...} ✅
```
✅ Backend logs show successful processing of test messages
✅ Next.js dev server restarted and picking up correct environment variables

## What's Failing
❌ Onboarding completion chat fails in the browser
❌ User sees: "There was an issue connecting to your coach"
❌ No POST request appears in backend logs when onboarding completes

## Code Context

### Frontend: Onboarding Submission (page-client.tsx)
```typescript
// Line 1778-1818
// Send as chat message so Head Coach can respond naturally
try {
  const { sendChat } = await import('../lib/api');

  // Send onboarding data as a user message to Head Coach
  // Use longer timeout for Ollama (can take 60+ seconds)
  const abortController = new AbortController();
  const timeoutId = setTimeout(() => abortController.abort(), 90000); // 90 second timeout

  const result = await sendChat({
    userId: targetUserId,
    persona: 'head_coach',
    text: onboardingMessage,
    clientTs: Date.now()
  }, {
    signal: abortController.signal
  });

  clearTimeout(timeoutId);
  console.log('[Onboarding] Chat message sent, HC responded:', result);

  // Refresh panels to show updated traits and HC response
  refreshAllPanels();

} catch (chatError) {
  console.error('[Onboarding] Failed to send onboarding chat:', chatError);
  // Non-fatal - user is created, just show warning
  const isTimeout = chatError instanceof Error && chatError.name === 'AbortError';
  const message = isTimeout
    ? `Welcome, ${data.displayName || targetUserId}! (Your coach is taking longer than usual to respond - check back in a moment)`
    : `Welcome, ${data.displayName || targetUserId}! (There was an issue connecting to your coach)`;
  pushNotice(message, 'warning');
  refreshAllPanels();
}
```

### Frontend: sendChat API function (lib/api.ts)
```typescript
// Line 2213-2272
export async function sendChat(
  params: {
    userId: string;
    persona: string;
    text: string;
    clientTs: number;
    provider?: ChatProviderSettings;
  },
  options: SendChatOptions = {}
): Promise<ChatSendResponse> {
  const streamRequested = options.stream ?? false;
  const query = streamRequested ? '?stream=1' : '';
  let response: Response;
  try {
    const body: Record<string, unknown> = {
      user_id: params.userId,
      persona: params.persona,
      text: params.text,
      client_ts: params.clientTs
    };
    const providerPayload = buildProviderRequestPayload(params.provider);
    if (providerPayload) {
      body.provider = providerPayload;
    }
    response = await ensureOk(
      await fetch(`${CORE_API_BASE}/ui/chat/send${query}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: streamRequested ? 'text/event-stream' : 'application/json'
        },
        body: JSON.stringify(body),
        signal: options.signal
      })
    );
  } catch (error) {
    if (isApiError(error)) {
      throw error;
    }
    throw error;
  }

  if (streamRequested && isEventStream(response)) {
    return consumeEventStream(response, options.onDelta);
  }

  // Fallback to JSON response
  const payload = await response.json();
  const rawTs = Number(payload?.ts);
  return {
    message_id: String(payload?.message_id ?? ''),
    persona: String(payload?.persona ?? ''),
    text: String(payload?.text ?? ''),
    ts: Number.isFinite(rawTs) ? rawTs : Date.now(),
    provider: typeof payload?.provider === 'string' ? payload.provider : undefined,
    provider_settings: normalizeProviderSettings(payload?.provider_settings ?? payload?.providerSettings)
  };
}
```

### Environment Configuration (web/.env.local)
```bash
NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:8001
CORE_API_URL=http://127.0.0.1:8001
```

### API Base Constant (lib/api.ts, line 3)
```typescript
export const CORE_API_BASE = process.env.NEXT_PUBLIC_CORE_API_BASE ?? 'http://127.0.0.1:8015';
```

## Diagnostic Evidence
1. **Backend never receives the request** - No POST /ui/chat/send in logs when onboarding completes
2. **User is created successfully** - The onboarding data is saved, user directory exists
3. **Error is caught in try/catch** - The chatError is logged in browser console
4. **Direct curl works** - Backend can process chat messages when called directly
5. **Health check shows correct port** - Frontend knows to use port 8001

## Troubleshooting Already Done
- ✅ Restarted Next.js dev server (`pkill -f "next dev"` then `npm run dev`)
- ✅ Verified .env.local has correct port (8001)
- ✅ Confirmed CORE_API_BASE is loaded correctly in health endpoint
- ✅ Extended timeout to 90 seconds with AbortController
- ✅ Backend is running and responding to curl tests
- ✅ Killed all stale Next.js processes before restart

## Questions for ChatGPT

1. **Why would the fetch request fail in the browser but succeed via curl?**
   - Could it be CORS? (But health check works...)
   - Could it be a build cache issue?
   - Could Next.js still be using old code despite restart?

2. **How can I debug what error is actually in `chatError`?**
   - What properties should I log?
   - Could the error be from `ensureOk()` wrapper?

3. **Is there a Next.js build cache that needs clearing?**
   - Should I delete `.next` folder?
   - Do I need to run `npm run build` instead of `npm run dev`?

4. **Could the issue be with how environment variables are loaded?**
   - Does `NEXT_PUBLIC_*` work in client components during dev mode?
   - Should I hardcode the URL temporarily to test?

5. **What else should I check?**
   - Browser console errors/warnings?
   - Network tab to see if request is even attempted?
   - CORS headers on backend?
   - Next.js middleware intercepting requests?

## What I Need From You
Please help me identify:
1. Most likely root cause based on symptoms
2. Step-by-step debugging plan
3. How to log the actual error from the browser
4. Whether this is a Next.js caching issue or a runtime issue

## Additional Context
- This was working before, but we changed ports from 8015 → 8001
- The frontend was restarted but may still have cached something
- The onboarding form and user creation work fine
- Only the POST /ui/chat/send call fails
- No requests hit the backend (checked logs), so it fails before network call

---

## Browser Debugging Steps to Try First

Before sending to ChatGPT, try these diagnostics:

### 1. Check Browser Console
Open DevTools → Console and look for:
```javascript
[Onboarding] Failed to send onboarding chat: <ERROR_DETAILS>
```

### 2. Check Network Tab
- Open DevTools → Network
- Filter: "chat"
- Complete onboarding
- Look for POST request to `/ui/chat/send`
- Check: Status code, Response, Headers, Preview

### 3. Hard Refresh Browser
- Clear cache: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- Or manually: DevTools → Network → Disable cache checkbox

### 4. Check if .next cache needs clearing
```bash
cd web
rm -rf .next
npm run dev
```

### 5. Temporarily hardcode the URL
In `web/src/lib/api.ts` line 3, change:
```typescript
export const CORE_API_BASE = 'http://127.0.0.1:8001';  // Hardcoded for testing
```

Then restart Next.js and test again.

### 6. Add more detailed error logging
In `web/src/app/page-client.tsx` around line 1808, change:
```typescript
} catch (chatError) {
  console.error('[Onboarding] Failed to send onboarding chat:', chatError);
  console.error('[Onboarding] Error type:', typeof chatError);
  console.error('[Onboarding] Error name:', chatError?.name);
  console.error('[Onboarding] Error message:', chatError?.message);
  console.error('[Onboarding] Error stack:', chatError?.stack);
  console.error('[Onboarding] CORE_API_BASE:', CORE_API_BASE);  // Need to import this
  // ... rest of error handling
```

After trying these steps, copy the console output and network tab details into this document before sending to ChatGPT.

Thank you!
