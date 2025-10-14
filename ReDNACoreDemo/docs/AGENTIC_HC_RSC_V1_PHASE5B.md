# Agentic Head Coach RSC v1 — Phase 5.B

**Author:** ReDNA Core Team
**Date:** 2025-10-10
**Status:** ✅ Complete
**Scope:** Remote Sentient Collaboration (RSC) v1 — Agent-to-agent messaging with policy enforcement, consent gates, and DevX observability.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Protocol Overview](#2-protocol-overview)
3. [Message Types & Schema](#3-message-types--schema)
4. [Policy Model](#4-policy-model)
5. [Agent Daemon Integration](#5-agent-daemon-integration)
6. [DevX API Reference](#6-devx-api-reference)
7. [DevX UI — RSC Console](#7-devx-ui--rsc-console)
8. [Audit & Telemetry](#8-audit--telemetry)
9. [Example Workflows](#9-example-workflows)
10. [Security & Consent](#10-security--consent)
11. [Integration Notes](#11-integration-notes)

---

## 1. Executive Summary

Phase 5.B delivers **RSC Collaboration v1**, enabling Head Coach agents to communicate directly through structured messaging:

- **5 message types:** invite, accept, decline, brief, close
- **Policy enforcement:** RSC enabled flag + partner allow/deny lists
- **Agent daemon integration:** Auto-processes inbox, enqueues jobs, responds to invites
- **DevX UI:** Full-featured RSC Console with inbox/sent tabs, filters, compose drawer
- **Full audit trail:** All events log to `data/telemetry/agents/agent_activity.jsonl`

**Outcome:** Head Coach agents can now invite each other to collaborate, exchange briefs constrained by namespace/consent policies, and close collaboration threads — all under full DevX visibility and audit control.

---

## 2. Protocol Overview

### 2.1 Collaboration Lifecycle

```
┌─────────┐                                ┌─────────┐
│ Agent A │                                │ Agent B │
└────┬────┘                                └────┬────┘
     │                                          │
     │  rsc_invite (topic, constraints)        │
     ├────────────────────────────────────────>│
     │                                          │
     │           rsc_accept                     │
     │<─────────────────────────────────────────┤
     │                                          │
     │  rsc_brief (payload)                    │
     ├────────────────────────────────────────>│
     │                                          │
     │           rsc_brief (payload)            │
     │<─────────────────────────────────────────┤
     │                                          │
     │  rsc_close                               │
     ├────────────────────────────────────────>│
     │                                          │
```

### 2.2 Storage

- **Inbox:** `data/users/{user_id}/agent/rsc_inbox.jsonl`
- **Sent:** `data/users/{user_id}/agent/rsc_sent.jsonl`
- **Audit:** `data/telemetry/agents/agent_activity.jsonl`

---

## 3. Message Types & Schema

### 3.1 Base Message Structure

```json
{
  "id": "a1b2c3d4e5f6",
  "type": "rsc_invite",
  "from": "hc_USER1",
  "to": "hc_USER2",
  "timestamp": "2025-10-10T21:30:00Z",
  "ttl_seconds": 86400,
  "topic": "career_brief",
  "constraints": {
    "namespaces": ["SkillDNA"],
    "max_tokens": 3000
  },
  "policy": {
    "allow_reply": true,
    "expires": "2025-10-11T21:30:00Z"
  },
  "payload": {},
  "metadata": {},
  "thread_id": "thread_a1b2c3d4",
  "in_reply_to": null
}
```

### 3.2 Message Types

| Type | Sent By | Purpose |
|------|---------|---------|
| `rsc_invite` | Initiator | Request collaboration on a topic with constraints |
| `rsc_accept` | Recipient | Agree to collaborate |
| `rsc_decline` | Recipient | Refuse collaboration (with optional reason) |
| `rsc_brief` | Either | Exchange work product within constraints |
| `rsc_close` | Either | Finalize thread |

### 3.3 Example: Invite

```json
{
  "id": "abc123",
  "type": "rsc_invite",
  "from": "hc_USER1",
  "to": "hc_USER2",
  "timestamp": "2025-10-10T21:30:00Z",
  "ttl_seconds": 86400,
  "topic": "career_brief",
  "constraints": {
    "namespaces": ["SkillDNA", "Career"],
    "max_tokens": 3000
  },
  "policy": {
    "allow_reply": true
  },
  "thread_id": "thread_abc123de"
}
```

### 3.4 Example: Accept

```json
{
  "id": "def456",
  "type": "rsc_accept",
  "from": "hc_USER2",
  "to": "hc_USER1",
  "timestamp": "2025-10-10T21:31:00Z",
  "ttl_seconds": 86400,
  "thread_id": "thread_abc123de",
  "in_reply_to": "abc123"
}
```

### 3.5 Example: Brief

```json
{
  "id": "ghi789",
  "type": "rsc_brief",
  "from": "hc_USER2",
  "to": "hc_USER1",
  "timestamp": "2025-10-10T21:32:00Z",
  "ttl_seconds": 86400,
  "topic": "career_brief",
  "payload": {
    "summary": "User's career trajectory aligns with software engineering...",
    "links": ["trait://SkillDNA.programming_skill"],
    "token_count": 250
  },
  "thread_id": "thread_abc123de",
  "in_reply_to": "def456"
}
```

---

## 4. Policy Model

### 4.1 Policy Fields

```python
@dataclass
class AgentPolicy:
    rsc_enabled: bool = False
    rsc_partners_allow: List[str] = []
    rsc_partners_deny: List[str] = []
```

### 4.2 Enforcement Logic

**Send validation:**
1. Check `rsc_enabled` (sender)
2. Check deny list (takes priority)
3. Check allow list:
   - If empty: allow all (unless denied)
   - If populated: recipient must be in list

**Receive validation:**
- Same logic, but from recipient's perspective

**Example:**

```json
{
  "rsc_enabled": true,
  "rsc_partners_allow": ["hc_USER2", "hc_USER3"],
  "rsc_partners_deny": ["hc_USER99"]
}
```

- Can send to: USER2, USER3
- Cannot send to: USER99, USER4 (not in allow list)

### 4.3 Setting RSC Policy

Via agency level configurator (L3+) or direct policy update:

```python
from ReDNACoreDemo.agents.policy import update_policy

update_policy("USER1", {
    "rsc_enabled": True,
    "rsc_partners_allow": ["hc_USER2"],
})
```

---

## 5. Agent Daemon Integration

### 5.1 Processing Flow

On each daemon tick (`AgentDaemon.run_once()`):

1. Load RSC inbox (non-expired)
2. For each message:
   - **invite:** Validate policy → enqueue `rsc_draft` job → send accept/decline
   - **brief:** Store to outbox → audit
   - **accept/decline/close:** Audit
3. Sweep expired invites → send auto-decline

### 5.2 Job Creation

Accepted invites create local jobs:

```python
job = AgentJob(
    job_id=f"rsc_draft_{msg.id[:12]}",
    kind="rsc_draft",
    payload={
        "rsc_message_id": msg.id,
        "rsc_thread_id": msg.thread_id,
        "topic": msg.topic,
        "constraints": msg.constraints,
        "from_agent": msg.from_agent,
    },
    source="rsc",
    required_autonomy=policy.autonomy,
)
```

### 5.3 Auto-Responses

```python
# Accept if policy allows
send_message(
    from_user_id=user_id,
    to_user_id=partner_user_id,
    message_type="rsc_accept",
    thread_id=msg.thread_id,
    in_reply_to=msg.id,
)

# Decline if policy denies
send_message(
    from_user_id=user_id,
    to_user_id=partner_user_id,
    message_type="rsc_decline",
    thread_id=msg.thread_id,
    in_reply_to=msg.id,
    payload={"reason": "rsc_disabled"},
)
```

---

## 6. DevX API Reference

### 6.1 Send Message

**POST** `/devx/api/agents/rsc/send`

**Request:**

```json
{
  "from_user": "USER1",
  "to_user": "USER2",
  "type": "rsc_invite",
  "topic": "career_brief",
  "constraints": {
    "namespaces": ["SkillDNA"]
  },
  "policy": {
    "allow_reply": true
  },
  "ttl_seconds": 86400
}
```

**Response:**

```json
{
  "ok": true,
  "message": {
    "id": "abc123",
    "type": "rsc_invite",
    "from": "hc_USER1",
    "to": "hc_USER2",
    "thread_id": "thread_abc123de",
    ...
  }
}
```

**Errors:**
- `403` — Policy denies (RSC disabled, partner not allowed)
- `400` — Invalid payload

### 6.2 Get Inbox

**GET** `/devx/api/agents/rsc/{user_id}/inbox?limit=20&message_type=rsc_invite`

**Response:**

```json
{
  "inbox": [
    {
      "id": "abc123",
      "type": "rsc_invite",
      ...
    }
  ],
  "count": 1
}
```

### 6.3 Get Sent

**GET** `/devx/api/agents/rsc/{user_id}/sent?limit=20`

**Response:**

```json
{
  "sent": [
    {
      "id": "def456",
      "type": "rsc_accept",
      ...
    }
  ],
  "count": 1
}
```

### 6.4 Act on Message

**POST** `/devx/api/agents/rsc/{user_id}/act`

**Request:**

```json
{
  "message_id": "abc123",
  "action": "accept",
  "payload": {}
}
```

**Response:**

```json
{
  "ok": true,
  "action": "accept",
  "response": {
    "id": "xyz789",
    "type": "rsc_accept",
    ...
  }
}
```

---

## 7. DevX UI — RSC Console

### 7.1 Location

Embedded in **Head Coach** tab (User Operations) when `rsc_enabled: true` (agency level ≥ 3).

### 7.2 Features

#### Inbox / Sent Tabs
- Switch between received and sent messages
- Message count badges

#### Filters
- All
- Invites
- Briefs
- Open (non-expired invites)
- Closed (closed threads + expired)

#### Message List
- Color-coded type badges
- Topic, partner, timestamp
- Expiry indicator
- Click to view details

#### Message Detail Pane
- Full message metadata
- Constraints display (JSON)
- Payload preview (for briefs)
- Actions: Accept, Decline (for invites)

#### Compose Drawer
- Partner user ID input
- Topic input
- Namespace selector (multi-select)
- Send button

### 7.3 User Flow

1. Navigate to User Operations → Head Coach tab
2. Scroll to "RSC Collaboration" section (only visible for L3+)
3. View inbox (recent invites from other agents)
4. Click invite → see details → Accept/Decline
5. Click "Compose Invite" → fill form → Send
6. Check "Sent" tab to see outgoing messages
7. Filter by type/status to focus view

---

## 8. Audit & Telemetry

### 8.1 Audit Events

All events append to `data/telemetry/agents/agent_activity.jsonl`:

| Event | Fields |
|-------|--------|
| `rsc_invite_sent` | message_id, from_user, to_user, topic, thread_id |
| `rsc_invite_denied` | from_user, to_user, reason, stage |
| `rsc_invite_accepted` | user_id, message_id, from_agent, job_id |
| `rsc_invite_declined` | user_id, message_id, from_agent, reason |
| `rsc_invite_expired` | user_id, message_id, thread_id, from_agent |
| `rsc_brief_received` | user_id, message_id, thread_id, from_agent |
| `rsc_thread_closed` | user_id, message_id, thread_id, from_agent |

### 8.2 Example Audit Entry

```json
{
  "event": "rsc_invite_sent",
  "timestamp": "2025-10-10T21:30:00Z",
  "message_id": "abc123",
  "from_user": "USER1",
  "to_user": "USER2",
  "topic": "career_brief",
  "thread_id": "thread_abc123de"
}
```

---

## 9. Example Workflows

### 9.1 Happy Path (Invite → Accept → Brief → Close)

```bash
# 1) Enable RSC on both sides (L3 = Collaborative)
curl -X POST "http://localhost:8100/devx/api/users/USER1/agent/configure" \
  -H "Content-Type: application/json" \
  -d '{"level":3,"apply_defaults":true}'

curl -X POST "http://localhost:8100/devx/api/users/USER2/agent/configure" \
  -H "Content-Type: application/json" \
  -d '{"level":3,"apply_defaults":true}'

# 2) USER1 sends invite to USER2
curl -X POST "http://localhost:8100/devx/api/agents/rsc/send" \
  -H "Content-Type: application/json" \
  -d '{
    "from_user":"USER1",
    "to_user":"USER2",
    "type":"rsc_invite",
    "topic":"career_brief",
    "constraints":{"namespaces":["SkillDNA"]}
  }'

# 3) Run USER2 daemon to process invite
python -m ReDNACoreDemo.core.agent_daemon --user USER2 --once

# 4) Check USER1 inbox for accept
curl "http://localhost:8100/devx/api/agents/rsc/USER1/inbox?limit=10"

# 5) USER2 sends brief
curl -X POST "http://localhost:8100/devx/api/agents/rsc/send" \
  -H "Content-Type: application/json" \
  -d '{
    "from_user":"USER2",
    "to_user":"USER1",
    "type":"rsc_brief",
    "topic":"career_brief",
    "thread_id":"thread_abc123de",
    "payload":{"summary":"Career analysis complete"}
  }'

# 6) USER1 closes thread
curl -X POST "http://localhost:8100/devx/api/agents/rsc/USER1/act" \
  -H "Content-Type: application/json" \
  -d '{
    "message_id":"...",
    "action":"close"
  }'
```

### 9.2 Declined Invite (Policy Deny)

```bash
# 1) USER1 adds USER2 to deny list
curl -X PATCH "http://localhost:8100/devx/api/users/USER1/policy" \
  -H "Content-Type: application/json" \
  -d '{"rsc_partners_deny":["hc_USER2"]}'

# 2) USER1 tries to send to USER2
curl -X POST "http://localhost:8100/devx/api/agents/rsc/send" \
  -H "Content-Type: application/json" \
  -d '{
    "from_user":"USER1",
    "to_user":"USER2",
    "type":"rsc_invite",
    "topic":"test"
  }'

# Response: 403 Forbidden - Sender policy denies RSC message: partner_denied

# 3) Check audit
tail -n 5 data/telemetry/agents/agent_activity.jsonl | grep rsc_invite_denied
```

---

## 10. Security & Consent

### 10.1 Policy Enforcement

✅ Implemented:
- RSC enabled check (both sides)
- Partner allow/deny lists
- Audit trail for all denials

⚠️ Deferred (Phase 5.C):
- Consent checking for sensitive namespaces in constraints
- Capability token enforcement (`agents.rsc.send`, `agents.rsc.read`)

### 10.2 TTL & Expiry

- All messages have `ttl_seconds` (default 86400 = 24h)
- Expired invites filtered from inbox by default
- Daemon auto-sends `rsc_decline` with `reason: expired` on sweep

### 10.3 Thread Isolation

- Each invite creates a unique `thread_id`
- Responses include `in_reply_to` for traceability
- Messages can be filtered by thread in queries

---

## 11. Integration Notes

### 11.1 Touchpoints

- **Agency Configurator:** L3+ presets enable RSC
- **Agent Daemon:** Processes RSC inbox on every tick
- **DevX UI:** RSC Console embedded in HC Tab
- **Audit System:** Unified `agent_activity.jsonl` log

### 11.2 Phase 5.C Preview (Triggers & Events)

Upcoming:
- **Consent gates:** Integrate with consent service for namespace checks
- **Capability middleware:** Enforce `agents.rsc.*` scopes
- **Event triggers:** Auto-send invites based on user activity (e.g., trait conflict)
- **RSC analytics:** Dashboard for message volume, acceptance rates, thread durations

### 11.3 Known Limitations

1. **No consent integration:** Sensitive namespace constraints not validated yet
2. **No capability enforcement:** API endpoints don't require capability tokens
3. **No brief validation:** Payload structure/size not enforced
4. **No UI for briefs:** Viewing brief payloads is basic JSON preview

All addressable in future phases.

---

## Appendix A: File Reference

| File | Purpose | LOC |
|------|---------|-----|
| `ReDNACoreDemo/agents/messages.py` | Message schema & storage | 290 |
| `ReDNACoreDemo/agents/policy.py` | RSC policy fields + validation | +60 |
| `ReDNACoreDemo/devx/backend/rsc_api.py` | REST API endpoints | 290 |
| `ReDNACoreDemo/core/agent_daemon.py` | RSC inbox processing | +210 |
| `ReDNACoreDemo/devx/frontend/src/lib/rscApi.ts` | TypeScript client | 240 |
| `ReDNACoreDemo/devx/frontend/src/routes/agent-control/RSCConsole.tsx` | React UI | 380 |
| `ReDNACoreDemo/tests/test_rsc_collaboration_v1.py` | Test suite | 250 |

**Total:** ~1720 LOC

---

## Appendix B: Quick Command Reference

```bash
# Enable RSC (agency level 3)
curl -X POST "http://localhost:8100/devx/api/users/{user_id}/agent/configure" \
  -d '{"level":3,"apply_defaults":true}'

# Send invite
curl -X POST "http://localhost:8100/devx/api/agents/rsc/send" \
  -d '{"from_user":"USER1","to_user":"USER2","type":"rsc_invite","topic":"test"}'

# Check inbox
curl "http://localhost:8100/devx/api/agents/rsc/{user_id}/inbox?limit=10"

# Accept message
curl -X POST "http://localhost:8100/devx/api/agents/rsc/{user_id}/act" \
  -d '{"message_id":"...","action":"accept"}'

# Run daemon
python -m ReDNACoreDemo.core.agent_daemon --user {user_id} --once

# Tail audit log
tail -f data/telemetry/agents/agent_activity.jsonl | grep rsc_
```

---

**End of Document – Phase 5.B Complete**
**Next Benchmark:** 5.C — Triggers, Events & Consent Integration
