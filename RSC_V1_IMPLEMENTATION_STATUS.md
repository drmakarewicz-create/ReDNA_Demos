# RSC Collaboration v1 — Implementation Status

**Date:** 2025-10-10
**Phase:** 5.B RSC Collaboration
**Status:** Core Backend Complete, UI Pending

---

## ✅ Completed Components

### 1. Message Schema & Storage ✅

**File:** [ReDNACoreDemo/agents/messages.py](ReDNACoreDemo/agents/messages.py) (~290 LOC)

**Implemented:**
- `RSCMessage` dataclass with all required fields
- Message types: `rsc_invite`, `rsc_accept`, `rsc_decline`, `rsc_brief`, `rsc_close`
- `RSCMessageStore` for inbox/sent operations
- Filtering by type, thread_id, expiry
- `send_message()` helper that writes to both sender's sent box and recipient's inbox
- Thread ID auto-generation for invites
- TTL expiry checking

**Storage Paths:**
- `data/users/{user_id}/agent/rsc_inbox.jsonl`
- `data/users/{user_id}/agent/rsc_sent.jsonl`

**Tests:** ✅ `test_send_invite_happy_path` passing

---

### 2. Policy & RSC Rules ✅

**File:** [ReDNACoreDemo/agents/policy.py](ReDNACoreDemo/agents/policy.py) (+60 LOC)

**Extended `AgentPolicy` with:**
```python
rsc_enabled: bool = False
rsc_partners_allow: List[str] = []
rsc_partners_deny: List[str] = []
```

**Added validation functions:**
- `can_send_rsc_message(from_policy, to_agent_id)` → (bool, reason)
- `can_receive_rsc_message(to_policy, from_agent_id)` → (bool, reason)

**Logic:**
1. Check RSC enabled
2. Check deny list (takes priority)
3. Check allow list (empty = allow all, populated = must be in list)

**Tests:** ✅ `test_policy_deny_rsc_disabled`, `test_policy_partner_allowlist`, `test_policy_partner_denylist` passing

---

### 3. DevX RSC API Endpoints ✅

**File:** [ReDNACoreDemo/devx/backend/rsc_api.py](ReDNACoreDemo/devx/backend/rsc_api.py) (~290 LOC)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/devx/api/agents/rsc/send` | Send RSC message with policy validation |
| GET | `/devx/api/agents/rsc/{user_id}/inbox?limit=N` | Get inbox messages |
| GET | `/devx/api/agents/rsc/{user_id}/sent?limit=N` | Get sent messages |
| POST | `/devx/api/agents/rsc/{user_id}/act` | Accept/decline/close message |

**Validation in `/send`:**
- ✅ Both users' RSC policies
- ✅ Partner allow/deny lists
- ✅ Audits to `data/telemetry/agents/agent_activity.jsonl`
- ⚠️ Consent checking (TODO: integrate with consent service)

**Audit Events:**
- `rsc_invite_sent`
- `rsc_invite_denied` (with reason + stage)
- `rsc_accept`, `rsc_decline`, `rsc_close`

**Registered:** ✅ Added to `devx/backend/api.py`

---

### 4. Comprehensive Test Suite ✅

**File:** [ReDNACoreDemo/tests/test_rsc_collaboration_v1.py](ReDNACoreDemo/tests/test_rsc_collaboration_v1.py) (~250 LOC)

**Test Coverage:**
- ✅ Happy path (invite → accept)
- ✅ Policy deny (RSC disabled)
- ✅ Partner allowlist enforcement
- ✅ Partner denylist enforcement
- ✅ Message expiry filtering
- ✅ Accept/decline workflow
- ✅ Thread filtering
- ✅ Message type filtering

**Results:** All unit tests passing (8/8)

---

## 🚧 Pending Components

### 5. Agent Daemon RSC Hooks (Not Started)

**File:** `ReDNACoreDemo/core/agent_daemon.py` (+120–180 LOC needed)

**Required Implementation:**

```python
def _process_rsc_messages(self, user_id: str, policy: AgentPolicy, state: AgentState) -> List[AgentJob]:
    """
    Drain inbound RSC messages and convert to local jobs.

    - invite → check policy/consent → enqueue rsc_draft job + send accept/decline
    - brief → store to outbox + audit
    - close → finalize thread + audit
    - Expire old invites (send decline with reason="expired")
    """
    store = RSCMessageStore(user_id)
    inbox = store.read_inbox(include_expired=False)

    jobs = []
    for msg in inbox:
        if msg.type == "rsc_invite":
            # Validate consent for namespaces in constraints
            # If pass: enqueue job + send rsc_accept
            # If fail: send rsc_decline with reason
            ...
        elif msg.type == "rsc_brief":
            # Store and audit
            ...
        elif msg.type == "rsc_close":
            # Finalize and audit
            ...

    return jobs
```

**Integration Point:**
Add call to `_process_rsc_messages()` in `AgentDaemon.run_once()` after inbox processing.

---

### 6. DevX Frontend — RSC API Client (Not Started)

**File:** `ReDNACoreDemo/devx/frontend/src/lib/rscApi.ts` (~140 LOC needed)

**Required Functions:**

```typescript
export interface RSCMessage {
  id: string
  type: 'rsc_invite' | 'rsc_accept' | 'rsc_decline' | 'rsc_brief' | 'rsc_close'
  from: string
  to: string
  timestamp: string
  ttl_seconds: number
  topic?: string
  constraints?: Record<string, any>
  payload?: Record<string, any>
  thread_id?: string
  in_reply_to?: string
}

export async function sendRSCMessage(payload: SendMessagePayload): Promise<{ok: boolean, message: RSCMessage}>
export async function getInbox(userId: string, limit?: number): Promise<{inbox: RSCMessage[], count: number}>
export async function getSent(userId: string, limit?: number): Promise<{sent: RSCMessage[], count: number}>
export async function actOnMessage(userId: string, messageId: string, action: string): Promise<{ok: boolean}>
```

---

### 7. RSC Console UI Component (Not Started)

**File:** `ReDNACoreDemo/devx/frontend/src/routes/agent-control/RSCConsole.tsx` (~400–500 LOC needed)

**Features:**

#### Inbox/Sent Tabs
- Filter pills: invites, briefs, open, closed, expired
- Message list with badges (type, status, partner, topic, timestamp)

#### Message Detail Pane
- Header: from/to, topic, TTL/expiry
- Constraints display (namespaces, max_tokens)
- Policy badges (allow_reply)
- Payload preview (for briefs)

#### Actions
- Accept / Decline buttons (call `/rsc/act`)
- Close thread button

#### Compose Drawer
- Partner picker (dropdown of allowed agents)
- Topic input
- Constraints editor (namespace selector)
- TTL slider
- Send button (call `/rsc/send`)

---

### 8. Integration into Head Coach Tab (Not Started)

**File:** `ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx`

**Integration:**

```typescript
{!isManual && configSummary?.rsc_enabled && (
  <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
    <div className="border-b border-gray-200 px-6 py-4">
      <h3 className="text-lg font-semibold text-gray-900">RSC Collaboration</h3>
      <p className="text-sm text-gray-600">
        Agent-to-agent messaging for collaborative workflows.
      </p>
    </div>
    <div className="px-2 py-4">
      <RSCConsole userId={userId} />
    </div>
  </div>
)}
```

**Condition:** Only show when `rsc_enabled: true` in policy (agency level ≥ 3).

---

### 9. Documentation (Not Started)

**File:** `ReDNACoreDemo/docs/AGENTIC_HC_RSC_V1_PHASE5B.md` (needed)

**Required Sections:**
1. Protocol overview
2. Message types & schemas
3. Policy model (enable, allow/deny lists)
4. Consent integration (placeholder for 5.C)
5. API reference
6. UI tour
7. Example workflows (invite → accept → brief → close)
8. Security & audit model
9. Integration notes

---

### 10. Roadmap & System State Updates (Not Started)

**Files:**
- `ReDNACoreDemo/docs/Benchmark_Roadmap_v4.0.md` → mark 5.B complete
- `docs/_system_state.json` → set `next_planned_benchmark: "5.C"`

---

## ✅ Verification Script (Ready to Use)

```bash
# 1) Enable RSC on both sides (L3 = Collaborative)
curl -s -X POST "http://localhost:8100/devx/api/users/USER1/agent/configure" \
  -H "Content-Type: application/json" \
  -d '{"level":3,"apply_defaults":true}' | jq .

curl -s -X POST "http://localhost:8100/devx/api/users/USER2/agent/configure" \
  -H "Content-Type: application/json" \
  -d '{"level":3,"apply_defaults":true}' | jq .

# 2) Send an invite from USER1 to USER2
curl -s -X POST "http://localhost:8100/devx/api/agents/rsc/send" \
  -H "Content-Type: application/json" \
  -d '{
    "from_user":"USER1",
    "to_user":"USER2",
    "type":"rsc_invite",
    "topic":"career_brief",
    "constraints":{"namespaces":["SkillDNA"]},
    "policy":{"allow_reply":true}
  }' | jq .

# 3) Check USER2 inbox
curl -s "http://localhost:8100/devx/api/agents/rsc/USER2/inbox?limit=10" | jq .

# 4) Check USER1 sent box
curl -s "http://localhost:8100/devx/api/agents/rsc/USER1/sent?limit=10" | jq .

# 5) USER2 accepts the invite
MESSAGE_ID=$(curl -s "http://localhost:8100/devx/api/agents/rsc/USER2/inbox?limit=1" | jq -r '.inbox[0].id')

curl -s -X POST "http://localhost:8100/devx/api/agents/rsc/USER2/act" \
  -H "Content-Type: application/json" \
  -d "{\"message_id\":\"$MESSAGE_ID\",\"action\":\"accept\"}" | jq .

# 6) Check audit log
tail -n 20 data/telemetry/agents/agent_activity.jsonl | grep rsc_
```

---

## 📊 Progress Summary

| Component | Status | LOC | Tests |
|-----------|--------|-----|-------|
| Message schema & storage | ✅ Complete | 290 | ✅ 8/8 |
| Policy RSC rules | ✅ Complete | 60 | ✅ 3/3 |
| DevX RSC API | ✅ Complete | 290 | ✅ Manual |
| Agent daemon hooks | ❌ Not Started | 0/180 | ❌ 0/2 |
| Frontend API client | ❌ Not Started | 0/140 | ❌ N/A |
| RSC Console UI | ❌ Not Started | 0/500 | ❌ 0/1 |
| HC Tab integration | ❌ Not Started | 0/20 | ❌ N/A |
| Documentation | ❌ Not Started | 0/800 | ❌ N/A |
| Roadmap updates | ❌ Not Started | 0/50 | ❌ N/A |

**Total Progress:** ~40% (640/1600 LOC)

---

## 🎯 Next Steps for Completion

### Immediate Priority (2–3 hours)

1. **Agent Daemon Integration** (~180 LOC)
   - Add `_process_rsc_messages()` to daemon
   - Convert invites to local jobs
   - Auto-respond with accept/decline
   - Handle expiry sweeps

2. **Frontend API Client** (~140 LOC)
   - Implement TypeScript client functions
   - Add error handling
   - Export interfaces

3. **RSC Console UI** (~500 LOC)
   - Build inbox/sent tabs
   - Message detail pane
   - Action buttons
   - Compose drawer

### Final Integration (1 hour)

4. **HC Tab Integration** (~20 LOC)
   - Conditional render when `rsc_enabled`
   - Pass userId prop
   - Refresh on config changes

5. **Documentation** (~800 LOC)
   - Protocol spec
   - API reference
   - UI tour with screenshots
   - Example workflows

6. **Roadmap Updates** (~10 min)
   - Mark 5.B complete
   - Set next_planned_benchmark to 5.C

---

## 🔐 Security & Audit

All implemented components properly audit to:
```
data/telemetry/agents/agent_activity.jsonl
```

**Audit Events Logged:**
- `rsc_invite_sent` (message_id, from/to, topic, thread_id)
- `rsc_invite_denied` (from/to, reason, stage)
- `rsc_accept`, `rsc_decline`, `rsc_close` (user_id, message_id, partner)

**Policy Enforcement:**
- ✅ RSC enabled check (both sides)
- ✅ Partner allow/deny lists
- ⚠️ Consent for sensitive namespaces (deferred to consent service integration)
- ⚠️ Capability tokens (deferred to capability middleware integration)

---

## 🧪 Test Results

```bash
$ python3 -m pytest ReDNACoreDemo/tests/test_rsc_collaboration_v1.py -v

test_send_invite_happy_path PASSED
test_policy_deny_rsc_disabled PASSED
test_policy_partner_allowlist PASSED
test_policy_partner_denylist PASSED
test_message_expiry PASSED
test_accept_decline_workflow PASSED
test_thread_filtering PASSED
test_message_type_filtering PASSED

8 passed in 0.04s
```

---

## 📝 Known Issues & Deferred Items

1. **Consent Integration:** Sensitive namespace checking in constraints is stubbed (TODO comment in `rsc_api.py`)
2. **Capability Middleware:** Not enforcing `agents.rsc.send`/`agents.rsc.read` scopes yet (needs middleware wrapper)
3. **Daemon Integration:** No background processing of RSC messages yet
4. **UI:** No frontend components built

All are addressable in the remaining 40% of implementation work.

---

**Status:** Backend Core Complete ✅ | UI & Integration Pending 🚧
**Next Handoff:** Complete daemon hooks + UI components → Full end-to-end workflow
