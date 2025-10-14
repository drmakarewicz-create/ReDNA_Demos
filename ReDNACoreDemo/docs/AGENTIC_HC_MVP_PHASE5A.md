# Agentic Head Coach Envelope — Phase 5.A MVP

**Author:** ReDNA Core Team  
**Date:** 2025-10-12  
**Status:** ✅ Complete  
**Scope:** Baseline implementation of the persistent, policy-bounded Head Coach agent capable of background execution, capability-gated actions, and DevX observability.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Registry & Policy Schema](#3-registry--policy-schema)
3a. [Agency Level Presets](#33-agency-level-presets)
4. [Mailbox & State Management](#4-mailbox--state-management)
5. [Agent Daemon](#5-agent-daemon)
6. [Capability Tokens & Consent Gates](#6-capability-tokens--consent-gates)
7. [DevX Agent Control Center](#7-devx-agent-control-center)
8. [CLI Utilities](#8-cli-utilities)
9. [Testing & Verification](#9-testing--verification)
10. [Operational Runbook](#10-operational-runbook)
11. [Telemetry & Observability](#11-telemetry--observability)
12. [Agent Activity Auditing](#12-agent-activity-auditing)
13. [Integration Notes & Next Steps](#13-integration-notes--next-steps)

---

## 1. Executive Summary

Phase 5.A introduces the first persistent Agentic Head Coach envelope:

- Each user now has a registry entry and policy governing autonomy, quotas, namespaces, and escalation rules.
- Mailbox infrastructure records inbound work and outbound results using append-only JSONL streams.
- Runtime state persists last/next run, job queues, failure history, and counters inside user-specific directories.
- The `AgentDaemon` executes curiosity, refinement, and self-improvement loops according to autonomy levels.
- Capability tokens enforce scope-specific access for sensitive operations (run, config).
- The DevX Agent Control Center provides live visibility and controls with <300 ms render time.
- A new pytest suite validates registry CRUD, policy updates, daemon behavior, capability lifecycles, API gating, and CLI flows (8 tests, <2 s runtime).

Outcome sentence: **Agentic Head Coach Envelope MVP implemented — per-user policy-bound agents now run background curiosity, refinement, and learning jobs with DevX control and full audit trail.**

---

## 2. Architecture Overview

### 2.1 Component Map

| Layer | Responsibilities | Key Modules |
|-------|-----------------|-------------|
| Persistence | Registry, policies, state, mailboxes | `ReDNACoreDemo/agents/registry.py`, `policy.py`, `state.py`, `mailbox.py` |
| Execution | Scheduling loop, quota & autonomy enforcement, telemetry | `ReDNACoreDemo/core/agent_daemon.py` |
| Security | Capability token issuance & verification, audit logging | `ReDNACoreDemo/core/agent_capabilities.py` |
| Interfaces | DevX API + UI, CLI workflows | `devx/backend/agent_api.py`, `devx/frontend/src/lib/agentApi.ts`, `AgentControlPanel.tsx`, `agents/cli.py` |
| Tests | Regression coverage for new capabilities | `ReDNACoreDemo/tests/test_agentic_hc_mvp.py` |

### 2.2 Data Flow

```
┌───────────────┐        enqueue jobs       ┌───────────────┐
│  AgentDaemon  │ ─────────────────────────>│ inbox.jsonl   │
└──────┬────────┘                           └───────────────┘
       │ run job results                       │ append results
       │                                       ▼
       │                                 ┌───────────────┐
       ├────────── telemetry            │ outbox.jsonl  │
       │                                 └───────────────┘
       ▼                                         ▲
┌───────────────┐      update status             │
│ state.json    │◄───────────────────────────────┘
└───────────────┘
```

Telemetry events from the daemon land in `data/telemetry/agents/*.jsonl`, while capability validation failures append to `data/audit/agent_capability_failures.jsonl`.

---

## 3. Registry & Policy Schema

### 3.1 Registry Structure

File: `ReDNACoreDemo/agents/registry.json`

```json
{
  "agents": [
    {
      "user_id": "USER1",
      "agent_id": "hc_USER1",
      "status": "enabled",
      "autonomy": "semi",
      "quotas": { "jobs_per_day": 50 },
      "permissions": {
        "namespaces": ["SkillDNA", "Career", "Core"],
        "sensitive": ["PsyDNA", "PaDNA"]
      },
      "created_at": "2025-10-12T00:00:00Z",
      "updated_at": "2025-10-12T00:00:00Z",
      "metadata": {
        "notes": "Phase 5.A baseline head coach agent"
      }
    }
  ],
  "updated_at": "2025-10-12T00:00:00Z"
}
```

Helper APIs:

```python
from ReDNACoreDemo import agents

record = agents.ensure_agent_record("USER42")
agents.update_agent_record("USER42", {"autonomy": "auto", "status": "enabled"})
```

Concurrency safety uses an in-process lock (`_REGISTRY_LOCK`). Each update rewrites the registry with deterministic ordering by `user_id`.

### 3.2 Policy Files

Per-user policies live in `ReDNACoreDemo/agents/policies/hc_<user_id>.json`. Schema:

- `autonomy`: `"propose" | "semi" | "auto"`
- `quotas.jobs_per_day`: integer maximum self-executing jobs per UTC day
- `permissions.namespaces`: accessible data namespaces
- `permissions.sensitive`: sensitive scopes requiring heightened logging/consent
- `escalation.manual_review`: scopes forcing manual handling even in auto mode
- `escalation.notify`: scopes that trigger notifications

Example:

```json
{
  "user_id": "USER1",
  "agent_id": "hc_USER1",
  "autonomy": "semi",
  "quotas": { "jobs_per_day": 50 },
  "permissions": {
    "namespaces": ["SkillDNA", "Career", "Core"],
    "sensitive": ["PsyDNA", "PaDNA"]
  },
  "escalation": {
    "manual_review": ["core.refinement.resolve"],
    "notify": ["sensitive.read"]
  }
}
```

Validation rules:

- Autonomy must be one of `propose`, `semi`, `auto`.
- `permissions.namespaces` cannot be empty when explicitly provided.
- Quotas must be integers; `jobs_per_day` defaults to 50.

`agents.update_agent_policy` synchronizes registry and policy files to keep autonomy consistent across both.

### 3.3 Agency Level Presets

A single configure endpoint (`POST /devx/api/users/{user_id}/agent/configure`) now applies bundled presets across policy, schedule, quotas, capability tokens, telemetry, and audit trails. The presets enable User Ops to shift automation envelopes without touching internals.

| Level | Name | Policy Highlights | Schedule / Quotas | Capabilities | Safeguards |
|-------|------|------------------|-------------------|--------------|-----------|
| L0 | Manual | Autonomy retired (`None`); automation disabled; consent stays fail-closed | Timers cancelled; quota `0` | Revoke all persisted tokens | Archive latest state to `quarantine/agents`; capability audit entry |
| L1 | Background | Autonomy `propose`; manual review for sensitive scopes | `interval_hours = 12`; quota `10` jobs/day | None persisted (per-job only) | Sensitive scopes fail closed; agent guaranteed to exist |
| L2 | Autonomous | Autonomy `auto`; self-improvement trivial auto-apply; refinement auto-accept threshold `0.75` | `interval_hours = 4`; quota `50` jobs/day | `core.agent.run` + `core.agent.config` tokens (≤60 min TTL) | Telemetry + audit diffs; tokens rotated on reapply |
| L3 | Collaborative | L2 settings + `rsc_enabled = true` | Same as L2 | L2 tokens + `agents.rsc.send` / `agents.rsc.read` scopes | RSC messaging scoped; downgrade requires confirmation |
| L4 | Delegated | L3 settings + workflow back-pressure + circuit breaker metadata | `interval_hours = 2`; quota `120` jobs/day | L3 tokens + `agents.workflow.{calendar,report,email}` | Dual-control flag, destructive workflow guardrails |

Re-applying a preset rotates capability tokens, refreshes `next_run`, and emits paired telemetry (`agent_config_change`) and audit (`agent_configured`) records. Downgrades (for example, L3 → L1 or L2 → L0) require an explicit `"confirm": "apply"` payload and automatically revoke previously issued tokens, cancel timers, and archive state snapshots.

---

## 4. Mailbox & State Management

### 4.1 Directory Layout

```
data/users/<user_id>/agent/
├── inbox.jsonl        # append-only inbound job queue
├── outbox.jsonl       # append-only job outputs
└── state.json         # runtime state snapshot
```

Templates mirrored in `ReDNACoreDemo/agents/state/hc_<user_id>.json` allow repo seeding.

### 4.2 State File

`state.json` tracks:

- `status`: `idle | running | disabled`
- `last_run` / `next_run`: ISO timestamps
- `pending_jobs`: array of job dictionaries with `status`, `queued_at`, `completed_at`, `result`
- `errors`: bounded error log (latest 20)
- `job_counts`: per-kind counters + `day_YYYYMMDD`
- `inbox_cursor` / `outbox_cursor`: last processed line indices
- `run_count`: total number of daemon invocations

State updates always rewrite both runtime and template copies.

### 4.3 Mailbox Operations

`AgentMailbox` exposes:

- `append_inbox(payload)` — ensures `job_id`, `queued_at`
- `append_outbox(payload)` — ensures `emitted_at`
- `read_inbox(limit, start_index)` / `read_outbox(...)` returning `(entries, next_index)`

The daemon advances `inbox_cursor` per run, preventing double-processing.

---

## 5. Agent Daemon

### 5.1 Execution Sequence

1. **Registry & Policy Load** — ensures agent record/policy exist.
2. **Inbox Harvest** — reads new inbox entries, logs `job_enqueued`.
3. **Curiosity Engine** — provider returns nudge candidates above threshold.
4. **Refinement Resolver** — provider returns refinement/resolve tasks.
5. **Self-Improvement Analyzer** — provider returns telemetry-driven jobs.
6. **Quota & Autonomy Enforcement** — checks daily quotas and mode before execution.
7. **Job Execution** — delegates to configurable executor, appends outbox results.
8. **Telemetry & State Persist** — emits `job_completed`/`job_failed`, updates state.

### 5.2 Autonomy Levels

| Level | Behavior |
|-------|----------|
| `propose` | Jobs are logged with `awaiting_manual` status; no execution. |
| `semi` | Executes low-risk jobs (`nudge`, `refine`) within quota. |
| `auto` | Executes all policy-approved jobs (including `resolve`, `analyze`). |

### 5.3 Daily Quotas

- Per-policy `jobs_per_day` limit enforced using state `job_counts["day_YYYYMMDD"]`.
- Quota exhaustion results in `quota_exceeded` outbox entries and telemetry `job_failed`.
- Quota resets occur when the day key changes (daemon recalculates on next run).

### 5.4 Telemetry Events

Emitted JSONL events live under `data/telemetry/agents/`:

- `agent_run`
- `job_enqueued`
- `job_completed`
- `job_failed`

Each entry includes `agent_id`, `user_id`, `job_id`, `kind`, `source`, and UTC timestamp.

### 5.5 CLI-Friendly Usage

```
python3 -m ReDNACoreDemo.core.agent_daemon --user USER1 --once
```

`--interval` controls loop duration when running as a persistent service.

---

## 6. Capability Tokens & Consent Gates

### 6.1 Token Format

Tokens are signed with HMAC-SHA256 (`AGENT_CAPABILITY_SECRET`, default `dev-agent-capability-secret`).

Logical payload:

```json
{
  "agent": "hc_USER1",
  "scope": "core.refinement.resolve",
  "exp": "2025-10-12T02:00:00Z",
  "issued_at": "2025-10-12T01:30:00Z",
  "user_id": "USER1",
  "metadata": {
    "issued_by": "devx-control-panel",
    "reason": "Run Now"
  }
}
```

Serialized token: `base64url(payload_json) + "." + base64url(signature)`.

### 6.2 Verification Rules

- Signature mismatch → 403 + audit entry (`capability_bad_signature`).
- Expired tokens → 403 + audit entry (`capability_expired`).
- Scope mismatch → 403 + audit entry (`capability_scope_mismatch`).
- User mismatch → 403 + audit entry (`capability_user_mismatch`).

Audit failures append to `data/audit/agent_capability_failures.jsonl` with timestamped records.

### 6.3 Issuance API (DevX-only)

```
POST /devx/api/agents/{user_id}/capability
Headers: x-devx-auth: <admin token>
Body: { "scope": "core.agent.run", "ttl_seconds": 900 }
```

Response returns both token string and payload metadata. Default admin token is `devx-local`, override via `DEVX_AGENT_ADMIN_TOKEN`.

---

## 7. DevX Agent Control Center

### 7.1 Frontend Overview

File: `devx/frontend/src/routes/agent-control/AgentControlPanel.tsx`

Features (<300 ms render target):

- Agent roster with status, autonomy, job counts.
- Context panel showing last/next run, pending jobs, quota usage.
- Autonomy dropdown switching between `propose`, `semi`, `auto`.
- Start/Stop controls tied to capability token `core.agent.config`.
- “Run Now” button using `core.agent.run` capability.
- Live Inbox/Outbox JSON tables (latest entries).
- Mailbox refresh + detail reload controls.
- Toast notifications for operations and errors.

`agentApi.ts` wraps backend endpoints and handles capability issuance, including fallback admin token detection via `import.meta` (with safe cast).

### 7.2 Backend Endpoints

`devx/backend/agent_api.py` exposes:

| Method | Path | Description | Capability |
|--------|------|-------------|------------|
| GET | `/devx/api/agents` | List registry entries with state summary | n/a |
| GET | `/devx/api/agents/{user_id}` | Detailed snapshot (record, policy, state, mailbox) | n/a |
| POST | `/devx/api/agents/{user_id}/run` | Trigger daemon once | `core.agent.run` |
| POST | `/devx/api/agents/{user_id}/autonomy` | Update autonomy mode | `core.agent.config` |
| POST | `/devx/api/agents/{user_id}/status` | Enable/disable agent | `core.agent.config` |
| GET | `/devx/api/agents/{user_id}/mailbox` | Tail inbox/outbox | n/a |
| POST | `/devx/api/agents/{user_id}/capability` | Issue capability token (DevX admin only) | `x-devx-auth` |

Responses include run summaries mirroring the CLI output for consistency.

### 7.3 Screenshot

See `docs/images/agent_control_overview.png` for a visual reference exported via Pillow for this MVP.

---

## 8. CLI Utilities

Module: `ReDNACoreDemo/agents/cli.py`

```
python3 -m ReDNACoreDemo.agents.cli --user USER1 --status
python3 -m ReDNACoreDemo.agents.cli --user USER1 --run-once
python3 -m ReDNACoreDemo.agents.cli --user USER1 --set-autonomy auto
python3 -m ReDNACoreDemo.agents.cli --user USER1 --quota 25
```

Output is JSON-friendly for automation pipelines. `--run-once` prints both run summary and latest status.

---

## 9. Testing & Verification

### 9.1 Pytest Suite (new file `tests/test_agentic_hc_mvp.py`)

Coverage:

1. Registry CRUD operations (ensure/update/list).
2. Policy fetch/update validations (autonomy, quotas, permissions, error handling).
3. Daemon job execution with mock providers & quota enforcement.
4. Autonomy gating (propose vs auto).
5. Capability token lifecycle (scope checks, expiry).
6. DevX API endpoints (capability issuance, run, autonomy updates, mailbox).
7. API capability enforcement (403 with missing/bad tokens).
8. CLI smoke test for `--status` and `--run-once`.

Runtime: 1.43 s on local sandbox.

### 9.2 Manual Verification Commands

```
# Run daemon once
python3 -m ReDNACoreDemo.core.agent_daemon --user USER1 --once

# Fetch agent state from core API (requires service running)
curl -s http://localhost:8015/agents/state?user_id=USER1 | jq .

# DevX Agent Control actions (issue capability then run)
http POST :8100/devx/api/agents/USER1/capability scope=core.agent.run x-devx-auth:devx-local
http POST :8100/devx/api/agents/USER1/run x-agent-capability:<token>
```

---

## 10. Operational Runbook

### 10.1 Bootstrapping a New Agent

1. Add user to registry: `agents.ensure_agent_record("NEWUSER")`.
2. Adjust policy (if needed): `agents.update_agent_policy("NEWUSER", {...})`.
3. Prime runtime directories via `AgentStateStore("NEWUSER").save(...)` or CLI `--status`.
4. Issue capability tokens for automation actors.

### 10.2 Running the Daemon as a Service

```
ENV=prod \
AGENT_LOOP_INTERVAL_MINUTES=5 \
AGENT_CAPABILITY_SECRET=<secure-secret> \
python3 -m ReDNACoreDemo.core.agent_daemon --user USER1
```

Use `supervisord`, `systemd`, or a container entrypoint to manage lifecycle.

### 10.3 Monitoring

- Tail telemetry: `tail -f data/telemetry/agents/job_completed.jsonl`.
- Watch audit failures: `tail -f data/audit/agent_capability_failures.jsonl`.
- DevX UI shows status LED (green/yellow/red) and quota usage.

### 10.4 Troubleshooting

| Symptom | Diagnosis | Remediation |
|---------|-----------|-------------|
| Jobs stuck in `awaiting_manual` | Autonomy mismatch | Increase autonomy or handle manual queue via outbox |
| `quota_exceeded` in outbox | Daily quota reached | Raise `jobs_per_day` or wait for reset |
| 403 responses on run/autonomy | Missing/expired capability | Issue new token via DevX or CLI |
| State not updating | Files locked/damaged | Inspect `state.json`; use CLI to resync |

---

## 11. Telemetry & Observability

### 11.1 Event Catalogue

| Event | Payload Fields | Description |
|-------|----------------|-------------|
| `agent_run` | agent_id, user_id, autonomy, pending | Emitted at start of daemon run |
| `job_enqueued` | job_id, kind, source, reason | Logged for inbox + generator jobs |
| `job_completed` | job_id, kind, source | Successful execution |
| `job_failed` | job_id, kind, reason | Failure (quota, capability, exception) |

### 11.2 Audit Entries

`agent_capability_failures.jsonl` stores fields: `event`, `payload`, `required_scope`, `user_id`, `ts`.

Example failure entry:

```json
{
  "event": "capability_scope_mismatch",
  "payload": {"agent": "hc_USER1", "scope": "core.agent.run", "...": "..."},
  "required_scope": "core.agent.config",
  "user_id": "USER1",
  "ts": "2025-10-12T01:05:24Z"
}
```

### 11.3 Metrics Hooks

Future 5.B+ phases can scrape telemetry to compute:

- Jobs executed per day per agent.
- Autonomy distribution.
- Failure rate by reason.
- Average runtime per job type.

---

## 12. Agent Activity Auditing

### 12.1 Overview

All agent lifecycle events, job operations, and capability changes are logged to a unified audit trail:

**Path:** `data/telemetry/agents/agent_activity.jsonl`

This canonical log replaces the prior split-file approach and ensures:
- Atomic append-only writes
- Single source of truth for audit queries
- Sub-200ms tail read performance for DevX UI
- Full traceability of agent configuration and job execution

### 12.2 Event Types

| Event | Fields | Description |
|-------|--------|-------------|
| `agent_configured` | audit_id, user_id, agent_id, old_level, new_level, by, changes, revoked_capabilities, issued_capabilities | Agency level change via DevX configurator |
| `agent_run` | agent_id, user_id, autonomy, status, pending | Daemon run started |
| `job_enqueued` | agent_id, user_id, job_id, kind, source, reason | Job added to pending queue |
| `job_completed` | agent_id, user_id, job_id, kind, source | Job successfully executed |
| `job_failed` | agent_id, user_id, job_id, kind, reason | Job failed (quota, capability, exception) |

### 12.3 Schema Examples

#### Agent Configuration Change

```json
{
  "audit_id": "d73db23032c54fc0bcc8fb9d1777c29c",
  "event": "agent_configured",
  "timestamp": "2025-10-10T21:08:02.279222Z",
  "user_id": "USER1",
  "agent_id": "hc_USER1",
  "old_level": 0,
  "new_level": 1,
  "by": "devx_api",
  "changes": {
    "autonomy": {"from": null, "to": "propose"},
    "quotas": {"from": {"jobs_per_day": 0}, "to": {"jobs_per_day": 10}},
    "features": {
      "from": {"automation": {"enabled": false}},
      "to": {
        "automation": {"enabled": true, "mode": "propose"},
        "refinement": {"auto_accept_threshold": 0.6, "max_risk": "low"}
      }
    },
    "schedule": {"from": null, "to": {"interval_hours": 12}},
    "rsc_enabled": {"from": false, "to": false}
  },
  "revoked_capabilities": [],
  "issued_capabilities": []
}
```

#### Job Enqueued

```json
{
  "event": "job_enqueued",
  "timestamp": "2025-10-10T17:31:20.775832Z",
  "agent_id": "hc_USER1",
  "user_id": "USER1",
  "job_id": "curiosity-USER1-0",
  "kind": "nudge",
  "source": "curiosity",
  "reason": "curiosity_threshold"
}
```

#### Job Completed

```json
{
  "event": "job_completed",
  "timestamp": "2025-10-10T17:31:20.776626Z",
  "agent_id": "hc_USER1",
  "user_id": "USER1",
  "job_id": "curiosity-USER1-0",
  "kind": "nudge",
  "source": "curiosity"
}
```

### 12.4 DevX API Endpoint

**GET** `/devx/api/agents/{user_id}/audit?limit=20`

Returns the last N audit entries for a specific user.

**Response:**

```json
{
  "audit": [
    { "audit_id": "...", "event": "agent_configured", ... },
    { "event": "job_completed", ... }
  ],
  "count": 20,
  "total": 47
}
```

**Performance:** Sub-100ms for limit ≤ 50 entries.

### 12.5 DevX UI Integration

The **Head Coach** tab in User Operations now includes an **Activity Audit** panel showing:

- Event type badges (color-coded by event kind)
- Timestamp (formatted as human-readable local time)
- Event-specific details (level changes, job source/kind, etc.)
- Audit ID snippet (first 8 hex chars) for traceability

**Location:** `ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx`

**Component:** `AgentAuditTail` (`ReDNACoreDemo/devx/frontend/src/components/AgentAuditTail.tsx`)

**Refresh Behavior:** Panel updates automatically when agency level changes or agent is reconfigured.

### 12.6 Backwards Compatibility

Historical audit entries in legacy paths are preserved:
- `data/audit/agents/agent_configured.jsonl`
- `data/telemetry/agents/agent_config_change.jsonl`
- `data/telemetry/agents/job_enqueued.jsonl`
- `data/telemetry/agents/job_completed.jsonl`
- `data/telemetry/agents/agent_run.jsonl`

New events since the normalization write exclusively to `agent_activity.jsonl`.

Migration scripts for consolidating legacy logs are available in `scripts/migrate_audit_logs.py` (future 5.C).

---

## 13. Integration Notes & Next Steps

### 13.1 Integration Touchpoints

- **Core API**: Expose agent state via `GET /agents/state` (planned 5.B).
- **Explorer**: Pull outbox entries for UI nudges (future integration).
- **Consent Service**: Replace DevX-issued tokens with official consent grants once capability mediation is live.
- **Scheduler**: Integrate with shared scheduler service to coordinate multi-user runs.
- **DevX Environment**: Frontend now consumes Vite-prefixed env vars; see `DEVX_ENVIRONMENT_GUIDE.md` for configuration baseline.

### 12.2 Phase 5.B Preview (RSC Collaboration)

Upcoming focus areas:

1. Collaborative scheduling across RSC cohorts (multi-agent coordination).
2. Shared context ledger for cross-user refinement loops.
3. Advanced telemetry correlation (confidence vs curiosity vs resolution).
4. Consent workflow linking capability issuance to user approvals.

### 12.3 Open Questions

- Should quota enforcement be per job type (nudge vs resolve) instead of aggregate?
- Which sensitive scopes require multi-factor confirmation before execution?
- How should agent runs interact with active UI sessions to avoid conflicting actions?
- What retention window is acceptable for inbox/outbox JSONL data?

---

## Appendix A: Quick Reference

### A.1 Key Files

| Path | Purpose |
|------|---------|
| `ReDNACoreDemo/agents/registry.py` | Registry helpers |
| `ReDNACoreDemo/agents/policy.py` | Policy model & validation |
| `ReDNACoreDemo/agents/state.py` | Runtime state store |
| `ReDNACoreDemo/agents/mailbox.py` | Inbox/outbox operations |
| `ReDNACoreDemo/agents/cli.py` | CLI interface |
| `ReDNACoreDemo/core/agent_daemon.py` | Scheduler loop |
| `ReDNACoreDemo/core/agent_capabilities.py` | Capability tokens |
| `devx/backend/agent_api.py` | DevX REST endpoints |
| `devx/frontend/src/lib/agentApi.ts` | Frontend client |
| `devx/frontend/src/routes/agent-control/AgentControlPanel.tsx` | React UI |
| `ReDNACoreDemo/tests/test_agentic_hc_mvp.py` | Regression coverage |

### A.2 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_LOOP_INTERVAL_MINUTES` | Daemon loop frequency (minutes) | `5` |
| `AGENT_CAPABILITY_SECRET` | HMAC secret key | `dev-agent-capability-secret` |
| `DEVX_AGENT_ADMIN_TOKEN` | DevX endpoint guard for capability issuance | `devx-local` |

### A.3 CLI Cheat Sheet

```
# Inspect agent status
python3 -m ReDNACoreDemo.agents.cli --user USER1 --status

# Change autonomy
python3 -m ReDNACoreDemo.agents.cli --user USER1 --set-autonomy auto

# Run daemon once for diagnostics
python3 -m ReDNACoreDemo.agents.cli --user USER1 --run-once
```

---

**End of Document – Phase 5.A MVP**  
Next planned benchmark: **5.B — RSC Collaboration Envelope**
