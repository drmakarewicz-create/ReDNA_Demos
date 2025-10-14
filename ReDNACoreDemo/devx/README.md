# DevX - ReDNA Developer Experience

**Version**: 1.0.0
**Status**: Production Ready
**Module**: Trait Workshop (v1)

---

## Overview

DevX is the next-generation developer console for ReDNA, designed for clarity, stability, and modular expansion. It provides isolated, predictable tools for managing and evolving the ReDNA ontology and system configuration.

**Current Modules**:
- ✅ **Trait Workshop**: Edit and validate trait definitions with value models and semantics
- ✅ **Privacy Dashboard**: Monitor capabilities, ledger events, and consent preferences (auto-fallback to synthetic demo data)
- ✅ **Jarvis-Codex Panel**: Review, diff, approve/reject Head Coach-proposed UI edits with full audit trail

**Planned Modules**:
- ⏳ Observation Ingestion Studio
- ⏳ Agent Behavior Studio
- ⏳ System Health Dashboard

---

## Architecture

```
DevX/
├── backend/              # FastAPI service (port 8100)
│   ├── api.py           # Main FastAPI app
│   ├── config.py        # Port safety and configuration
│   ├── routers/
│   │   └── traits.py    # Trait Workshop endpoints
│   └── run_devx.py      # Backend runner script
│
├── frontend/            # React + TypeScript app (port 3100)
│   ├── src/
│   │   ├── routes/
│   │   │   ├── privacy-dashboard/
│   │   │   │   └── PrivacyDashboard.tsx
│   │   │   ├── trait-workshop/
│   │   │   │   ├── TraitWorkshop.tsx
│   │   │   │   └── panels/
│   │   │   │       ├── TraitBrowser.tsx
│   │   │   │       └── DefinitionEditor.tsx
│   │   │   └── jarvis-codex/
│   │   │       └── JarvisCodexPanel.tsx
│   │   ├── lib/
│   │   │   ├── devxApi.ts           # API client
│   │   │   └── jarvisCodexApi.ts    # Jarvis-Codex API client
│   │   └── App.tsx
│   ├── vite.config.ts
│   └── package.json
│
└── logs/                # Runtime logs and PID files
```

---

## Port Safety

DevX is **completely isolated** from existing ReDNA services:

| Service | Port | Status |
|---------|------|--------|
| **DevX Backend** | 8100 | ✅ Auto-increment if unavailable |
| **DevX Frontend** | 3100 | ✅ Auto-increment if unavailable |
| Core API | 8015 | ❌ Never touched |
| UCNRR | 8011 | ❌ Never touched |
| React HC | 3001 | ❌ Never touched |
| CP++ | 8501 | ❌ Never touched |

**Port Detection**:
- Automatically finds available ports (8100→8101→8102, etc.)
- Logs final ports to `devx/logs/devx_start.log`
- Never terminates or interferes with other services

---

## Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ with pnpm
- ReDNA Core repository

### Quick Start

1. **Start Consent Service**:
   ```bash
   ./scripts/start_consent.sh
   ```

2. **Start DevX** (backend + frontend):
   ```bash
   cd /path/to/ReDNA_Demos
   ./scripts/start_devx.sh
   ```

3. **Access DevX**:
   - Backend API: http://127.0.0.1:8100
   - Frontend UI: http://127.0.0.1:3100
   - API Docs: http://127.0.0.1:8100/docs

4. **Stop DevX**:
   ```bash
   ./scripts/stop_devx.sh
   ```

### Manual Setup

**Backend**:
```bash
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH python3 devx/backend/run_devx.py
```

**Frontend**:
```bash
cd ReDNACoreDemo/devx/frontend
pnpm install
pnpm dev --port 3100
```

---

## Trait Workshop Module

### Features

1. **Trait Browser**
   - Filter by namespace, status, and value model presence
   - Search by path or name
   - Visual indicators for value models and semantics

2. **Definition Editor**
   - View trait metadata (namespace, version, status)
   - Edit value models (type, range, unit, categories)
   - View trait semantics (coming soon: full editor)
   - Live validation before save

3. **Value Model Types**
   - `numeric`: Range-based values with units (e.g., 0-100 meters)
   - `categorical`: Discrete categories (e.g., ["low", "medium", "high"])
   - `ordinal`: Ordered categories with rankings
   - `boolean`: True/false values
   - `text`: Free-form text
   - `composite`: Complex nested structures

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/devx/api/traits/list` | List all traits with filters |
| GET | `/devx/api/traits/definition?path=...` | Get trait definition |
| POST | `/devx/api/traits/assert` | Save value model (direct) |
| POST | `/devx/api/traits/propose-change` | Create change request |
| GET | `/devx/api/traits/validate?cr_id=...` | Validate change request |
| POST | `/devx/api/traits/apply-change` | Apply validated CR |
| POST | `/devx/api/traits/rollback` | Rollback applied CR |

### Change Request Flow

**Low-Risk Changes** (auto-apply):
- Adding value model to new trait
- Documentation updates
- Example additions

**Medium/High-Risk Changes** (require approval):
- Updating existing value models
- Changing semantic boundaries
- Modifying inclusion/exclusion criteria

**Risk Calculation**:
```python
def calculate_risk_level(change_type: str, has_existing: bool) -> str:
    if change_type == "add_value_model" and not has_existing:
        return "low"
    if change_type == "update_value_model" and has_existing:
        return "medium"
    if "semantics" in change_type and has_existing:
        return "high"
    return "medium"
```

---

## Privacy Dashboard Module

### Features

1. **Master Controls**
   - Toggle refinement plane activity
   - Persist preferences in `data/users/<user>/privacy_prefs.json`

2. **Active Permissions**
   - Lists capabilities from Consent Service
   - Supports one-click revocation via PermCoach pipeline
   - Falls back to synthetic trait summaries when no active capabilities exist

3. **Consent Ledger**
   - Visual ledger of grant/revoke/use/deny events
   - Sorted by most recent activity

4. **Export & Deletion**
   - Triggers export and purge requests via DevX API proxy

### Navigation

- Route: `http://127.0.0.1:3100/privacy`
- Navigation label: `🔒 Privacy Dashboard`
- Synthetic data endpoint: `GET http://127.0.0.1:8100/devx/api/synthetic/traits`

### Demo Mode

If Consent Service is offline or no capabilities exist, the dashboard automatically activates synthetic preview mode so the UI remains demonstrable without live data.

---

## Jarvis-Codex Panel Module

### Features

1. **Proposal Review**
   - Lists all HC-proposed UI edits with metadata
   - Filter by status: All | Pending | Applied | Rejected
   - Live stats chips showing counts

2. **Diff Viewer**
   - Side-by-side before/after comparison
   - Syntax highlighting for code changes
   - Scrollable for long edits

3. **Approval Workflow**
   - One-click approve with optimistic UI
   - Creates automatic backup before apply
   - SHA-256 checksum validation prevents stale patches

4. **Audit Trail**
   - Complete history in JSONL logs
   - Backup paths for manual rollback
   - User attribution and timestamps

### Navigation

- Route: `http://127.0.0.1:3100/jarvis-codex`
- Navigation label: `🤖 Jarvis-Codex`
- Backend endpoint: `http://127.0.0.1:8015/jarvis_codex/*`

### API Endpoints (Core API)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jarvis_codex/propose` | Create new edit proposal |
| GET | `/jarvis_codex/proposals` | List all proposals (with filter) |
| GET | `/jarvis_codex/proposals/{id}` | Get single proposal by ID |
| POST | `/jarvis_codex/apply` | Apply approved proposal |
| POST | `/jarvis_codex/reject` | Reject proposal with reason |

### Security Model

**5-Layer Validation:**
1. **Scope enforcement**: Only `web/src/` and `devx/frontend/src/` allowed
2. **File size limit**: Max 50KB per file
3. **Confidence threshold**: Min 0.85 (configurable)
4. **Checksum validation**: SHA-256 prevents race conditions
5. **Atomic backup**: Full file backup before every apply

**Safety Guarantees:**
- ✅ No backend code modification (scope restricted to UI)
- ✅ Stale patch detection (checksum abort on mismatch)
- ✅ Reversible changes (backups in `web/backups/`)
- ✅ Complete audit trail (JSONL logs)
- ✅ Confidence gating (low-quality proposals blocked)

### Usage Example

**Approving a Proposal:**

1. Navigate to Jarvis-Codex panel
2. Select pending proposal from sidebar
3. Review diff and metadata:
   - File path and intent
   - Confidence score (≥85%)
   - Before/after comparison
4. Click "Approve"
5. **Instant feedback:** Status → "applied" (optimistic UI)
6. **Backend:** Creates backup, applies change
7. **Toast:** "✓ Proposal Applied — Backup: web/backups/..."

**Rejecting a Proposal:**

1. Select proposal
2. Click "Reject"
3. **Instant feedback:** Status → "rejected"
4. **Backend:** Logs to audit trail
5. Proposal removed from pending list

### Audit Trail

**Location:** `prompts/insights/jarvis_codex_audit.jsonl`

**Example Entry:**
```json
{
  "ts": "2025-10-10T02:45:30.123456+00:00",
  "proposal_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "applied",
  "user": "admin",
  "file": "web/src/components/header/HeaderTitle.tsx",
  "backup": "web/backups/HeaderTitle.tsx_20251010_024530.bak",
  "checksum_after": "a7f3b2e1..."
}
```

**Query Examples:**
```bash
# Count total applies
grep '"action":"applied"' prompts/insights/jarvis_codex_audit.jsonl | wc -l

# Find backups for specific file
grep 'HeaderTitle.tsx' prompts/insights/jarvis_codex_audit.jsonl | jq '.backup'

# Recent rejections
tail -20 prompts/insights/jarvis_codex_audit.jsonl | grep rejected
```

### Documentation

Full technical documentation: [`ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1.md`](../docs/JARVIS_CODEX_PHASE1.md)

---

## Usage Examples

### 1. Edit a Trait Value Model

1. Open DevX at http://127.0.0.1:3100
2. Select a trait from the browser (e.g., `SkillDNA.PresentationDNA`)
3. Click "Value Model" tab
4. Edit the canonical type, range, and unit
5. Click "Save Value Model"
6. Changes are validated and applied immediately

### 2. Create a Change Request (API)

```bash
curl -X POST http://127.0.0.1:8100/devx/api/traits/propose-change \
  -H "Content-Type: application/json" \
  -d '{
    "trait_path": "SkillDNA.PresentationDNA",
    "change_type": "add_value_model",
    "value_model": {
      "canonical_type": "numeric",
      "range": [0, 100],
      "unit": "skill_level"
    },
    "reason": "Adding value model for skill scoring",
    "author": "dev_user"
  }'
```

### 3. Validate and Apply CR

```bash
# Validate
curl http://127.0.0.1:8100/devx/api/traits/validate?cr_id=cr_abc123

# Apply (if valid)
curl -X POST http://127.0.0.1:8100/devx/api/traits/apply-change \
  -H "Content-Type: application/json" \
  -d '{"cr_id": "cr_abc123"}'
```

---

## Development

### Backend Development

**Run with auto-reload**:
```bash
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH uvicorn devx.backend.api:app --reload --port 8100
```

**Test API endpoints**:
```bash
# Health check
curl http://127.0.0.1:8100/health

# List traits
curl http://127.0.0.1:8100/devx/api/traits/list

# Get trait definition
curl "http://127.0.0.1:8100/devx/api/traits/definition?path=SkillDNA.PresentationDNA"
```

### Frontend Development

**Run with hot reload**:
```bash
cd ReDNACoreDemo/devx/frontend
pnpm dev --port 3100
```

**Build for production**:
```bash
pnpm build
pnpm preview
```

---

## Integration with CP++

DevX can be launched from Control Panel++ with a dedicated button.

**CP++ Integration** (future):
```python
# In control_panel_plus_plus.py
if st.button("🛠️ Open DevX"):
    open_devx()

def open_devx():
    # Check if DevX is running
    if not is_devx_running():
        # Start DevX
        subprocess.Popen(["./scripts/start_devx.sh"])
        time.sleep(2)

    # Open browser tab
    webbrowser.open("http://127.0.0.1:3100")
```

---

## Testing

### Backend Tests

```bash
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH python3 -m pytest tests/test_devx_traits.py -v
```

### Frontend Tests

```bash
cd devx/frontend
pnpm test
```

### Integration Tests

```bash
# Start DevX
./scripts/start_devx.sh

# Wait for startup
sleep 3

# Test health
curl http://127.0.0.1:8100/health

# Test frontend
curl http://127.0.0.1:3100

# Cleanup
./scripts/stop_devx.sh
```

---

## Troubleshooting

### Backend won't start

**Check port availability**:
```bash
lsof -ti:8100
```

**View logs**:
```bash
tail -f ReDNACoreDemo/devx/logs/backend.log
```

### Frontend build fails

**Clear node_modules and reinstall**:
```bash
cd ReDNACoreDemo/devx/frontend
rm -rf node_modules
pnpm install
```

### Changes not appearing

**Clear browser cache**:
- Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

**Restart backend**:
```bash
./scripts/stop_devx.sh
./scripts/start_devx.sh
```

---

## Roadmap

### Phase 1: Trait Workshop ✅ (Current)
- Trait browser with filtering
- Value model editor
- Basic validation
- Change request API

### Phase 2: Trait Semantics Editor (Q1 2026)
- Inclusion/exclusion criteria editor
- Examples and counterexamples manager
- Visual semantic validation
- AI Steward integration

### Phase 3: Observation Studio (Q2 2026)
- Import observation files
- Manual trait assignment UI
- Bulk operations
- Observation validation pipeline

### Phase 4: Agent Behavior Studio (Q3 2026)
- Coach prompt editor
- Intent routing visualizer
- Performance metrics dashboard
- A/B testing framework

---

## Support

**Documentation**: `/docs/DEVX_*.md`
**Issues**: GitHub Issues (ReDNA repository)
**Questions**: ReDNA development channel

---

**Last Updated**: 2025-10-10
**Authors**: ReDNA Core Team
**License**: Proprietary
