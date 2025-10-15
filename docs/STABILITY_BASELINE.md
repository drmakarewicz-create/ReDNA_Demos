# Stability Baseline v1

This baseline keeps the Core ↔ UCNRR path healthy and exposes clear guardrails when something drifts.

---

## Guardrails
- **Import drift canary** (`tests/test_imports_canary.py`): fails if any `ReDNACoreDemo/core/**/*.py` file reintroduces `import core.*` or `from core.*`.
- **Core ingestion contract** (`tests/test_ingestion_contract.py`): exercises `/core/api/ingest_evidence` with a canonical payload and a malformed one. Guarantees:
  - Valid evidence returns `200` with `{"ok": true, "ingested": ≥1, snapshot.traits includes PaDNA.EyeDNA.IrisColor}`.
  - Invalid evidence returns `400` with `{"error": "EVIDENCE_VALIDATION_FAILED"}`.
- **UCNRR contract** (`tests/test_ucnrr_contract.py`, marked `pytest -m e2e`): hits the live service at `http://127.0.0.1:8011`. Skips automatically when UCNRR is not running. Verifies `/health` is online and `/ucnrr/selftest` returns `{"ok": true}`.

---

## Local Smoke Test
Run `scripts/smoke.sh` after activating the repo virtualenv:

```bash
. .venv/bin/activate
scripts/smoke.sh
```

What it does:
1. Starts DevX (`127.0.0.1:${DEVX_BACKEND_PORT:-8100}`), UCNRR (`127.0.0.1:8011`), and Core (`127.0.0.1:8001`) if those ports are idle.
2. Probes `/health` for each service.
3. Exercises `/core/api/ingest_evidence` with a good and bad payload; fails fast if the contract regresses.
4. Polls `/devx/api/stack/ready` for up to 90 s, triggering an automatic restart after 60 s if the stack is still unready.
5. Prints `SMOKE OK` (no recovery needed) or `SMOKE OK (RESILIENCE)` when a supervised restart restored readiness.

---

## CI Coverage
`.github/workflows/stability.yml` runs on every push and pull request:

1. **test** job  
   - Sets up Python 3.11 and a `.venv`.  
   - Installs `requirements.txt` + `pytest`.  
   - Runs the import canary and ingestion contract tests.
2. **e2e** job  
   - Same environment bootstrap.  
  - Installs `requests` for the smoke script.  
   - Executes `scripts/smoke.sh`, which spins up Core + UCNRR and verifies the roundtrip.

If any guardrail fails, the workflow blocks the merge.

---

## Stack Readiness Endpoint
- **Endpoint**: `GET /devx/api/stack/ready` (served by `ReDNACoreDemo/devx/backend/stack_api.py`).  
  - Aggregates Core `/metrics` (five-minute window), Core `/health`, and UCNRR `/ucnrr/selftest`.  
  - Returns a structured payload with `status`, `fail_conditions`, `recovery_suggestions`, `error_rate_5m`, `p95_latency_ms_5m`, `unready_since`, and `rate_limit` information.  
  - `status` can be `ready`, `warming`, or `unready`; readiness is `true` only when the rolling thresholds are satisfied and both services are healthy. 
- **UI**: `/stack` shows a green **System Ready** pill only when `status === 'ready'`.  
  - When warming or unready, the panel lists reasons, fail codes, restart suggestions, rate-limit warnings, and exposes an Auto-Recovery button.  
  - Any fetch error surfaces as `Readiness check failed: ...` so operators know the probe itself failed.

Use these signals before any ingest or chat demos to guarantee the pipeline is ready.

## Phase 3 extensions
- **Supervisor restarts**: `POST /devx/api/stack/restart` accepts `{services, reason, force}` and honours the grace window (`DEVX_RESTART_GRACE_SEC`) plus hourly rate limits (`DEVX_MAX_RESTARTS_PER_HOUR`). Restart history is exposed at `GET /devx/api/stack/restart/history?limit=N`.
- **Unified stack logging**: `ReDNACoreDemo/core/logutil.py` appends structured JSONL records to `~/.redna/logs/stack.log` covering ingestion, UCNRR self-tests, readiness transitions, and supervisor restart events.
- **DevX UI upgrades**: the `/stack` page surfaces fail conditions, rolling window telemetry, restart suggestions, recent supervisor history, and an “Attempt Auto-Recovery” button that POSTs the supervisor endpoint.
- **Smoke harness resilience**: `scripts/smoke.sh` now boots DevX, exercises the ingestion contracts, polls `/devx/api/stack/ready`, triggers a supervised restart after 60 seconds if still unready, and exits with `SMOKE OK` or `SMOKE OK (RESILIENCE)` depending on whether recovery was needed.
