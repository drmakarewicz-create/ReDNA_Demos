# Codex Task: CP++ DevX Bootstrap — Stack Status + Troubleshooter UI

**Version**: 1.0
**Date**: 2025-10-14
**Phase**: 2.1 (Operational Integrity)
**Owner**: Codex
**Reviewer**: Claude

---

## Executive Summary

**Goal**: Eliminate terminal dependency for ReDNA service management by building a web-based Stack Status dashboard and Troubleshooter wizard in the DevX UI.

**Context**:
- Phase 1 (Architectural Reliability) is **COMPLETE** ✅
- Phase 2.2 (Unified Logging + Metrics) **FOUNDATION COMPLETE** ✅
  - JSON-structured logging module exists: `ReDNACoreDemo/core/logging_config.py`
  - Metrics tracking exists: `ReDNACoreDemo/core/metrics.py`
  - Core API has `GET /metrics` endpoint
- Current pain point: Users need terminal access to diagnose/restart services
- Target: API-only lifecycle management via DevX web UI

**Success Criteria**: User can diagnose and restart all ReDNA services (Core, UCNRR, DevX) from browser without touching terminal.

---

## Background: Current Architecture

### Services

| Service | Port | Framework | Purpose | Health Endpoint |
|---------|------|-----------|---------|----------------|
| **Core API** | 8000 | FastAPI | Ingestion pipeline, chat API, resolver | `GET /health` |
| **UCNRR** | 8011 | FastAPI | UCN/RR scoring engine | `GET /health` |
| **DevX Backend** | 8100 | FastAPI | Developer tooling API | `GET /health` |
| **DevX Frontend** | 3100 | Vite + React Router | Developer UI (React 18) | N/A |

### Health Endpoint Contract (Phase 1 Complete)

All services expose `GET /health` with this structure:

```json
{
  "status": "healthy",
  "service": "core",
  "version": "1.0",
  "port": 8000,
  "prompt_sha256": "abc123...",       // Core and UCNRR only
  "prompt_version": "2.0",            // Core and UCNRR only
  "rr_mode": "online",                // Core only: "online" | "fallback" | "unavailable"
  "uptime_seconds": 3600
}
```

### Logging & Metrics (Phase 2.2 Foundation)

**Logs**:
- Location: `.run/logs/{service}.jsonl` (unified JSON logs)
- Format: `{"ts": "...", "service": "core", "level": "INFO", "event": "ingest_start", "req_id": "...", ...}`
- Already implemented in Core; needs adoption in UCNRR/DevX

**Metrics**:
- Endpoint: `GET /metrics` (Core API only, currently)
- Format: JSON counters/gauges
- Example metrics:
  ```json
  {
    "ingests_total": 42,
    "ingests_errors_4xx": 3,
    "rr_fallback_count": 0,
    "rr_online_count": 42
  }
  ```

---

## Task Breakdown

### 1. Stack Status Dashboard UI

**File**: `ReDNACoreDemo/devx/frontend/components/StackStatus.tsx` (NEW)

**Requirements**:

1. **Service Tile Grid**:
   - Display 3 tiles: Core API, UCNRR, DevX Backend
   - Each tile shows:
     - Service name
     - Status indicator: 🟢 Healthy / 🟠 Degraded / 🔴 Down
     - Port number
     - Prompt SHA (first 8 chars) — Core/UCNRR only
     - RR mode badge — Core only: `🟢 online` / `🟡 fallback` / `🔴 unavailable`
     - Uptime (formatted: `3h 24m`)
   - Status determined by:
     - 🟢 Healthy: `/health` returns 200 with `"status": "healthy"`
     - 🟠 Degraded: `/health` returns 200 but `rr_mode: "fallback"` (Core only)
     - 🔴 Down: `/health` fails or times out (>2s)

2. **Polling Logic**:
   - Poll `GET /devx/api/stack/status` every 5 seconds
   - Show "Last updated: 3s ago" timestamp
   - Display loading spinner on initial load
   - Show stale warning if last poll >15s ago

3. **Interaction**:
   - Click tile → Open modal with:
     - Full health JSON (formatted, syntax-highlighted)
     - Live metrics (if available)
     - Live logs (last 50 lines, auto-scrolling)
     - "Troubleshoot" button (opens Troubleshooter wizard)
   - Click "Refresh All" button → Force immediate poll

4. **Visual Design**:
   - Use Tailwind CSS (existing DevX stack)
   - Tile layout: CSS Grid, 3 columns on desktop, 1 column on mobile
   - Color palette:
     - Healthy: `bg-green-100 border-green-500`
     - Degraded: `bg-yellow-100 border-yellow-500`
     - Down: `bg-red-100 border-red-500`

---

### 2. Troubleshooter Wizard UI

**File**: `ReDNACoreDemo/devx/frontend/components/Troubleshooter.tsx` (NEW)

**Requirements**:

1. **Trigger**:
   - Automatically opens when service tile is clicked AND status is 🔴 Down
   - Can also be triggered from service detail modal

2. **Multi-Step Wizard Flow**:

   **Step 1: Diagnose** (Auto-runs on open)
   - Run diagnostics via `POST /devx/api/stack/diagnose` with body: `{"service": "core"}`
   - Display results:
     ```
     ✅ Port 8000 is available
     ❌ No process running for core
     ✅ Log file exists: .run/logs/core.jsonl
     ⚠️  Last log entry: ERROR - UCNRR connection failed
     ```
   - Show "View Full Logs" expandable section

   **Step 2: Restart Options**
   - Button: **"Kill & Restart on Port {current_port}"**
     - Calls `POST /devx/api/stack/restart` with `{"service": "core", "port": 8000}`
     - Shows restart logs in real-time (streaming if possible, or polling)
   - Button: **"Choose Different Port"**
     - Auto-detect next available port in range 8000-8099
     - Show: "Port 8012 is available"
     - Calls `POST /devx/api/stack/restart` with `{"service": "core", "port": 8012}`
     - Updates config file (e.g., `.env` or service config)

   **Step 3: Self-Test** (Auto-runs after restart)
   - Calls `POST /devx/api/stack/selftest/{service}`
   - For **Core**:
     - POST test chat: `"I have blue eyes"`
     - Verify evidence extraction
     - Check UCNRR connection
     - Validate resolver output
   - For **UCNRR**:
     - Call `GET /ucnrr/selftest` (existing endpoint)
     - Verify UCN score returned
   - For **DevX**:
     - Check `/health` endpoint
   - Display step-by-step results:
     ```
     ✅ Service started (PID 12345)
     ✅ Health check passed
     ✅ Self-test passed (UCN = 0.85)
     ```

   **Step 4: Logs Viewer** (Always available)
   - Tail last 100 lines from `.run/logs/{service}.jsonl`
   - Parse JSON logs and format:
     - Timestamp in local time
     - Color-coded log level (INFO=blue, WARN=yellow, ERROR=red)
     - Event name bolded
   - Auto-refresh every 2 seconds
   - Filter dropdown: All Levels | INFO | WARN | ERROR
   - Search box: Filter by text match

3. **Visual Design**:
   - Modal overlay with conditional step rendering (use plain React state, no wizard library needed)
   - Each step shows checkmarks/crosses in progress indicator
   - Real-time updates for restart/selftest steps
   - "Close" button only enabled after Step 3 completes (or user force-closes)
   - Follow existing DevX modal patterns for consistency

---

### 3. DevX Backend API

**File**: `ReDNACoreDemo/devx/backend/stack_api.py` (NEW)

**Integration**: Add router to `ReDNACoreDemo/devx/backend/api.py`:
```python
from .stack_api import router as stack_router

# At end of file (after line 107):
app.include_router(stack_router, tags=["stack"])
```

**Router Setup in `stack_api.py`**:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/devx/api/stack")

@router.get("/status")
async def get_stack_status():
    # ...implementation...
```

**Endpoints**:

#### `GET /devx/api/stack/status`

**Purpose**: Aggregate health from all services

**Logic**:
```python
async def get_stack_status():
    services = ["core", "ucnrr", "devx"]
    results = []

    for service in services:
        port = PORT_MAP[service]  # e.g., {"core": 8000, "ucnrr": 8011, "devx": 8100}
        health_url = f"http://127.0.0.1:{port}/health"

        try:
            response = await http_client.get(health_url, timeout=2.0)
            health_data = response.json()

            results.append({
                "service": service,
                "status": "healthy" if health_data["status"] == "healthy" else "degraded",
                "port": port,
                "health": health_data,
                "last_check": datetime.utcnow().isoformat()
            })
        except Exception as e:
            results.append({
                "service": service,
                "status": "down",
                "port": port,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            })

    return {"services": results, "timestamp": datetime.utcnow().isoformat()}
```

**Response**:
```json
{
  "services": [
    {
      "service": "core",
      "status": "healthy",
      "port": 8000,
      "health": {"status": "healthy", "rr_mode": "online", ...},
      "last_check": "2025-10-14T22:45:00Z"
    },
    {
      "service": "ucnrr",
      "status": "down",
      "port": 8011,
      "error": "Connection refused",
      "last_check": "2025-10-14T22:45:00Z"
    }
  ],
  "timestamp": "2025-10-14T22:45:00Z"
}
```

---

#### `POST /devx/api/stack/diagnose`

**Body**: `{"service": "core"}`

**Logic**:
1. Check port availability: `lsof -ti:{port}`
2. Check process running: `ps aux | grep {service_name}`
3. Check log file exists: `.run/logs/{service}.jsonl`
4. Parse last log entry

**Response**:
```json
{
  "service": "core",
  "port_available": true,
  "process_running": false,
  "pid": null,
  "log_file_exists": true,
  "last_log_entry": {
    "ts": "2025-10-14T22:40:00Z",
    "level": "ERROR",
    "event": "rr_connection_failed",
    "message": "UCNRR unavailable"
  }
}
```

---

#### `POST /devx/api/stack/restart`

**Body**: `{"service": "core", "port": 8000}`

**Logic**:
1. Kill existing process (if running): `pkill -f {service_name}`
2. Wait 1 second
3. Start service on specified port:
   - Core: `uvicorn ReDNACoreDemo.core.api:app --host 0.0.0.0 --port {port} &`
   - UCNRR: `uvicorn UCN_RR_Demo.ucnrr_app:app --host 0.0.0.0 --port {port} &`
   - DevX: `uvicorn ReDNACoreDemo.devx.backend.app:app --host 0.0.0.0 --port {port} &`
4. Write PID to `.run/{service}.pid`
5. Poll health endpoint (max 10 attempts, 1s apart)

**Response**:
```json
{
  "service": "core",
  "status": "started",
  "pid": 12345,
  "port": 8000,
  "health_check": "passed",
  "startup_logs": [
    "INFO: Started server process [12345]",
    "INFO: Waiting for application startup.",
    "INFO: Application startup complete."
  ]
}
```

---

#### `POST /devx/api/stack/change_port`

**Body**: `{"service": "core", "new_port": 8012}`

**Logic**:
1. Find available port (if not specified): scan 8000-8099 with `lsof -ti:{port}`
2. Update port config in `.env` or service-specific config
3. Call `restart` endpoint with new port

**Response**:
```json
{
  "service": "core",
  "old_port": 8000,
  "new_port": 8012,
  "status": "restarted",
  "config_updated": true
}
```

---

#### `POST /devx/api/stack/selftest/{service}`

**Logic**:

**For Core**:
```python
async def selftest_core():
    # POST test chat message
    response = await http_client.post("http://127.0.0.1:8000/ui/chat/send", json={
        "user_id": "SELFTEST_USER",
        "persona": "head_coach",
        "text": "I have blue eyes",
        "client_ts": int(time.time() * 1000)
    })

    # Parse response to verify evidence extraction
    data = response.json()

    return {
        "service": "core",
        "test": "blue_eyes_chat",
        "passed": "PaDNA.EyeDNA.IrisColor" in str(data),
        "details": data
    }
```

**For UCNRR**:
```python
async def selftest_ucnrr():
    response = await http_client.get("http://127.0.0.1:8011/ucnrr/selftest")
    data = response.json()

    return {
        "service": "ucnrr",
        "test": "selftest_endpoint",
        "passed": data.get("ok") and data.get("ucn", 0) > 0.5,
        "details": data
    }
```

**Response**:
```json
{
  "service": "core",
  "test": "blue_eyes_chat",
  "passed": true,
  "details": {
    "evidence_extracted": true,
    "ucn_score": 0.85,
    "rr_mode": "online"
  }
}
```

---

#### `GET /devx/api/stack/logs/{service}`

**Query Params**: `?lines=100&level=ERROR`

**Logic**:
1. Read `.run/logs/{service}.jsonl`
2. Parse last N lines (default 100)
3. Filter by log level if specified
4. Return as JSON array

**Response**:
```json
{
  "service": "core",
  "lines": [
    {
      "ts": "2025-10-14T22:45:00Z",
      "level": "INFO",
      "event": "ingest_start",
      "req_id": "abc123",
      "message": "Ingesting chat message for user TEST"
    },
    {
      "ts": "2025-10-14T22:45:01Z",
      "level": "ERROR",
      "event": "rr_connection_failed",
      "error": "Connection refused"
    }
  ],
  "total_lines": 2,
  "log_file": ".run/logs/core.jsonl"
}
```

---

### 4. Bootstrap Script

**File**: `scripts/cppp_bootstrap.py` (NEW)

**Purpose**: Single-command startup script for all services

**Usage**:
```bash
python scripts/cppp_bootstrap.py
```

**Logic**:
1. Create `.run/` directory if missing
2. Start services in dependency order:
   - UCNRR (no dependencies)
   - Core (depends on UCNRR)
   - DevX Backend (depends on Core)
3. For each service:
   - Check if port is available
   - Start process in background
   - Write PID to `.run/{service}.pid`
   - Poll health endpoint (max 30s timeout)
   - Log startup status to console
4. On success: Print summary table
5. On failure: Stop all services, print error, exit 1

**Output**:
```
🚀 ReDNA Stack Bootstrap v1.0

Starting services...
  [1/3] UCNRR (port 8011)... ✅ Healthy (2.3s)
  [2/3] Core API (port 8000)... ✅ Healthy (3.1s)
  [3/3] DevX Backend (port 8100)... ✅ Healthy (1.5s)

Stack Status:
┌───────────┬──────┬─────────┬──────────┐
│ Service   │ Port │ Status  │ PID      │
├───────────┼──────┼─────────┼──────────┤
│ UCNRR     │ 8011 │ Healthy │ 12345    │
│ Core      │ 8000 │ Healthy │ 12346    │
│ DevX      │ 8100 │ Healthy │ 12347    │
└───────────┴──────┴─────────┴──────────┘

🟢 All services running!

Next steps:
  - Stack Status UI: http://127.0.0.1:3100/stack
  - Core API: http://127.0.0.1:8000/health
  - UCNRR: http://127.0.0.1:8011/health
```

**Error Handling**:
- If port is already in use: Auto-detect next available port
- If health check fails: Print last 20 log lines, exit 1
- If service crashes: Kill all services, exit 1

---

### 5. Frontend Route Integration

**File**: `ReDNACoreDemo/devx/frontend/src/routes/stack/StackStatusPage.tsx` (NEW)

**Requirements**:
1. New route component following existing pattern (e.g., like `SystemMonitor.tsx`)
2. Add route in `App.tsx`:
   ```tsx
   import StackStatusPage from './routes/stack/StackStatusPage'

   // In <Routes>:
   <Route path="/stack" element={<StackStatusPage />} />
   ```
3. Add navigation link in `App.tsx` navigation section:
   ```tsx
   <NavLink
     to="/stack"
     className={({isActive}) =>
       isActive ? 'text-blue-600 font-semibold' : 'text-gray-600 hover:text-blue-600'
     }
   >
     Stack Status
   </NavLink>
   ```
4. Layout: Follow existing DevX route patterns (same container styles as `SystemMonitor.tsx`)
5. Component structure:
   ```tsx
   export default function StackStatusPage() {
     return (
       <div className="p-6">
         <h1 className="text-2xl font-bold mb-6">ReDNA Stack Status</h1>
         <StackStatus />
       </div>
     )
   }
   ```

---

## Acceptance Criteria

### Critical Success Scenarios

#### Scenario 1: Normal Operation
```bash
# Start stack
python scripts/cppp_bootstrap.py

# Open UI
open http://127.0.0.1:3100/stack

# Expected: All 3 tiles show 🟢 Healthy
# Expected: Core shows rr_mode: "online"
# Expected: All prompt SHAs displayed
```

#### Scenario 2: UCNRR Down → Troubleshoot → Restart
```bash
# Kill UCNRR manually
pkill -f ucnrr_app

# Wait 5 seconds
# Expected: UCNRR tile shows 🔴 Down within 5s

# Click UCNRR tile
# Expected: Troubleshooter wizard opens

# Click "Kill & Restart on Port 8011"
# Expected: Wizard shows:
#   - Step 1: Diagnose ✅
#   - Step 2: Restarting... (spinner)
#   - Step 3: Self-test ✅
#   - UCNRR tile now 🟢 Healthy

# No terminal commands used ✅
```

#### Scenario 3: Port Conflict Resolution
```bash
# Manually start service on port 8000
python -m http.server 8000 &

# Try to restart Core via Troubleshooter
# Expected: Wizard shows "Port 8000 in use"
# Expected: "Choose Different Port" button available
# Click button
# Expected: Core restarts on port 8012
# Expected: Core tile shows "Port: 8012"
```

#### Scenario 4: Logs Viewer
```bash
# Open Core detail modal
# Click "View Logs" tab
# Expected: Last 50 log entries displayed
# Expected: Auto-refresh every 2s
# Select "ERROR" filter
# Expected: Only ERROR level logs shown
```

---

## Testing Requirements

### Unit Tests

**File**: `ReDNACoreDemo/devx/backend/tests/test_stack_api.py` (NEW)

1. `test_get_stack_status_all_healthy()` — Mock all health endpoints returning 200
2. `test_get_stack_status_one_down()` — Mock UCNRR returning connection refused
3. `test_diagnose_port_in_use()` — Mock `lsof` returning PID
4. `test_restart_service()` — Mock process start, verify PID file written
5. `test_selftest_core()` — Mock chat API response with evidence
6. `test_logs_endpoint()` — Create temp log file, verify last N lines returned

### Integration Tests

**File**: `tests/test_stack_lifecycle.py` (NEW)

1. `test_bootstrap_script()` — Run bootstrap, verify all services healthy
2. `test_restart_via_api()` — Kill service, call restart API, verify recovery

### E2E Test (CI)

**File**: `.github/workflows/test-suite.yml` (UPDATE)

Add job: `stack-troubleshooter-e2e`:
```yaml
- name: E2E Stack Troubleshooter
  run: |
    # Start stack
    python scripts/cppp_bootstrap.py

    # Verify all healthy
    curl -s http://127.0.0.1:8100/devx/api/stack/status | jq -e '.services[] | select(.status != "healthy") | length == 0'

    # Kill UCNRR
    pkill -f ucnrr_app

    # Wait for detection
    sleep 6

    # Call restart API
    curl -s -X POST http://127.0.0.1:8100/devx/api/stack/restart \
      -H 'Content-Type: application/json' \
      -d '{"service": "ucnrr", "port": 8011}'

    # Verify recovered
    sleep 3
    curl -s http://127.0.0.1:8011/health | jq -e '.status == "healthy"'
```

---

## Implementation Checklist

### Phase A: Backend API (Priority 1)
- [ ] Create `ReDNACoreDemo/devx/backend/stack_api.py`
- [ ] Implement `GET /devx/api/stack/status`
- [ ] Implement `POST /devx/api/stack/diagnose`
- [ ] Implement `POST /devx/api/stack/restart`
- [ ] Implement `POST /devx/api/stack/change_port`
- [ ] Implement `POST /devx/api/stack/selftest/{service}`
- [ ] Implement `GET /devx/api/stack/logs/{service}`
- [ ] Add endpoints to DevX FastAPI app
- [ ] Write unit tests (`test_stack_api.py`)

### Phase B: Bootstrap Script (Priority 1)
- [ ] Create `scripts/cppp_bootstrap.py`
- [ ] Implement service startup logic
- [ ] Implement health check polling
- [ ] Implement PID file management
- [ ] Add error handling and rollback
- [ ] Test with all services
- [ ] Document usage in README

### Phase C: Frontend Components (Priority 2)
- [ ] Create `ReDNACoreDemo/devx/frontend/components/StackStatus.tsx`
- [ ] Implement service tile grid
- [ ] Implement status polling (5s interval)
- [ ] Implement service detail modal
- [ ] Create `ReDNACoreDemo/devx/frontend/components/Troubleshooter.tsx`
- [ ] Implement Step 1: Diagnose
- [ ] Implement Step 2: Restart options
- [ ] Implement Step 3: Self-test
- [ ] Implement Step 4: Logs viewer
- [ ] Add stepper UI navigation

### Phase D: Route Integration (Priority 2)
- [ ] Create `ReDNACoreDemo/devx/frontend/src/routes/stack/StackStatusPage.tsx`
- [ ] Add route to `App.tsx` (`<Route path="/stack" element={<StackStatusPage />} />`)
- [ ] Add navigation link in `App.tsx` navigation section
- [ ] Test responsive layout (mobile + desktop)

### Phase E: CI Integration (Priority 3)
- [ ] Update `.github/workflows/test-suite.yml`
- [ ] Add `stack-troubleshooter-e2e` job
- [ ] Test in CI environment
- [ ] Document CI expectations

---

## Technical Notes

### Port Configuration

**Current Ports** (hardcoded in various places):
- Core: `8000`
- UCNRR: `8011`
- DevX Backend: `8100`
- DevX Frontend: `3100`

**Recommendation**: Create `.env` file with:
```bash
CORE_PORT=8000
UCNRR_PORT=8011
DEVX_BACKEND_PORT=8100
DEVX_FRONTEND_PORT=3100
```

Load in bootstrap script and update on `change_port` API call.

### Log File Locations

Per Phase 2.2, logs are in:
- `.run/logs/core.jsonl`
- `.run/logs/ucnrr.jsonl`
- `.run/logs/devx.jsonl`

**Note**: UCNRR and DevX may still be logging to old locations. Part of this task is to ensure all services adopt the unified log directory.

### Process Management

**PID Files**:
- `.run/core.pid`
- `.run/ucnrr.pid`
- `.run/devx.pid`

**Kill Command**: `pkill -f {service_name}` (more reliable than `kill $(cat .run/{service}.pid)`)

### Security Considerations

**Admin Endpoints**: The restart/diagnose/logs APIs are **development-only**. Do NOT expose in production without authentication.

**Recommendations**:
1. Add `ADMIN_TOKEN` env var check (similar to Phase 1.2 `/core/admin/reload_prompt`)
2. Or: Bind DevX backend to `127.0.0.1` only (localhost-only access)
3. Or: Add IP whitelist

For MVP, localhost binding is sufficient.

---

## Dependencies

### Python Packages (Backend)
- `fastapi` (already installed)
- `httpx` (for async HTTP client)
- `psutil` (for process management — may be useful for PID checks)

Install:
```bash
pip install httpx psutil
```

### Node Packages (Frontend)
- `date-fns` (for timestamp formatting — may already be installed)

Install if needed:
```bash
cd ReDNACoreDemo/devx/frontend
npm install date-fns
```

**Note**: For wizard UI, use plain React state with conditional rendering (no additional wizard library needed).

---

## Reference Files

**Existing Health Endpoints**:
- Core: `ReDNACoreDemo/core/api.py` (search for `/health`)
- UCNRR: `UCN_RR_Demo/ucnrr_app.py` (search for `/health`)
- DevX: `ReDNACoreDemo/devx/backend/health_api.py` (existing health aggregation logic)

**Metrics Module**:
- `ReDNACoreDemo/core/metrics.py` — Phase 2.2 foundation complete

**Logging Module**:
- `ReDNACoreDemo/core/logging_config.py` — Phase 2.2 foundation complete

**Existing DevX Patterns**:
- **Frontend App**: `ReDNACoreDemo/devx/frontend/src/App.tsx` (routing, health polling pattern lines 22-59)
- **Example Route**: `ReDNACoreDemo/devx/frontend/src/routes/system/SystemMonitor.tsx` (component structure)
- **Backend Router**: `ReDNACoreDemo/devx/backend/api.py` (lines 100-107 show router inclusion pattern)
- **Health API**: `ReDNACoreDemo/devx/backend/health_api.py` (existing health check aggregation logic to extend)

---

## Handoff to Claude (Review Checklist)

When ready for review, ensure:

1. **All API endpoints work**:
   - Test with `curl` or Postman
   - Verify error handling (e.g., service not found)
   - Check response schemas match spec

2. **Bootstrap script tested**:
   - Run on clean state (no services running)
   - Run with port conflicts (manual service on port 8000)
   - Verify PID files created
   - Verify health checks pass

3. **Frontend renders correctly**:
   - All 3 service tiles display
   - Status colors match service state
   - Modal opens on tile click
   - Troubleshooter wizard navigates through steps

4. **E2E scenario works**:
   - Kill UCNRR → Tile shows red → Troubleshoot → Restart → Green

5. **Code quality**:
   - TypeScript types defined (frontend)
   - Python type hints used (backend)
   - Error handling comprehensive
   - Logs written to unified location

---

## Success Metrics

After implementation, we should be able to:

✅ **Start entire stack**: `python scripts/cppp_bootstrap.py` → All services green
✅ **View status**: Open UI, see all tiles healthy
✅ **Diagnose issues**: Service down → Click tile → See diagnostics
✅ **Restart service**: Click "Restart" → Service recovers
✅ **View logs**: Click "Logs" tab → See real-time JSON logs
✅ **Run self-tests**: After restart, verify evidence extraction works
✅ **Zero terminal usage**: All lifecycle management via browser

---

## DevX Stack Details (Pre-Verified)

**Frontend**:
- **Framework**: Vite + React 18 + React Router (NOT Next.js)
- **State Management**: Plain React hooks (`useState`, `useEffect`) — no Redux/Zustand
- **UI Library**: Tailwind CSS utility classes + bespoke JSX (Radix in deps but not actively used)
- **Routing**: React Router v6 (`<BrowserRouter>`, `<Routes>`, `<Route>`)
- **Entry Point**: `ReDNACoreDemo/devx/frontend/src/App.tsx`
- **Existing Routes**: `/trait-workshop`, `/system`, `/user-ops`, etc.

**Backend**:
- **Framework**: FastAPI
- **App Definition**: `ReDNACoreDemo/devx/backend/api.py` (lines 26-118)
- **Router Pattern**: `app.include_router(router, tags=[...])` at end of file (lines 100-107)
- **Auth**: No authentication currently — routes are open
- **Existing Health**: `/health/status` endpoint exists (aggregates DevX, Consent, Core)

**Key Insights**:
1. The existing `/health/status` endpoint in `health_api.py` is similar to what we need but only covers 3 services (DevX, Consent, Core). We'll create a new comprehensive `/devx/api/stack/status` that includes UCNRR.
2. DevX frontend uses plain React patterns with Tailwind — follow `SystemMonitor.tsx` as a reference for component structure.
3. No auth layer means we can proceed with open endpoints (localhost-bound for security).

---

## Contact

**Task Owner**: Codex
**Reviewer**: Claude
**Status**: Ready for Implementation
**Phase**: 2.1 (Operational Integrity)
**ETA**: 2-3 days (backend → bootstrap → frontend → CI)

---

**End of Codex Prompt**
