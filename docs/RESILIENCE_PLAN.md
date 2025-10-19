# Resilience Plan — Phase 3

## Overview

Phase 3 establishes supervised recovery for the Core ↔ UCNRR stack. A lightweight DevX supervisor monitors readiness, triggers safe restarts when the stack is unhealthy, and publishes unified JSONL logs for Core, UCNRR, and DevX.

Key capabilities:
- Rolling five-minute health window (error-rate & latency thresholds) surfaced by `/devx/api/stack/ready`.
- Supervisor-managed restarts with rate limiting and history (`/devx/api/stack/restart`, `/devx/api/stack/restart/history`).
- Unified log stream at `~/.redna/logs/stack.log` with structured records for ingest, readiness, self-tests, and restarts.
- Smoke harness upgrades that verify readiness and optionally auto-recover (`scripts/smoke.sh`).

## Environment Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEVX_RESTART_GRACE_SEC` | `60` | Minimum number of seconds the stack must be unready before automatic restarts (unless `force=true`). |
| `DEVX_MAX_RESTARTS_PER_HOUR` | `6` | Per-service restart limit. Once exceeded, the supervisor reports `rate_limited` in readiness. |
| `DEVX_BACKEND_PORT` | `8100` | DevX API port (used by smoke script and supervisor). |
| `REDNA_STACK_LOG` | `~/.redna/logs/stack.log` | Destination for unified JSONL logs. |

## Readiness Model

`/devx/api/stack/ready` returns a JSON payload with the following semantics:
- `status`: `"ready"`, `"warming"`, or `"unready"`.
- `fail_conditions`: machine-readable codes (`core_error_rate_high`, `ucnrr_selftest_fail`, `core_rate_limited`, etc.).
- `recovery_suggestions`: actionable hints per service when restart is recommended.
- `rolling_window_sec`, `error_rate_5m`, `p95_latency_ms_5m`: statistics derived from Core's five-minute rolling window.
- `unready_since`: ISO timestamp tracked across evaluations; used to enforce grace periods.
- `rate_limit`: per-service restart counters (`rate_limited`, `recent_restarts`, `remaining`).
- `failures_by_service`: narrative text grouped by `core` and `ucnrr` to surface which subsystem triggered the failure.

**Thresholds**
- Error rate: `errors_5xx_window_5m / max(1, requests_window_5m) <= 0.02`.
- Latency: `latency_p95_ms_window_5m <= 750`.
- Warmup: until the five-minute window accumulates at least one request (or the service has been running for 60s), status is `"warming"`.

## Supervisor Flow

1. Readiness transitions to `"unready"` with actionable failures (e.g., high error rate, UCNRR self-test failure).
2. After `DEVX_RESTART_GRACE_SEC`, the supervisor queue marks the service eligible for restart.
3. `/devx/api/stack/restart` (new payload `{services, reason, force}`) checks eligibility. If `force=false` and the grace window has not elapsed, the request is skipped.
4. When eligible, the supervisor stops the uvicorn process (SIGTERM + SIGKILL fallback) and starts a fresh worker using the same interpreter, port, and reload mode as today.
5. Each attempt appends a history entry (`restart_event`) to `~/.redna/devx_supervisor/state.json` and emits a `restart_event` line in the JSONL log.
6. If the per-hour limit is exceeded, restarts are refused with `status="rate_limited"`, surfaced both in readiness and the restart response.

Restart history is accessible via `GET /devx/api/stack/restart/history?limit=50` and surfaces timestamp, service, status, reason, and PID where available.

## Unified Logging

`ReDNACoreDemo/core/logutil.py` exposes `stack_log(service, level, event, msg, meta)` for structured logging. Core ingestion, UCNRR self-tests, readiness transitions, and supervisor restarts all write JSONL entries of the form:

```json
{
  "ts": "2025-10-15T19:05:13.123Z",
  "service": "core",
  "level": "INFO",
  "event": "ingest_ok",
  "msg": "ingest_evidence succeeded",
  "meta": {"user_id": "contract_user", "ingested": 1}
}
```

These records can be tailed via `scripts/tail_logs.sh` (simple `tail -F` + `jq` convenience).

## Smoke Harness

`scripts/smoke.sh` now:
1. Boots DevX, UCNRR, and Core (if not already running).
2. Exercises the ingestion contract (good + bad payload).
3. Polls `/devx/api/stack/ready` for 90 seconds.
4. If the stack remains unready for 60 seconds, posts `/devx/api/stack/restart` with `{services:["core","ucnrr"], force:false}`.
5. Exits successfully only when readiness becomes green. The script prints `SMOKE OK (RESILIENCE)` when auto-recovery was needed, otherwise `SMOKE OK`.

This smoke path runs in CI (`.github/workflows/stability.yml`) to guard the regression gates.

## Sequence Summary

```
Ingress request → Core rolling window updates → Readiness eval
  ↳ Healthy? → status=ready, no action
  ↳ Unhealthy? → fail_conditions populated, suggestions emitted
      ↳ After grace window → supervisor restart (unless rate limited)
          ↳ Unified log records `restart_event`
          ↳ Readiness re-evaluated until status=ready
```

This phase keeps the stack self-healing while maintaining the Phase 2 stability guardrails.
