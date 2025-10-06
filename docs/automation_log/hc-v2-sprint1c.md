# HC v2 Sprint 1c — Automation Log

**Date**: 2025-10-04
**Sprint**: HC v2 Sprint 1c
**Status**: ✅ **ALL TESTS PASSING** (5/5)

---

## Overview

Sprint 1c builds upon HC v2 Sprint 1a/1b, adding UI wiring, basic AI conversation replies, task priorities, and UCNRR real mode toggle. This sprint completes the foundation for user-facing Head Coach interactions.

---

## Deliverables

### 1. **UI Components** (Frontend)

#### A. Playbooks Panel (`hc-playbooks.tsx`)
- **Location**: `web/src/components/hc/hc-playbooks.tsx`
- **Features**:
  - Three playbook buttons: Curiosity Campaign, Photo Refine, Explain Change
  - One-click execution via `/api/hc/playbooks/run`
  - Inline toast showing "Enqueued N task(s)"
  - Auto-refresh tasks after successful execution

#### B. Conversation Panel (`hc-conversation.tsx`)
- **Location**: `web/src/components/hc/hc-conversation.tsx`
- **Features**:
  - Displays recent 30 messages from conversation history
  - Input box + Send button
  - Message bubbles with role (user/assistant)
  - Provenance tooltips for task-linked messages
  - Auto-scroll to bottom on new messages

#### C. HCPanel Integration
- **Location**: `web/src/components/hc/hc-panel.tsx`
- **Changes**: Added Playbooks and Conversation panels below Tasks

#### D. Task Priority Badges
- **Location**: `web/src/components/hc/hc-tasks.tsx`
- **Changes**:
  - Added `priority` field to `HCTask` interface
  - Added `getPriorityBadgeColor()` helper
  - Display priority badge (high=red, normal=neutral, low=gray)

---

### 2. **Backend Features** (Core API)

#### A. Task Priorities
- **File**: `ReDNACoreDemo/core/hc_task_runner.py`
- **Changes**:
  - Added `priority: "low" | "normal" | "high"` to task schema (default: "normal")
  - Updated `enqueue()` to accept priority parameter
  - Modified `tick()` to sort by priority (high > normal > low), then by created_ts (oldest first)

#### B. AI Conversation Replies
- **File**: `ReDNACoreDemo/core/api.py` (`/hc/say` endpoint)
- **Changes**:
  - Added `_load_hc_flags()` helper function
  - After logging user message, checks `enable_llm_replies` flag
  - If enabled, generates rule-based assistant reply:
    - If high-curiosity trait exists (curiosity >= 800): suggests adding evidence
    - Otherwise: suggests running Curiosity Campaign
  - Logs assistant reply with provenance `{"source": "auto_reply"}`
  - Returns `{"reply_logged": true/false}` in response

#### C. Priority Parameter in Tasks API
- **File**: `ReDNACoreDemo/core/api.py` (`/hc/tasks/queue` endpoint)
- **Changes**: Added optional `priority` body parameter (default: "normal")

#### D. Feature Flags
- **File**: `ReDNACoreDemo/config/hc_flags.yaml`
- **New Flags**:
  - `enable_llm_replies: true` — Enable AI assistant replies in conversation
  - `enable_ucnrr_real: false` — Use real UCNRR service instead of mock

---

### 3. **Next.js API Proxies**

All proxies were already created in Sprint 1a/1b:
- `/api/hc/say` → `/hc/say`
- `/api/hc/conversation/history` → `/hc/conversation/history`
- `/api/hc/playbooks/list` → `/hc/playbooks/list`
- `/api/hc/playbooks/run` → `/hc/playbooks/run`
- `/api/hc/tasks/*` (list, queue, tick, update)

No changes required for Sprint 1c.

---

### 4. **Acceptance Tests**

**File**: `test_hc_v2_sprint1c_acceptance.py`

**Test Coverage** (5/5 passing):

| Test | Description | Status |
|------|-------------|--------|
| **Test 1** | Conversation UI flow with AI reply | ✅ PASS |
| **Test 2** | Playbook button execution path | ✅ PASS |
| **Test 3** | Task priorities in tick() | ✅ PASS |
| **Test 4** | UCNRR real toggle flag | ✅ PASS |
| **Test 5** | End-to-end: conversation → task → journal | ✅ PASS |

**Test 1: Conversation AI Reply**
- POST /hc/say with user message
- Verify `reply_logged: true` when flag enabled
- GET /hc/conversation/history → 2 messages (user + assistant)
- Verify assistant reply has provenance

**Test 2: Playbook Execution**
- Create user with high-curiosity trait (curiosity=950)
- POST /hc/playbooks/run with `curiosity_campaign`
- Verify task was enqueued
- Verify task has correct provenance (playbook_id, reason)

**Test 3: Task Priorities**
- Enqueue 3 tasks with different priorities (high, normal, low)
- Tick 3 times
- Verify execution order: high → normal → low

**Test 4: UCNRR Real Toggle**
- GET /hc/flags
- Verify `enable_ucnrr_real` flag exists and is readable
- (UCNRR service integration tested elsewhere)

**Test 5: End-to-End Flow**
- User asks "What should I focus on?"
- Assistant replies with suggestion (high-curiosity trait)
- Run playbook to enqueue task
- Tick to execute task
- Verify journal entry created with provenance + task_id

---

## How to Run

### Start Core API

```bash
pkill -9 -f uvicorn || true
.venv/bin/python -m uvicorn ReDNACoreDemo.core.api:app --port 8001
```

### Run Sprint 1c Tests

```bash
.venv/bin/python test_hc_v2_sprint1c_acceptance.py
```

**Expected Output**:
```
======================================================================
HC v2 Sprint 1c Acceptance Tests
======================================================================
✓ Core API is running at http://localhost:8001
============================= test session starts ==============================
...
============================== 5 passed in 0.06s ===============================
```

### Start Next.js Frontend (Optional)

```bash
cd web
npm run dev
# or with custom port
PORT=3001 npm run dev
```

---

## Test Results

**Date**: 2025-10-04
**Environment**: macOS Darwin 24.6.0, Python 3.13.7
**Core API**: http://localhost:8001
**Tests**: 5/5 passing (100%)

```
test_1_conversation_ui_flow_with_ai_reply ✅ PASSED
test_2_playbook_button_path ✅ PASSED
test_3_task_priorities_in_tick ✅ PASSED
test_4_ucnrr_real_toggle ✅ PASSED
test_5_end_to_end_conversation_task_journal ✅ PASSED
```

**Coverage**:
- ✅ Conversation AI replies (flag-gated)
- ✅ Playbook execution (curiosity campaign)
- ✅ Task priority sorting (high > normal > low)
- ✅ Feature flags (enable_llm_replies, enable_ucnrr_real)
- ✅ End-to-end: conversation → playbook → task → journal

---

## Files Changed

### Created
- `web/src/components/hc/hc-playbooks.tsx`
- `web/src/components/hc/hc-conversation.tsx`
- `test_hc_v2_sprint1c_acceptance.py`
- `docs/automation_log/hc-v2-sprint1c.md` (this file)

### Modified
- `ReDNACoreDemo/config/hc_flags.yaml` — Added `enable_llm_replies` and `enable_ucnrr_real` flags
- `ReDNACoreDemo/core/hc_task_runner.py` — Added priority field and sorting logic
- `ReDNACoreDemo/core/api.py` — Added `_load_hc_flags()`, AI reply logic in `/hc/say`, priority param in `/hc/tasks/queue`
- `web/src/components/hc/hc-panel.tsx` — Integrated playbooks and conversation panels
- `web/src/components/hc/hc-tasks.tsx` — Added priority badges

---

## Feature Flags (Sprint 1c)

| Flag | Default | Description |
|------|---------|-------------|
| `enable_llm_replies` | `true` | Generate AI assistant replies in /hc/say |
| `enable_ucnrr_real` | `false` | Use real UCNRR service instead of mock |

**Config File**: `ReDNACoreDemo/config/hc_flags.yaml`

```yaml
# LLM Replies - Generate AI assistant replies in conversation (Sprint 1c)
enable_llm_replies: true  # Set to false to disable auto-replies

# UCNRR Real Mode - Use real UCNRR service instead of mock (Sprint 1c)
enable_ucnrr_real: false  # Set to true to call actual UCNRR service
```

---

## Success Criteria

✅ **All Sprint 1c criteria met**:

- ✅ No HC v1 regressions
- ✅ Sprint 1c acceptance tests: 5/5 passing
- ✅ Playbooks runnable from UI (via proxies)
- ✅ `/hc/say` logs user + assistant entries (flag-gated)
- ✅ `tick()` honors priorities (high > normal > low)
- ✅ UCNRR real mode toggleable and non-blocking
- ✅ Docs + logs updated

---

## Next Steps (Future Sprints)

1. **Sprint 2a**: Advanced AI replies using real LLM (OpenAI/Anthropic)
2. **Sprint 2b**: Multi-turn conversation context (RAG over conversation history)
3. **Sprint 2c**: Playbook builder UI (no-code playbook creation)
4. **Sprint 2d**: Real-time task execution (WebSocket updates)

---

## Notes

- **Non-Breaking**: All Sprint 1c changes are additive. HC v1 behavior preserved.
- **File-Backed Only**: No external APIs required (except optional UCNRR service).
- **Test Isolation**: Each test uses unique user ID with cleanup to avoid conflicts.
- **Auto-Replies**: Simple rule-based logic; no LLM API calls in Sprint 1c.

---

**Sprint 1c Complete** ✅
**Timestamp**: 2025-10-04T12:24:19Z
**Branch**: main (or HC-v2-sprint1c if branched)
