# Session Integrity System — Code Examples

Quick reference for key implementation patterns.

---

## 1. Building Augmented Context (Backend)

```python
from ReDNACoreDemo.core.head_coach.session_manager import build_augmented_context

# Build atomic context with versioning
context = build_augmented_context(
    user_id="TEST",
    active_coach_id="career_coach"
)

# Returns:
{
    "merged_prompt": "[HC mandate] + [Career Coach augmentation] + [Runtime hints]",
    "active_coach_id": "career_coach",
    "context_version": 42,          # ← Incremented on every build
    "cancel_token": "uuid-string",  # ← New UUID each time
    "behavior_context": {
        "features": {"tone": "Empathetic", "creativity": 70},
        "hints": {"tone": "empathetic", "creativity_bias": 0.7}
    },
    "telemetry": {
        "merged_hash": "f4e3d2c1",
        "build_ms": 8.92,
        "augmentations": ["career_coach"]  # ← Always 0 or 1 entry
    }
}
```

---

## 2. Validating Cancel Tokens (Backend)

```python
from ReDNACoreDemo.core.head_coach.session_manager import validate_request_token

# In chat response handler (streaming or non-streaming)
def handle_llm_response(user_id: str, response_token: str, response_text: str):
    # Validate token before processing
    if not validate_request_token(user_id, response_token):
        logger.debug(f"(ignored stale response) for {user_id}")
        return  # Discard silently — user switched coaches mid-response

    # Process response
    return response_text
```

**Example Log Output:**
```
[2025-10-09 14:22:19.123] DEBUG: Stale token detected for TEST: a1b2c3d4... != b2c3d4e5... (current v5)
[2025-10-09 14:22:19.124] DEBUG: (ignored stale response) — discarded LLM response with v4 token
```

---

## 3. Coach Mode Switch with Context Build (API)

```python
# In ReDNACoreDemo/core/api.py

@app.post("/users/{user_id}/coach-mode")
def switch_coach_mode(user_id: str, payload: dict = Body(...)):
    from core.coach_mode_manager import switch_mode_with_handoff
    from core.head_coach.session_manager import get_session_manager

    target_mode = payload.get("target_mode")

    # Step 1: Switch mode (updates coach_mode.json)
    result = switch_mode_with_handoff(
        user_id=user_id,
        target_mode=target_mode,
        data_dir=CORE_DATA_ROOT,
        delegation_id=payload.get("delegation_id"),
        context=payload.get("context", {})
    )

    if not result["success"]:
        return JSONResponse(content={
            "ok": False,
            "error": result.get("error")
        }, status_code=400)

    # Step 2: Build new context atomically (session.json)
    session_mgr = get_session_manager()
    context_packet = session_mgr.build_context(
        user_id=user_id,
        active_coach_id=target_mode,
        force_rebuild=True  # ← Always rebuild on switch
    )

    # Step 3: Return new session data
    return JSONResponse(content={
        "ok": True,
        "context_version": context_packet["context_version"],  # ← Frontend caches this
        "cancel_token": context_packet["cancel_token"],        # ← Frontend sends in requests
        **result
    }, status_code=200)
```

---

## 4. Frontend Coach Switcher (React)

```typescript
// In web/src/components/coach-switcher.tsx

const handleSwitch = async () => {
  // Cancel any in-flight request
  if (abortControllerRef.current) {
    abortControllerRef.current.abort()
  }

  const abortController = new AbortController()
  abortControllerRef.current = abortController

  setSwitching(true)
  setError(null)

  try {
    // Step 1: Create delegation
    const delegationResponse = await fetch(`${API_BASE}/delegation/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        coach_id: targetCoach,
        curiosity_targets: curiosityTargets,
      }),
      signal: abortController.signal,  // ← Cancelable
    })

    const delegationData = await delegationResponse.json()
    const delegationId = delegationData.delegation.delegation_id

    // Step 2: Switch mode (atomic context build)
    const modeResponse = await fetch(`${API_BASE}/users/${userId}/coach-mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_mode: targetCoach,
        delegation_id: delegationId,
      }),
      signal: abortController.signal,  // ← Cancelable
    })

    const modeData = await modeResponse.json()

    // Extract new session data
    const newContextVersion = modeData.context_version || 0
    const cancelToken = modeData.cancel_token || ""

    setContextVersion(newContextVersion)

    // Notify parent with new session credentials
    onSwitchComplete(delegationId, newContextVersion, cancelToken)

  } catch (err) {
    // Gracefully handle abort errors (user canceled)
    if (err instanceof Error && err.name === "AbortError") {
      console.log("Switch canceled by user")
      return
    }

    console.error("Switch error:", err)
    setError(err instanceof Error ? err.message : "Failed to switch coaches")
    setSwitching(false)
  }
}

// Debounced handler (300ms delay)
const handleSwitchDebounced = () => {
  if (debounceTimerRef.current) {
    clearTimeout(debounceTimerRef.current)
  }

  debounceTimerRef.current = setTimeout(() => {
    handleSwitch()
  }, SWITCH_DEBOUNCE_MS)
}

// Button click
<button onClick={handleSwitchDebounced} disabled={switching}>
  Switch to {targetInfo.name}
</button>
```

---

## 5. Session State Model (Data Structure)

```python
# SessionState class in session_manager.py

class SessionState:
    """
    Atomic session state for a user's Head Coach session.
    """
    def __init__(
        self,
        active_coach_id: str = "head_coach",   # Current augmentation
        context_version: int = 0,               # Incremented on every build
        merged_hash: str = "",                  # SHA-256 hash of merged prompt
        cancel_token: str = "",                 # UUID for request validation
        behavior_context: Dict[str, Any] = {},  # Runtime hints from feature state
        built_at: str = ""                      # ISO timestamp
    ):
        self.active_coach_id = active_coach_id
        self.context_version = context_version
        self.merged_hash = merged_hash
        self.cancel_token = cancel_token
        self.behavior_context = behavior_context
        self.built_at = built_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage in session.json."""
        return {
            "active_coach_id": self.active_coach_id,
            "context_version": self.context_version,
            "merged_hash": self.merged_hash,
            "cancel_token": self.cancel_token,
            "behavior_context": self.behavior_context,
            "built_at": self.built_at
        }
```

**Stored in:** `data/users/{user_id}/head_coach/session.json`

---

## 6. Telemetry Logging

```python
# In session_manager.py

def _log_telemetry(self, user_id: str, session: SessionState, build_ms: float):
    """Log telemetry for context build."""
    telemetry_file = CORE_DATA_ROOT.parent / "prompts" / "insights" / "session_integrity.jsonl"

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "active_coach_id": session.active_coach_id,
        "context_version": session.context_version,
        "augmentations": [session.active_coach_id] if session.active_coach_id != "head_coach" else [],
        "prompt_hash": session.merged_hash,
        "features": session.behavior_context.get("features", {}),
        "hints": session.behavior_context.get("hints", {}),
        "build_ms": round(build_ms, 2),
        "cancel_token": session.cancel_token[:8] + "..."  # Truncated for privacy
    }

    with telemetry_file.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')
```

**Example Entry:**
```json
{
  "ts": "2025-10-09T14:22:15.334Z",
  "user_id": "TEST",
  "active_coach_id": "career_coach",
  "context_version": 3,
  "augmentations": ["career_coach"],
  "prompt_hash": "f4e3d2c1b0a98765",
  "features": {"tone": "Empathetic", "creativity": 70},
  "hints": {"tone": "empathetic", "creativity_bias": 0.7},
  "build_ms": 8.92,
  "cancel_token": "a1b2c3d4..."
}
```

---

## 7. Thread-Safe Context Building

```python
# In session_manager.py

class SessionManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._locks: Dict[str, threading.Lock] = {}     # Per-user locks
        self._locks_lock = threading.Lock()              # Lock for locks dict

    def _get_lock(self, user_id: str) -> threading.Lock:
        """Get or create lock for user."""
        with self._locks_lock:
            if user_id not in self._locks:
                self._locks[user_id] = threading.Lock()
            return self._locks[user_id]

    def build_context(self, user_id: str, active_coach_id: str, force_rebuild: bool = False):
        """Build context atomically (thread-safe)."""
        lock = self._get_lock(user_id)

        with lock:  # ← Serialize all session operations for this user
            # Load current session
            current_session = self.get_session(user_id)

            # Build new context
            # ... (fetch mandate, merge prompt, increment version, etc.)

            # Save atomically
            self._save_session(user_id, new_session)

            return context_packet
```

**Concurrency Guarantee:**
- Per-user serialization (no race conditions on `context_version`)
- Cross-user parallelism (users don't block each other)
- Atomic read-modify-write (no partial updates)

---

## 8. Test Example (Cancel Token Validation)

```python
# In tests/test_session_integrity.py

def test_cancel_token_validation(session_manager, temp_data_dir):
    """Test cancel token validation."""
    user_id = "test_user_4"

    # Create user directories
    user_dir = temp_data_dir / "users" / user_id
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build initial context
    ctx1 = session_manager.build_context(user_id, "head_coach")
    token1 = ctx1["cancel_token"]

    # Token should be valid
    assert session_manager.validate_token(user_id, token1) is True

    # Build new context (invalidates old token)
    ctx2 = session_manager.build_context(user_id, "photo_coach", force_rebuild=True)
    token2 = ctx2["cancel_token"]

    # Old token should be invalid
    assert session_manager.validate_token(user_id, token1) is False

    # New token should be valid
    assert session_manager.validate_token(user_id, token2) is True
```

**Run:**
```bash
pytest ReDNACoreDemo/tests/test_session_integrity.py::test_cancel_token_validation -v
```

---

## 9. API Usage Examples

### Get Current Session

```bash
curl http://localhost:8000/users/TEST/hc-session
```

**Response:**
```json
{
  "ok": true,
  "session": {
    "active_coach_id": "career_coach",
    "context_version": 42,
    "cancel_token": "uuid-here",
    "built_at": "2025-10-09T14:22:15.334Z"
  }
}
```

### Build New Context

```bash
curl -X POST http://localhost:8000/users/TEST/hc-session/build \
  -H "Content-Type: application/json" \
  -d '{"active_coach_id": "career_coach", "force_rebuild": true}'
```

**Response:**
```json
{
  "ok": true,
  "context_version": 43,
  "cancel_token": "new-uuid-here",
  "active_coach_id": "career_coach",
  "telemetry": {
    "merged_hash": "abc123",
    "build_ms": 9.45,
    "augmentations": ["career_coach"]
  }
}
```

### Validate Token

```bash
curl -X POST http://localhost:8000/users/TEST/hc-session/validate-token \
  -H "Content-Type: application/json" \
  -d '{"cancel_token": "uuid-to-validate"}'
```

**Response:**
```json
{
  "ok": true,
  "valid": false,
  "current_version": 43
}
```

---

## 10. Edge Case Handling

### Double-Click Racing

```typescript
// Debounce prevents rapid clicks
const handleSwitchDebounced = () => {
  if (debounceTimerRef.current) {
    clearTimeout(debounceTimerRef.current)  // ← Cancel previous click
  }

  debounceTimerRef.current = setTimeout(() => {
    handleSwitch()  // ← Only executes after 300ms of inactivity
  }, 300)
}
```

### Streaming Response Cancellation

```python
# Pseudo-code for chat streaming endpoint

async def chat_stream(user_id: str, message: str, cancel_token: str):
    # Start streaming
    async for chunk in llm_provider.stream(message):
        # Before yielding each chunk, validate token
        if not validate_request_token(user_id, cancel_token):
            logger.debug(f"(stream canceled) — user switched coaches")
            break  # Stop streaming

        yield chunk
```

---

**End of Code Examples**
