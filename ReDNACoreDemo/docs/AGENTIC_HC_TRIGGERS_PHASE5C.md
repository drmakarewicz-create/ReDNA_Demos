# Agentic Head Coach — Triggers Phase 5.C (Core Wiring)

_Status:_ ✅ Core wiring complete (no UI)

This slice delivers the foundational plumbing for event-driven Head Coach automation. Trigger sources now emit structured entries into each agent inbox, the daemon converts those triggers into domain jobs, and consent/capability guardrails are enforced before execution. DevX APIs expose basic configuration and testing hooks; UI will arrive in `5.C.ui`.

## Trigger Schema & Storage

| Field | Description |
|-------|-------------|
| `id` | Unique trigger identifier (`trg_<uuid>`) |
| `type` | `trigger.file_added`, `trigger.calendar_upcoming`, `trigger.telemetry_threshold`, or `trigger.conflict_backlog` |
| `source` | Origin label (`file_watcher`, `calendar`, `telemetry`, `conflict_monitor`, `api`) |
| `key` | Deduplication key per source |
| `payload` | Source-specific payload (path, calendar metadata, telemetry summary, backlog size) |
| `timestamp` | ISO-8601 (UTC) |

Triggers are appended to `data/users/<id>/agent/inbox.jsonl`. A lightweight cache (`triggers.cache.json`) keeps per-type dedupe and rate-limit timestamps.

## DevX Endpoints

```
GET  /devx/api/users/{user_id}/triggers/config          # Fetch config + recent events
POST /devx/api/users/{user_id}/triggers/config          # Persist config sections
POST /devx/api/users/{user_id}/triggers/test            # Emit a synthetic trigger
GET  /devx/api/users/{user_id}/triggers/recent?limit=20 # Tail latest trigger entries
POST /devx/api/users/{user_id}/triggers/webhook         # Calendar/file webhook ingress
```

All routes require `core.agent.config` capability headers. The `triggers.test` endpoint fans into the trigger engine, which normalises the payload, enforces dedupe/rate limits, writes to inbox, and audits with `event=trigger_emitted`.

## Daemon Conversion Rules

| Trigger | Job | Required Autonomy | Notes |
|---------|-----|-------------------|-------|
| `trigger.file_added` | `analyze` (Self-Improvement) | `auto` | Includes watched path metadata; optional `sensitive_namespaces` propagate to consent checks |
| `trigger.telemetry_threshold` | `analyze` | `auto` | Payload carries metric, count, window |
| `trigger.conflict_backlog` | `resolve` (Refinement) | `auto` | Pushes backlog size and requires `core.refinement.resolve` capability |
| `trigger.calendar_upcoming` | `nudge` | `semi` | Adds lead minutes from config |

- L1 (`autonomy=propose`) agents mark trigger jobs as `awaiting_manual` (proposed) without execution.
- L2+ execute automatically when guardrails pass.

For every trigger consumed the daemon writes `event=trigger_consumed` (action `enqueued`). Unsupported/duplicate triggers log `event=trigger_ignored` or `trigger_dropped`.

## Consent & Capability Enforcement

Execution requires:

- **Capabilities** — Active records in `data/capability_tokens/<id>.json` for `core.agent.run` and `core.refinement.resolve`. Missing scopes raise `CapabilityError`, the daemon logs `event=job_blocked` with `reason=capability_missing`, and no job executes.
- **Consent** — `data/consent/<id>.json` serves as the interim consent source. Jobs referencing `sensitive_namespaces` (e.g., PaDNA, PsyDNA) must have explicit grants. Missing consent triggers `event=job_blocked` with `reason=consent_denied`.

Telemetry events (`job_completed`, `job_failed`, `job_blocked`, etc.) append to `data/telemetry/agents/agent_activity.jsonl` for unified auditing.

## Example Audit Flow

1. `trigger_emitted` — test API emits `trigger.file_added`
2. `trigger_consumed` — daemon converts to `analyze`
3. `job_completed` — execution succeeds **OR**
4. `job_blocked` (`reason=capability_missing|consent_denied`) — enforcement stops job

## DevX Triggers Tab (5.C.ui)

Operators can now manage trigger presets directly in User Ops → User Detail → Triggers:

- Configuration cards for File Watcher, Telemetry Threshold, Conflict Backlog, and Calendar webhook settings
- Inline validation, optimistic save, and quick links to the Permissions tab for sensitive consent checks
- One-click test events that exercise the trigger engine and surface toast feedback
- A recent events table (tail 20) with payload previews, status badges, and modal view for JSON payloads

![Triggers configuration and test controls](images/triggers_config.png)

![Recent trigger events table](images/triggers_recent.png)

Refreshing the table uses `/triggers/recent` (no extra configuration fetch), keeping the UI fast while the daemon appends audits.

## Next Slice (5.C.consent_hardening)

- Extend capability middleware across remaining DevX endpoints (including calendar webhook secret validation)
- Harden consent reconciliation with Consent Service responses
- Expand regression coverage for webhook ingress and operator workflows

With the core plumbing in place, upcoming work can focus on operator tooling without revisiting the wiring.
