# AI Readiness Probe

**Purpose**: Provide at-a-glance traffic-light status for all three AI ingestion layers in the ReDNA system.

**Endpoint**: `GET /devx/api/ingestion/ai_ready`

**UI**: DevX "AI Readiness" tab in LLM Benchmarks console

---

## What It Checks

The AI Readiness Probe verifies that all three ingestion layers are operational:

### 1. **HC/DevX Backend** (Northstar Intake)
- **Checks**: DevX backend `/health` endpoint
- **Green if**: `status == "healthy"`
- **Purpose**: Ensures Northstar/Head Coach intake layer is running

### 2. **UCNRR Processing** (LLM Extraction)
- **Checks**: UCNRR `/health` endpoint for LLM configuration
- **Green if**: `llm_configured == true`
- **Purpose**: Verifies LLM is configured and ready for trait extraction
- **Details Captured**:
  - `llm_provider` (e.g., "ollama", "openai")
  - `llm_model` (e.g., "phi3:mini", "llama3.1:8b")
  - `llm_configured` (boolean)

### 3. **Core Processing** (Resolver & Storage)
- **Checks**: Core `/health` endpoint and optional E2E test
- **Green if**: `rr_mode == "online"` AND `ucnrr_enabled == true`
- **Purpose**: Confirms Core resolver is online and UCNRR integration is enabled
- **Details Captured**:
  - `rr_mode` (online/offline/dry_run)
  - `ucnrr_enabled` (boolean)

### 4. **End-to-End Test** (Optional)
- **Checks**: Full ingestion pipeline (ingest → rescore → promotion → Why-Card)
- **Green if**:
  - Chronotype trait appears in rescore response
  - Why-Card API returns non-empty explanation
- **Test Data**:
  - User ID: `ai_ready_probe` (configurable)
  - Text: "I am a morning person, up before sunrise." (configurable)
  - Trait: `BehaviorDNA.Sleep.Chronotype`
- **Details Captured**:
  - `rescore_rr` (RR score, e.g., 800.0)
  - `why_excerpt` (first 80 characters of Why-Card)

---

## Response JSON Schema

```json
{
  "hc_devx": {
    "status": "green" | "red",
    "details": {"status": "healthy"},
    "ts": "2025-10-18T03:45:00Z",
    "reason": null | "DevX status is 'degraded', expected 'healthy'"
  },
  "ucnrr": {
    "status": "green" | "red",
    "details": {
      "llm_configured": true,
      "llm_provider": "ollama",
      "llm_model": "phi3:mini",
      "status": "healthy"
    },
    "ts": "2025-10-18T03:45:00Z",
    "reason": null | "UCNRR is not LLM-configured (llm_configured=false)"
  },
  "core": {
    "status": "green" | "red",
    "details": {
      "rr_mode": "online",
      "ucnrr_enabled": true,
      "status": "healthy",
      "e2e": {
        "status": "green" | "red",
        "details": {
          "rescore_rr": 800.0,
          "why_excerpt": "Promotion threshold met (rr=800.0) from text: I am a morning person, up..."
        },
        "ts": "2025-10-18T03:45:01Z",
        "reason": null | "Chronotype not found in rescore response"
      }
    },
    "ts": "2025-10-18T03:45:00Z",
    "reason": null | "rr_mode is 'offline', expected 'online'"
  },
  "result": "ALL-GOOD" | "NEEDS-FIX",
  "probe_duration_ms": 450,
  "ts": "2025-10-18T03:45:01Z"
}
```

---

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_READY_PROBE_USER` | `ai_ready_probe` | User ID for E2E test |
| `AI_READY_PROBE_TEXT` | `"I am a morning person, up before sunrise."` | Test phrase for ingestion |
| `AI_READY_TIMEOUT_MS` | `1500` | HTTP timeout for health checks (ms) |
| `AI_READY_ENABLE_E2E` | `true` | Enable E2E promotion test |
| `AI_READY_NO_WRITE` | `false` | Skip E2E writes (for clean CI runs) |
| `DEVX_CORE_BASE` | `http://127.0.0.1:8004` | Core service URL |
| `DEVX_UCNRR_BASE` | `http://127.0.0.1:8017` | UCNRR service URL |
| `DEVX_BASE` | `http://127.0.0.1:8012` | DevX backend URL |

---

## Common Red Reasons & Remediation

### 🔴 UCNRR: "UCNRR is not LLM-configured (llm_configured=false)"

**Cause**: LLM provider/model not configured in UCNRR

**Remediation**:
1. Check UCNRR `.env` file:
   ```bash
   cat ReDNACoreDemo/.env | grep LLM
   ```
2. Ensure `LLM_PROVIDER` and `LLM_MODEL` are set:
   ```env
   LLM_PROVIDER=ollama
   LLM_MODEL=phi3:mini
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   ```
3. Restart UCNRR service

**Verify**:
```bash
curl -s http://127.0.0.1:8017/health | jq '{llm_configured, llm_provider, llm_model}'
```

---

### 🔴 Core: "rr_mode is 'offline', expected 'online'"

**Cause**: Core is running in offline/dry_run mode

**Remediation**:
1. Check Core `.env` file:
   ```bash
   cat ReDNACoreDemo/.env | grep RR_MODE
   ```
2. Set `RR_MODE=online`:
   ```env
   RR_MODE=online
   ```
3. Restart Core service

**Verify**:
```bash
curl -s http://127.0.0.1:8004/health | jq '{rr_mode}'
```

---

### 🔴 Core: "ucnrr_enabled is false"

**Cause**: Core is not configured to use UCNRR

**Remediation**:
1. Check Core `.env` file:
   ```bash
   cat ReDNACoreDemo/.env | grep UCNRR
   ```
2. Ensure `UCNRR_BASE` is set:
   ```env
   UCNRR_BASE=http://127.0.0.1:8017
   ```
3. Restart Core service

**Verify**:
```bash
curl -s http://127.0.0.1:8004/health | jq '{features}'
```

---

### 🔴 E2E: "Chronotype not found in rescore response"

**Cause**: UCNRR failed to extract Chronotype from test phrase

**Possible Issues**:
1. **LLM not responding**: Check UCNRR logs for timeouts
2. **Ollama not running**: Verify `ollama list` shows `phi3:mini`
3. **Wrong model**: Model may not recognize chronotype phrases

**Remediation**:
1. Test UCNRR directly:
   ```bash
   curl -s -X POST http://127.0.0.1:8017/api/rescore \
     -H 'Content-Type: application/json' \
     -d '{"user_id":"test","text":"I am a morning person, up before sunrise."}' | jq .
   ```
2. Verify Chronotype appears in `rr_by_trait`
3. If not, check UCNRR prompt configuration

---

### 🔴 E2E: "Why-Card is empty"

**Cause**: Core Why-Card generation failed

**Remediation**:
1. Check if promotion succeeded:
   ```bash
   curl -s -X POST http://127.0.0.1:8004/core/api/ingest_text \
     -H 'Content-Type: application/json' \
     -d '{"user_id":"test2","text":"I am a morning person, up before sunrise.","source":"test"}' | jq .snapshot.traits
   ```
2. Verify trait is in snapshot
3. Check Why-Card API:
   ```bash
   curl -s 'http://127.0.0.1:8004/core/api/traits/BehaviorDNA.Sleep.Chronotype/why?user_id=test2' | jq .why
   ```
4. If empty, check Core logs for Why-Card generation errors

---

### 🔴 DevX: "DevX health check timeout (1.5s)"

**Cause**: DevX backend not responding

**Remediation**:
1. Check if DevX backend is running:
   ```bash
   curl -s http://127.0.0.1:8012/health
   ```
2. If not responding, start DevX backend:
   ```bash
   ./scripts/dev_up.sh
   ```
3. Check port conflicts (default: 8012)

---

## How to Run

### From CLI

```bash
# Run probe and see full JSON
curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq .

# Check just the overall result
curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq .result

# See top failure reason
curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq '{result, hc_devx: .hc_devx.reason, ucnrr: .ucnrr.reason, core: .core.reason}'
```

### From DevX UI

1. Navigate to **Tools > LLM Benchmarks**
2. Click the **"AI Readiness"** tab
3. Click **"Run Probe"** button
4. View traffic-light indicators for each layer
5. Click **"Copy Diagnostics"** to copy full JSON

---

## Performance Notes

- **Typical Runtime**: 200-500ms (all services healthy)
- **Timeouts**: 1.5s per health check, 3s for E2E test
- **Max Runtime**: ~5s (if all timeouts occur)
- **Auto-Refresh**: Optional 10s interval in UI

---

## Storage Impact

**E2E Test Writes** (if `AI_READY_NO_WRITE=false`):
- Creates user directory: `data/users/ai_ready_probe/`
- Stores trait snapshot for `BehaviorDNA.Sleep.Chronotype`
- Generates Why-Card

**Cleanup** (optional):
```bash
# Remove E2E test data
rm -rf data/users/ai_ready_probe/
```

**No-Write Mode** (for CI):
Set `AI_READY_NO_WRITE=true` to skip E2E writes. The probe will return:
```json
{
  "e2e": {
    "status": "green",
    "details": {"no_write_mode": true, "skipped": true},
    "reason": "E2E probe skipped (AI_READY_NO_WRITE=true)"
  }
}
```

---

## Integration with CI/CD

### Example GitHub Actions Workflow

```yaml
name: AI Readiness Check

on: [push, pull_request]

jobs:
  ai-readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: ./scripts/dev_up.sh

      - name: Wait for services
        run: sleep 10

      - name: Run AI Readiness Probe
        run: |
          RESULT=$(curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq -r .result)
          if [ "$RESULT" != "ALL-GOOD" ]; then
            echo "AI Readiness check failed: $RESULT"
            curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq .
            exit 1
          fi
          echo "✅ AI Readiness: ALL-GOOD"

      - name: Save diagnostics on failure
        if: failure()
        run: |
          curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq . > ai_readiness_failure.json
          cat ai_readiness_failure.json

      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: ai-readiness-diagnostics
          path: ai_readiness_failure.json
```

---

## Acceptance Criteria

✅ **Backend**:
- `/devx/api/ingestion/ai_ready` returns schema above in <2s
- All health checks use configurable timeouts
- E2E test can be disabled via `AI_READY_ENABLE_E2E=false`
- Red status includes human-readable `reason` field

✅ **Frontend**:
- DevX UI displays traffic-light indicators for all 3 layers
- E2E status shown under Core (if enabled)
- "Copy Diagnostics" button copies full JSON to clipboard
- Auto-refresh toggle works (10s interval)

✅ **Tests**:
- Backend tests cover all probe functions
- Tests verify green/red logic for each layer
- Timeout handling tested
- E2E probe skip modes tested

✅ **Documentation**:
- Complete remediation guide for common red reasons
- CLI usage examples
- CI/CD integration example
- Configuration reference

---

## Per-Layer Diagnostics

In addition to the summary probe, you can request detailed diagnostics for individual layers using query parameters.

### Endpoint with Query Parameters

```
GET /devx/api/ingestion/ai_ready?layer=<layer>&verbose=<0|1>&no_write=<0|1>
```

**Query Parameters**:
- `layer` (optional): Specific layer to diagnose
  - `"devx"` - HC/DevX Backend
  - `"ucnrr"` - UCNRR Processing
  - `"core"` - Core Processing
  - `"core_e2e"` - End-to-End Test
- `verbose` (optional): Include verbose diagnostic data
  - `1` = Enable verbose mode (default)
  - `0` = Minimal response
- `no_write` (optional): Skip E2E writes (for `core_e2e` layer only)
  - `1` = Skip database writes
  - `0` = Normal operation (default)

### Layer Diagnostic Response Schema

```json
{
  "layer": "ucnrr",
  "status": "green" | "red",
  "ts": "2025-10-18T04:00:00Z",
  "details": {
    "llm_configured": true,
    "llm_provider": "ollama",
    "llm_model": "phi3:mini",
    "status": "healthy"
  },
  "reason": null | "UCNRR is not LLM-configured",
  "suggestions": [
    "Set LLM_PROVIDER in UCNRR .env (e.g., LLM_PROVIDER=ollama)",
    "Set LLM_MODEL in UCNRR .env (e.g., LLM_MODEL=phi3:mini)",
    "Restart UCNRR service"
  ],
  "verbose_data": {
    "http_status": 200,
    "response_time_ms": 45,
    "ollama_tags_ok": true,
    "ollama_models": ["phi3:mini", "llama3.1:8b"]
  }
}
```

### Layer-Specific Features

#### DevX Layer (`layer=devx`)
**Standard Details**:
- `status`: Backend health status

**Verbose Data** (`verbose=1`):
- `http_status`: HTTP response code
- `response_time_ms`: Response latency
- `used_fallback_endpoint`: Whether `/health` fallback was used (tries `/devx/api/health` first)

**Example**:
```bash
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=devx&verbose=1' | jq .
```

#### UCNRR Layer (`layer=ucnrr`)
**Standard Details**:
- `llm_configured`: LLM ready status
- `llm_provider`: Provider name (ollama, openai, etc.)
- `llm_model`: Model name
- `status`: Service health

**Verbose Data** (`verbose=1`):
- `http_status`: HTTP response code
- `response_time_ms`: Response latency
- `ollama_tags_ok`: Ollama `/api/tags` probe success (if provider=ollama)
- `ollama_models`: List of available Ollama models

**Example**:
```bash
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=ucnrr&verbose=1' | jq .
```

#### Core Layer (`layer=core`)
**Standard Details**:
- `rr_mode`: Resolver mode (online/offline/dry_run)
- `ucnrr_enabled`: UCNRR integration status
- `status`: Service health

**Verbose Data** (`verbose=1`):
- `http_status`: HTTP response code
- `response_time_ms`: Response latency
- `promotion_state`: Full promotion policy configuration (thresholds, enabled traits)

**Example**:
```bash
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core&verbose=1' | jq .
```

#### Core E2E Layer (`layer=core_e2e`)
**Standard Details**:
- `rescore_rr`: Chronotype RR score
- `why_excerpt`: Why-Card snippet
- `test_user`: User ID used for test
- `test_text`: Text phrase ingested

**Verbose Data** (`verbose=1`):
- `ingest_duration_ms`: Ingest request timing
- `ingest_response`: Full ingest API response (rescore, snapshot)
- `why_response`: Full Why-Card API response
- `why_full_text`: Complete Why-Card explanation

**No-Write Mode** (`no_write=1`):
- Skips database writes during E2E test
- Useful for CI/test environments that should remain stateless

**Examples**:
```bash
# Standard E2E diagnostic
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core_e2e&verbose=1' | jq .

# No-write mode (for CI)
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core_e2e&no_write=1' | jq .
```

### Remediation Suggestions

Each layer diagnostic includes a `suggestions[]` array with actionable remediation steps when status is red.

**Example (UCNRR not configured)**:
```json
{
  "layer": "ucnrr",
  "status": "red",
  "reason": "UCNRR is not LLM-configured (llm_configured=false)",
  "suggestions": [
    "Set LLM_PROVIDER in UCNRR .env (e.g., LLM_PROVIDER=ollama)",
    "Set LLM_MODEL in UCNRR .env (e.g., LLM_MODEL=phi3:mini)",
    "Restart UCNRR service"
  ]
}
```

### UI Integration

The DevX **AI Readiness** tab (LLM Benchmarks → AI Readiness) provides:
- Summary traffic-light view for all layers
- **"Diagnose" button** next to each traffic light
- **Diagnostic drawer** showing:
  - Layer status (green/red)
  - Remediation steps (suggestions)
  - Layer details
  - Verbose diagnostic data
  - Copyable JSON output

### CLI Usage Examples

```bash
# Summary probe (all layers)
curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq .

# Quick status check
curl -s http://127.0.0.1:8012/devx/api/ingestion/ai_ready | jq .result

# Diagnose specific layer
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=ucnrr&verbose=1' | jq .

# Get remediation suggestions
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core' | jq '.suggestions[]'

# Check UCNRR Ollama models
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=ucnrr&verbose=1' | jq '.verbose_data.ollama_models'

# View Core promotion policies
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core&verbose=1' | jq '.verbose_data.promotion_state'

# E2E test with timing breakdown
curl -s 'http://127.0.0.1:8012/devx/api/ingestion/ai_ready?layer=core_e2e&verbose=1' | jq '{
  status,
  rescore_rr: .details.rescore_rr,
  timing: .verbose_data.ingest_duration_ms
}'
```

---

## Future Enhancements

### Optional: No-Write Mode for CI

**Goal**: Run E2E test without persisting data

**Implementation**:
- When `AI_READY_NO_WRITE=true`:
  - Mock ingest request (don't hit Core)
  - Return simulated green E2E status
  - No snapshot or Why-Card created

**Use Case**: Clean CI runs that don't pollute data directories

---

## Summary

The AI Readiness Probe provides **instant visibility** into the health of all AI ingestion layers. Instead of manually checking three service health endpoints and running test ingestions, engineers get a **single traffic-light dashboard** that shows exactly what's working and what needs fixing.

### Features

✅ **Summary Probe**: Traffic-light status for all layers (HC/DevX, UCNRR, Core, E2E)
✅ **Per-Layer Diagnostics**: Detailed analysis with remediation suggestions
✅ **Verbose Mode**: Additional diagnostic data (response times, Ollama models, promotion policies)
✅ **No-Write Mode**: Clean E2E testing without persisting data
✅ **UI Integration**: AI Readiness tab in LLM Benchmarks with Diagnose buttons and diagnostic drawer
✅ **CLI Access**: Full REST API with query parameter support

**Status**: ✅ **Fully Implemented and Documented**
