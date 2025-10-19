# UCNRR Connectivity System

## Overview

This system ensures UCNRR (UCN Resolver & Reasoner) is connected and stays connected to Core, with automatic recovery, bounded health checks, and clear diagnostics.

## Features

- **Idempotent Startup**: `ensure_ucnrr()` validates environment and starts UCNRR if needed
- **Model Warmup**: Automatic warmup after ensure to preload slow LLMs (500ms connect, 2s read timeout)
- **Selftest Cache**: 3-minute cache with background refresh at 60% expiry to avoid repeated slow selftests
- **Health Monitoring**: Fast liveness probe with bounded timeouts (300ms connect, 700ms read)
- **Auto-Recovery**: Exponential backoff (2s → 5s → 10s → 30s) with restart capping
- **Restart Cap**: Max 3 restarts within 10 minutes to prevent thrashing
- **Reason Codes**: Precise diagnostics for all failure modes
- **DevX Controls**: Start, restart, status, and logs via API and UI
- **Zero Paid Usage**: Only local Ollama provider, no paid LLM changes

## Architecture

### Components

1. **Supervisor Module** (`ReDNACoreDemo/devx/backend/supervisor_ucnrr.py`)
   - `ensure_ucnrr(config)`: Idempotent startup with validation
   - `check_ucnrr()`: Fast health probe
   - `monitor_ucnrr()`: Async monitor loop with backoff
   - `get_ucnrr_status()`: Status for API

2. **DevX API** (`ReDNACoreDemo/devx/backend/stack_ucnrr_api.py`)
   - `POST /devx/api/stack/ucnrr/ensure`: Start/restart UCNRR
   - `GET /devx/api/stack/ucnrr/status`: Get current status
   - `POST /devx/api/stack/ucnrr/restart`: Hard restart (rate-limited)
   - `GET /devx/api/stack/ucnrr/logs?tail=N`: Tail logs

3. **Stack Ready Endpoint** (`ReDNACoreDemo/devx/backend/stack_api.py`)
   - Enhanced `_compute_readiness()` with UCNRR reason codes
   - Specific recovery suggestions for each failure mode

4. **Core Health** (`ReDNACoreDemo/core/api.py`)
   - Bounded UCNRR probe (existing, validated)
   - `rr_mode`: online | degraded | unavailable

5. **UI Card** (`web/src/components/llm-bench/UCNRRConnectivityCard.tsx`)
   - Status display (online/degraded/offline)
   - Ensure/Restart buttons
   - Live logs viewer
   - Auto-refresh when degraded

6. **CLI Helper** (`scripts/ensure_ucnrr.sh`)
   - Validates Ollama
   - Checks port availability
   - Starts UCNRR with logging

## Reason Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `ok` | All systems operational | None |
| `bad_llm` | LLM not configured | Start Ollama + pull model |
| `conn_refused` | Service not running | Call `/ensure` endpoint |
| `timeout` | Health check timed out | Wait or restart |
| `ollama_offline` | Ollama not reachable | `ollama serve & && ollama pull phi3:mini` |
| `ollama_conn_refused` | Ollama connection refused | Start Ollama |
| `ollama_timeout` | Ollama request timed out | Check Ollama health |
| `port_N_in_use` | Port already in use | Change port or kill process |
| `ucnrr_unreachable` | UCNRR not reachable | Ensure UCNRR |
| `ucnrr_llm_disabled` | LLM disabled | Start Ollama |
| `ucnrr_restart_capped` | Restart cap exceeded | Wait 10m or check logs |
| `ucnrr_backoff_active` | Backoff delay active | Wait for auto-restart |

## Usage

### CLI Quick Start

```bash
# 1. Ensure Ollama is running
ollama serve >/dev/null 2>&1 &
ollama list

# 2. Ensure UCNRR is running
./scripts/ensure_ucnrr.sh

# 3. Check UCNRR status
curl -s http://127.0.0.1:8012/devx/api/stack/ucnrr/status | jq .

# 4. Check Core health (should show rr_mode: "online")
curl -s http://127.0.0.1:8004/health | jq '{status, rr_mode, features}'

# 5. Check stack readiness
curl -s http://127.0.0.1:8012/devx/api/stack/ready | jq .

# 6. View UCNRR logs
curl -s 'http://127.0.0.1:8012/devx/api/stack/ucnrr/logs?tail=50'
```

### API Examples

#### Ensure UCNRR

```bash
curl -s -X POST http://127.0.0.1:8012/devx/api/stack/ucnrr/ensure \
  -H "Content-Type: application/json" \
  -d '{"force_restart": false}' | jq .
```

Response:
```json
{
  "status": "started",
  "reason": "ok",
  "pid": 12345,
  "model": "phi3:mini",
  "provider": "ollama",
  "alive": true,
  "llm_configured": true
}
```

#### Get Status

```bash
curl -s http://127.0.0.1:8012/devx/api/stack/ucnrr/status | jq .
```

Response:
```json
{
  "alive": true,
  "llm_configured": true,
  "reason": "ok",
  "restarts_last_10m": 0,
  "restart_capped": false,
  "backoff_sec_remaining": 0,
  "last_check": "2025-10-17T12:34:56Z",
  "pid": 12345
}
```

#### Restart UCNRR

```bash
curl -s -X POST http://127.0.0.1:8012/devx/api/stack/ucnrr/restart | jq .
```

Response:
```json
{
  "status": "scheduled",
  "reason": "ok",
  "pid": 12346
}
```

### DevX UI

1. Navigate to `/tools/llm-benchmarks`
2. Find "UCNRR Connectivity" card in right column
3. View status, restart count, and reason
4. Click "Ensure UCNRR" to start if down
5. Click "Show Logs" to view recent logs
6. Status auto-refreshes every 5s when degraded

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UCNRR_PORT` | `8017` | UCNRR service port |
| `UCNRR_LLM_PROVIDER` | `ollama` | LLM provider (ollama only) |
| `UCNRR_LLM_MODEL` | `phi3:mini` | LLM model name |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama base URL |
| `REDNA_HOME` | `~/.redna` | ReDNA home directory |
| `UCNRR_WARMUP_ENABLED` | `true` | Enable model warmup after ensure |
| `UCNRR_WARMUP_CONNECT_MS` | `500` | Warmup connect timeout (ms) |
| `UCNRR_WARMUP_READ_MS` | `2000` | Warmup read timeout (ms) |
| `UCNRR_SELFTEST_CACHE_SEC` | `180` | Selftest cache duration (3 min) |
| `UCNRR_SELFTEST_BG_TIMEOUT_SEC` | `4` | Background selftest timeout |

### Supervisor Tuning

Restart cap and backoff schedule are defined in `supervisor_ucnrr.py`:

```python
BACKOFF_SCHEDULE = [2, 5, 10, 30]  # seconds
RESTART_CAP_COUNT = 3
RESTART_CAP_WINDOW_SEC = 600  # 10 minutes
```

## Slow-Model Hardening

For slow LLMs like llama3.1:8b, UCNRR includes two optimizations:

### Model Warmup

When `ensure_ucnrr()` successfully starts UCNRR with a configured LLM, it automatically sends a trivial generation request (`prompt: "ok"`) to Ollama to preload the model into memory. This prevents the first real request from timing out.

- **When**: After ensure completes with `llm_configured: true`
- **Timeout**: 500ms connect, 2000ms read (configurable via env vars)
- **Behavior**: Failures are logged but don't block ensure from succeeding
- **Disable**: Set `UCNRR_WARMUP_ENABLED=false`

### Selftest Cache

The `/api/health` endpoint caches successful selftest results for 3 minutes to avoid repeated slow selftest calls during health checks.

- **Cache Duration**: 180 seconds (configurable via `UCNRR_SELFTEST_CACHE_SEC`)
- **Background Refresh**: Triggered at 60% cache age (108 seconds) to keep cache fresh
- **Response Fields**:
  - `selftest_cached: true` when serving from cache
  - `selftest_cache_age_sec` shows cache age
  - `model`, `provider`, `ucn`, `elapsed_ms` from cached selftest
- **Behavior**: When cache is stale or expired, returns base health without selftest and triggers background refresh

This allows Core's health checks to return quickly even with slow models, while ensuring selftest results are reasonably fresh.

## Testing

Run all UCNRR tests (55 tests total):

```bash
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_*.py -v
```

Or run individual test suites:

```bash
# Core supervisor tests (12 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_supervisor.py -v

# Ready endpoint reason codes (6 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ready_ucnrr_reasons.py -v

# Warmup functionality (6 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_warmup.py -v

# Selftest cache (6 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_selftest_cache.py -v

# Integration tests (7 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_integration.py -v

# Edge cases (10 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_edge_cases.py -v

# Performance tests (10 tests)
pytest ReDNACoreDemo/devx/backend/tests/test_ucnrr_performance.py -v
```

## Troubleshooting

### UCNRR won't start

**Symptom**: `ensure_ucnrr` returns `status: "failed"`

**Check**:
1. Ollama running? `curl -s http://127.0.0.1:11434/api/tags`
2. Port available? `lsof -nP -iTCP:8017 -sTCP:LISTEN`
3. Logs: `tail -f /tmp/ucnrr.log`

### Restart cap exceeded

**Symptom**: `restart_capped: true` in status

**Fix**:
1. Check logs for persistent errors: `curl -s 'http://127.0.0.1:8012/devx/api/stack/ucnrr/logs?tail=200'`
2. Wait 10 minutes for cap to expire
3. Fix underlying issue (usually Ollama or port conflict)

### LLM not configured

**Symptom**: `llm_configured: false` in status

**Fix**:
```bash
ollama serve >/dev/null 2>&1 &
ollama pull phi3:mini
curl -s -X POST http://127.0.0.1:8012/devx/api/stack/ucnrr/restart
```

### Stack ready reports ucnrr_unreachable

**Symptom**: `/stack/ready` shows `ucnrr_unreachable` in `fail_conditions`

**Fix**:
```bash
# Ensure UCNRR
curl -s -X POST http://127.0.0.1:8012/devx/api/stack/ucnrr/ensure | jq .

# Verify
curl -s http://127.0.0.1:8012/devx/api/stack/ready | jq '{ready, status, fail_conditions}'
```

## Integration Points

### Core → UCNRR

Core's `/health` endpoint probes UCNRR:
- Timeout: 500ms connect, 1000ms read
- Returns `rr_mode`: "online" | "degraded" | "unavailable"

### DevX → UCNRR

DevX supervises UCNRR:
- Monitors health every 5s
- Auto-restarts with backoff
- Provides diagnostics via API

### UI → DevX

UI displays UCNRR status:
- Real-time status from `/stack/ucnrr/status`
- Logs from `/stack/ucnrr/logs`
- Controls via `/stack/ucnrr/ensure` and `/restart`

## Logs

### UCNRR Service Logs

Location: `/tmp/ucnrr.log`

Tail:
```bash
curl -s 'http://127.0.0.1:8012/devx/api/stack/ucnrr/logs?tail=100'
```

### Supervisor Events

Location: Core logs (via `stack_log`)

Events:
- `ucnrr_start`: UCNRR started
- `ucnrr_restart`: UCNRR restarted
- `ucnrr_online`: UCNRR recovered
- `ucnrr_unhealthy`: Health check failed
- `ucnrr_backoff`: Backoff delay applied
- `ucnrr_cap`: Restart cap exceeded
- `ucnrr_ensure`: Ensure operation

## Safety

- **No Paid Usage**: System only uses local Ollama, never paid providers
- **Restart Cap**: Prevents thrashing on persistent errors
- **Bounded Timeouts**: Health checks never hang
- **No Secrets**: No API keys or tokens in logs or environment

## Future Enhancements

- [ ] Async monitor loop in DevX backend (requires background task)
- [ ] Metrics: restart frequency, downtime duration
- [ ] Alerts: Slack/email on cap exceeded
- [ ] Multi-provider support (with safety guardrails)
- [ ] Port conflict auto-resolution

## References

- DevX Bootstrap: `ReDNACoreDemo/devx/backend/supervisor.py`
- Stack API: `ReDNACoreDemo/devx/backend/stack_api.py`
- Core Health: `ReDNACoreDemo/core/api.py`
- UCNRR App: `UCN_RR_Demo/ucnrr_app.py`
