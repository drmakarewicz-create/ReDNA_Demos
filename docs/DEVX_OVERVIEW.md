# DevX System Overview

**System**: DevX (Developer Experience)
**Version**: 1.0.0
**Status**: Production Ready
**Date**: 2025-10-08

---

## Purpose

DevX is the next-generation developer console for ReDNA, designed to replace and modernize the existing Developer Explorer (DevExp) through gradual, modular migration.

**Key Principles**:
- **Modularity**: Add features one at a time, never bulk migrate
- **Isolation**: Complete service independence from Core, UCNRR, CP++
- **Stability**: Port safety, graceful fallbacks, no service interference
- **Clarity**: Predictable behavior, clear error messages, intuitive UI

---

## Architecture

### Service Layer

```
┌─────────────────────────────────────────┐
│          ReDNA Ecosystem                │
├─────────────────────────────────────────┤
│  Core API (8015)   │  UCNRR (8011)     │  ❌ Never affected
│  React HC (3001)   │  CP++ (8501)      │  ❌ Never affected
├─────────────────────────────────────────┤
│  DevX Backend (8100)                    │  ✅ Isolated
│  DevX Frontend (3100)                   │  ✅ Isolated
└─────────────────────────────────────────┘
```

### Technology Stack

**Backend**:
- FastAPI (async Python web framework)
- Python 3.11+
- Pydantic (data validation)
- JSON/YAML file storage

**Frontend**:
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Monaco Editor (code editing)
- AJV (JSON schema validation)

### Operational Status

The DevX header surfaces live health chips for DevX, Consent, and Core services using `/devx/api/health/status`. The frontend polls every ~20 seconds so regressions are visible before running batch actions.

### Directory Structure

```
ReDNACoreDemo/devx/
├── backend/
│   ├── api.py              # FastAPI app
│   ├── semantics_api.py    # Trait semantics change request endpoints
│   ├── batch_ops_api.py    # Batch user operations (quarantine, purge, future jobs)
│   ├── config.py           # Configuration & port safety
│   ├── routers/
│   │   └── traits.py       # Trait Workshop endpoints
│   └── run_devx.py         # Backend runner
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React app
│   │   ├── routes/         # Route components
│   │   │   └── trait-workshop/panels/
│   │   │       ├── DefinitionEditor.tsx
│   │   │       ├── SemanticsEditor.tsx
│   │   │       └── TraitBrowser.tsx
│   │   │   └── user-ops/UserOps.tsx
│   │   ├── components/     # Reusable UI components
│   │   └── lib/
│   │       ├── devxApi.ts       # Trait API client
│   │       ├── semanticsApi.ts  # Trait semantics API client
│   │       └── userOpsApi.ts    # Batch user operations API client
│   ├── vite.config.ts
│   ├── package.json
│   └── tsconfig.json
│
└── logs/                   # Runtime logs & PID files
```

---

## Port Configuration

### Reserved Ports

| Service | Primary Port | Fallback Range | Auto-Increment |
|---------|--------------|----------------|----------------|
| DevX Backend | 8100 | 8101-8109 | ✅ Yes |
| DevX Frontend | 3100 | 3101-3109 | ✅ Yes |

### Port Safety Mechanism

**Backend** (`config.py`):
```python
def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """Try binding to ports until one is available."""
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((DEVX_HOST, port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError("No available port found")
```

**Startup Log** (`devx/logs/devx_start.log`):
```
backend_port=8100
backend_host=127.0.0.1
frontend_port=3100
```

### Service Independence Guarantees

✅ **DevX startup**:
- Checks port availability before binding
- Auto-increments if port unavailable
- Never kills existing processes

❌ **DevX will NOT**:
- Terminate Core, UCNRR, or CP++ processes
- Modify existing service configurations
- Share state or databases with other services

---

## CP++ Integration

### Launch Button (Future)

Control Panel++ will have a dedicated "DevX" button:

```python
# In control_panel_plus_plus.py
def open_devx():
    """Open DevX in browser (start if not running)."""
    # Check if backend is running
    backend_running = is_port_open(8100)

    if not backend_running:
        # Start DevX backend
        subprocess.Popen(
            ["python3", "ReDNACoreDemo/devx/backend/run_devx.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for backend to be ready
        for _ in range(10):
            if is_port_open(8100):
                break
            time.sleep(1)

    # Open frontend in browser
    webbrowser.open("http://127.0.0.1:3100")
```

### Start All Behavior

**DevX is NOT included in "Start All" or "Refresh"**.

Rationale:
- DevX is a developer tool, not a core service
- Not all users need DevX running
- Reduces resource usage for non-dev workflows

Users must explicitly launch DevX via:
- CP++ button
- `./scripts/start_devx.sh`
- Manual backend/frontend startup

---

## Current Modules

### 1. Trait Workshop ✅

**Status**: Production Ready
**Purpose**: Edit and validate trait definitions

- **Features**:
- Trait browser with filtering
- Value model editor (6 types supported)
- Semantics authoring tab (Monaco editor + live JSON-schema errors)
- Change request lifecycle (propose → validate → apply low-risk)
- Seed helper when semantics are missing (one-click scaffold via `/devx/api/semantics/seed`)

**API Endpoints**: 11 endpoints
- List traits
- Get definition
- Assert value model
- Propose change
- Validate CR
- Apply CR
- Rollback CR
- Get semantics
- Propose semantics change
- Validate semantics CR
- Apply semantics CR
- Semantics diagnostics

**UI Components**:
- TraitBrowser: Search, filter, select
- DefinitionEditor: 3-tab editor (metadata, value model, semantics)
- SemanticsEditor: Monaco JSON editor with CR controls

### 2. User Ops (Batch) ✅

**Status**: Production Ready
**Purpose**: Execute bulk user maintenance jobs with reversible quarantine.

**Features**:
- Searchable multi-select user list with live vault metadata
- Dry-run planning (bytes, capability counts, existing tickets)
- Quarantine-based deletion with capability revocation
- Undo within grace window; purge after review deadline
- Holistic review job queue (non-destructive) with manifest logging
- Capability revocation manifests (Consent integration)
- Sanitized JSON exports with per-user download links

**API Endpoints**: 10 endpoints
- List users (`/devx/api/users/list`)
- User summary (`/devx/api/users/summary`)
- Dry-run delete (`/devx/api/users/batch/dry-run`)
- Submit delete (`/devx/api/users/batch/delete`)
- Batch status (`/devx/api/users/batch/status`)
- Undo (`/devx/api/users/batch/undo`)
- Purge (`/devx/api/users/batch/purge`)
- Queue holistic job (`/devx/api/users/batch/run-holistic`)
- Revoke caps (`/devx/api/users/batch/revoke-caps`)
- Export JSON batch (`/devx/api/privacy/export-json-batch`)

**UI Components**:
- User selector with pagination and status badges
- Dry run panel summarising per-user plans
- Confirmation modal enforcing grace period + reason capture
- Undo / purge console with confirmation strings and eligibility filters
- Capability revoke console with Consent warnings
- Export results panel with download links

See `docs/DEVX_USER_OPS.md` for flow details and screenshots.

The Conflicts dashboard also includes a one-click **Seed Example** button (via `/devx/api/conflicts/seed`), and the Trait Workshop semantics tab exposes **Seed Example Semantics** when a trait lacks a record.

### 3. Holistic Summary ✅

**Status**: Production Ready
**Purpose**: Inspect the latest holistic review metrics produced by the Phase 2 engine.

- **Features**:
- Load a user by ID and display container/evidence counts
- Show overall RR, RR by domain, and the lowest RR paths
- View historical snapshots and notes
- Process queued holistic jobs immediately from the UI

- **API Endpoints**:
- `GET /devx/api/holistic/get`
- `GET /devx/api/holistic/history`
- `POST /devx/api/users/batch/run-holistic/process`

### 4. System Monitor ✅

**Status**: Production Ready
**Purpose**: Track health of DevX, Consent, and Core services with a rolling timeline.

- **Features**:
- Live health chips mirrored in the header
- Latency sparkline per service (100-sample buffer)
- Availability timeline showing up/down windows
- Polls `/devx/api/health/status` every ~20 seconds, persists history to JSONL

- **API Endpoints**:
- `GET /devx/api/health/status`
- `GET /devx/api/health/history`

### 2. Privacy Dashboard ✅

**Status**: Production Ready
**Purpose**: Provide visibility into capabilities, consent ledger, and refinement preferences.

**Features**:
- Master refinement toggle persisted to `data/users/<user>/privacy_prefs.json`
- Active capability list with revoke actions
- Consent ledger table with grant/revoke/use/deny events
- Export & deletion request helpers

**API**: `/devx/api/privacy/*` proxies to the Consent Service (port 8200+).

---

### 3. Conflict Dashboard ✅

**Status**: Beta
**Purpose**: Surface active trait conflicts and resolution outcomes.

**Features**:
- Tabbed interface (All Conflicts, Details, Simulate)
- Evidence inspection showing weights and provenance
- Synthetic conflict simulator for developer experiments
- Learning stats endpoint (`/conflicts/learning-stats`) to expose calibration metrics

**Backend**: `devx/backend/conflict_api.py` proxies to the Core conflict subsystem.

---

## Planned Modules

### 2. Observation Studio (Q1 2026)

**Purpose**: Import and validate observation files

**Features**:
- File upload UI
- Manual trait assignment
- Bulk operations
- Validation pipeline

### 3. Agent Behavior Studio (Q2 2026)

**Purpose**: Edit and test agent behaviors

**Features**:
- Coach prompt editor
- Intent routing visualizer
- Performance metrics
- A/B testing framework

### 4. System Health Dashboard (Q3 2026)

**Purpose**: Monitor ReDNA system health

**Features**:
- Service status indicators
- Error log viewer
- Performance metrics
- Alert configuration

---

## Development Workflow

### Starting DevX

```bash
# Quick start (both backend + frontend)
./scripts/start_devx.sh

# Manual start (backend only)
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH python3 devx/backend/run_devx.py

# Manual start (frontend only)
cd ReDNACoreDemo/devx/frontend
pnpm install
pnpm dev --port 3100
```

### Stopping DevX

```bash
# Quick stop (both backend + frontend)
./scripts/stop_devx.sh

# Manual stop (backend)
lsof -ti:8100 | xargs kill

# Manual stop (frontend)
lsof -ti:3100 | xargs kill
```

### Accessing DevX

- **Frontend UI**: http://127.0.0.1:3100
- **Backend API**: http://127.0.0.1:8100
- **API Docs**: http://127.0.0.1:8100/docs
- **Health Check**: http://127.0.0.1:8100/health

---

## Testing

### Integration Test

```bash
#!/bin/bash
# Test DevX independence

# Start DevX
./scripts/start_devx.sh

# Verify DevX is running
curl http://127.0.0.1:8100/health || exit 1
curl http://127.0.0.1:3100 || exit 1

# Verify other services still healthy
curl http://127.0.0.1:8015/health || exit 1  # Core
curl http://127.0.0.1:8011/health || exit 1  # UCNRR

# Stop DevX
./scripts/stop_devx.sh

# Verify other services still healthy
curl http://127.0.0.1:8015/health || exit 1
curl http://127.0.0.1:8011/health || exit 1

echo "✅ DevX independence test passed"
```

### Unit Tests

```bash
# Backend tests
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH python3 -m pytest tests/test_devx_traits.py -v

# Frontend tests
cd devx/frontend
pnpm test
```

---

## Migration from DevExp

### Phase 1: Trait Workshop ✅ (Complete)
- Standalone implementation
- No dependencies on DevExp
- Fully functional value model editor

### Phase 2: Observation Import (Q1 2026)
- Evaluate DevExp observation tools
- Rebuild with modern UI if needed
- Maintain API compatibility

### Phase 3: Other Modules (Q2-Q3 2026)
- Gradual migration or rebuild
- One module at a time
- No bulk migration

### Deprecation Timeline

**DevExp will remain available** until all modules are migrated and validated.

Timeline:
- 2025 Q4: Trait Workshop only (current)
- 2026 Q1-Q2: Add 2-3 more modules
- 2026 Q3: Evaluate DevExp deprecation
- 2026 Q4: Full migration (if approved)

---

## Performance

### Latency Targets

| Operation | Target | Actual |
|-----------|--------|--------|
| List traits | <100ms | ~50ms |
| Get definition | <100ms | ~30ms |
| Save value model | <200ms | ~150ms |
| Validate CR | <300ms | ~200ms |

### Resource Usage

**Backend**:
- Memory: ~50MB baseline
- CPU: <5% idle, <20% under load

**Frontend**:
- Bundle size: ~500KB (gzipped)
- Initial load: <2s on broadband

---

## Security

### API Authentication

**Current**: None (local development only)
**Future**: JWT tokens for production deployment

### CORS Policy

**Allowed Origins**:
- `http://localhost:3100`
- `http://localhost:3101`
- `http://localhost:3102`
- `http://127.0.0.1:3100`
- `http://127.0.0.1:3101`
- `http://127.0.0.1:3102`

### Data Access

**Read-only**:
- Trait definitions
- Schema files

**Write access**:
- Value models (via assert endpoint)
- Change requests (stored in `data/devx/change_requests/`)

**No access to**:
- User personal data
- Observation raw files
- API keys or credentials

---

## Monitoring

### Logs

**Backend log**: `devx/logs/backend.log`
```
2025-10-08 10:30:15 - INFO - DevX backend starting...
2025-10-08 10:30:16 - INFO - Starting DevX backend on 127.0.0.1:8100
2025-10-08 10:30:16 - INFO - Application startup complete
```

**Frontend log**: `devx/logs/frontend.log`
```
VITE v5.0.8  ready in 523 ms
➜  Local:   http://localhost:3100/
➜  Network: use --host to expose
```

**Startup log**: `devx/logs/devx_start.log`
```
backend_port=8100
backend_host=127.0.0.1
frontend_port=3100
```

### Health Checks

**Backend**:
```bash
curl http://127.0.0.1:8100/health
# {"status":"healthy","service":"devx-backend","version":"1.0.0"}
```

**Frontend**:
```bash
curl -I http://127.0.0.1:3100
# HTTP/1.1 200 OK
```

---

## Troubleshooting

### Backend won't start

**Symptom**: `RuntimeError: Could not find available port`

**Solution**:
```bash
# Check what's using ports 8100-8109
lsof -ti:8100,8101,8102,8103,8104,8105,8106,8107,8108,8109

# Kill processes if safe
lsof -ti:8100 | xargs kill
```

### Frontend build fails

**Symptom**: `ENOENT: no such file or directory, open 'package.json'`

**Solution**:
```bash
cd ReDNACoreDemo/devx/frontend
pnpm install
```

### Changes not appearing

**Symptom**: Edits saved but UI shows old data

**Solution**:
```bash
# Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)
# Or clear cache and reload
```

---

## Support

**Documentation**: `/docs/DEVX_*.md`
**Logs**: `devx/logs/`
**API Docs**: http://127.0.0.1:8100/docs
**Issues**: GitHub (ReDNA repository)

---

**Last Updated**: 2025-10-08
**Version**: 1.0.0
**Status**: Production Ready
