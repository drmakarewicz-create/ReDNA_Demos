# Developer Explorer User Guide

**Last Updated:** 2025-10-04
**Version:** 2.0 (Streamlined Navigation)

---

## 📖 Overview

The **Developer Explorer** is an internal console for ReDNA system development, testing, and operations. It provides specialized tools for:

- Managing coach personas and CReDNA configurations
- Editing trait containers and RR baselines
- Observing system traces, logs, and service health
- Reviewing audit logs and governance protocols
- Testing, debugging, and artifact management

**Audience:** Developers, analysts, and system operators working on ReDNA demos and infrastructure.

---

## 🗺️ Navigation Structure

Developer Explorer uses a **7-section** navigation model:

```
🛠️ Developer Explorer
├── 1️⃣ Coach Workshop          Persona registry, CReDNA preview, templates
├── 2️⃣ CReDNA Studio           Import/export, trait graph, coverage analysis
├── 3️⃣ Container Studio        Trait editing with AI assistance
├── 4️⃣ RR Baselines Lab        RR baseline configuration and management
├── 5️⃣ Observability            Traces, logs, service health, feedback analytics, testing
├── 6️⃣ Governance & Audit       Audit logs, dormancy, sensitivity gating, provenance
└── 7️⃣ Developer Tools          Testing, artifacts, HTTP helpers, system settings
```

---

## 1️⃣ Coach Workshop

### Purpose
Manage persona registry, test CReDNA templates, and preview Head Coach configurations.

### Key Features
- **Persona Registry Viewer**: See all registered coaches (Head Coach, Photo Coach, Relationship Coach, etc.)
- **CReDNA Template Preview**: Test motivator templates with live/simulated curiosity data
- **Live Preview Mode**: Pull real curiosity data from Core for a specific user
- **Simulation Mode**: Use demo baselines for safe experimentation

### Common Workflows

#### View Persona Registry
1. Navigate to **Coach Workshop**
2. Review persona table (ID, description, prompt source, status)
3. Check for missing prompts or configuration issues

#### Test CReDNA Templates
1. Enable **Live Mode** toggle (or use simulation)
2. Enter a **Core User ID** (e.g., `demo_user`)
3. Click **Refresh Live Data**
4. Browse top curiosity traits and preview motivator templates

#### Export Persona Snapshot
1. Scroll to **Export Registry Snapshot**
2. Click **Download Persona Registry (JSON)**
3. Use for documentation or debugging

---

## 2️⃣ CReDNA Studio

### Purpose
Manage Coach ReDNA (CReDNA) configurations with import/export, versioning, and coverage analysis.

### Key Features
- **CReDNA Import/Export**: Load and save coach-specific behavior models
- **Trait Graph Viewer**: Visualize CReDNA trait coverage
- **Coverage Analysis**: See which traits have templates vs. gaps
- **Version Management**: Track CReDNA versions with rollback capability

### Common Workflows

#### Import CReDNA Configuration
1. Navigate to **CReDNA Studio**
2. Select **Import CReDNA** tab
3. Upload JSON file or paste CReDNA configuration
4. Review validation warnings
5. Click **Apply Import** (if `WRITE_PROTECT=false`)

#### Analyze Coverage
1. Select a coach (e.g., `photo_coach`)
2. View **Coverage Analysis** tab
3. Review trait families with template counts
4. Identify gaps (traits without templates)

#### Export CReDNA for Backup
1. Select coach
2. Click **Export CReDNA**
3. Download JSON file with timestamp
4. Store in version control or backup location

---

## 3️⃣ Container Studio

### Purpose
Edit trait containers with AI-powered suggestions and schema validation.

### Key Features
- **Trait Editor**: WYSIWYG editor for container and trait properties
- **AI Suggestions**: LLM-powered recommendations for trait values
- **Schema Validation**: Real-time validation against trait schema
- **Live Mode**: Edit actual user traits (with write-protect)

### Common Workflows

#### Edit a Trait
1. Navigate to **Container Studio**
2. Select **Live Mode** or **Simulation Mode**
3. Choose a **Container** (e.g., `PhotoPreferences`)
4. Select a **Trait** (e.g., `lighting_style`)
5. Edit trait properties (value, UCN, provenance)
6. Click **Save Changes**

#### Get AI Suggestions
1. Select a trait
2. Click **AI Suggest** button
3. Review LLM-generated recommendations
4. Accept or modify suggestions
5. Save changes

---

## 4️⃣ RR Baselines Lab

### Purpose
Configure and manage Relevance Rating (RR) baselines for UCN/RR computations.

### Key Features
- **Baseline Configuration**: Edit `mean_ucn`, `std_ucn`, `sample_size` for defaults and per-container
- **Demo Mode**: Enable/disable demo baselines
- **Import/Export**: Backup and restore baseline configurations
- **Validation**: Preflight checks for baseline integrity

### Common Workflows

#### Update RR Baselines
1. Navigate to **RR Baselines Lab**
2. View current baselines (defaults + container overrides)
3. Edit baseline values (mean, std, sample size)
4. Click **Save Baselines** (creates `.bak` file)
5. Review change log

#### Enable Demo Mode
1. Toggle **Demo Mode Enabled**
2. Save configuration
3. Demo baselines will override canonical baselines in UCN/RR calculations

#### Import Baselines from File
1. Click **Import Baselines** tab
2. Upload `rr_baselines.json` file
3. Review preflight validation
4. Click **Apply Import**

---

## 5️⃣ Observability

### Purpose
Unified observability for traces, logs, service health, feedback analytics, and testing.

### Sub-Tabs

#### 📊 Trace Viewer
**Purpose:** Visualize unified ORS traces with waterfall rendering

**Workflows:**
1. **Search Traces**: Enter trace ID or time range
2. **View Waterfall**: See component timings (Dev Explorer, UCN/RR, Core)
3. **Export Trace**: Download trace JSON for analysis

**Example:**
```
Trace ID: abc123
├── [Dev Explorer] ingest_text → 45ms
├── [UCN/RR] compute_ucn → 120ms
├── [Core] store_evidence → 30ms
└── [UCN/RR] compute_rr → 80ms
Total: 275ms
```

#### 💚 Service Health
**Purpose:** Ping microservices and view uptime

**Workflows:**
1. Click **Ping UCNRR**, **Ping Core**, **Ping LLM**
2. Review latency and status codes
3. Check service uptime table

#### 📜 Log Tailer
**Purpose:** View logs from multiple sources with auto-refresh

**Workflows:**
1. Select log source (diagnostics, scheduler, trace logs)
2. Enable **Auto-refresh (5s)** for real-time monitoring
3. Download log file for offline analysis

#### 📈 Feedback Analytics
**Purpose:** Analyze trait scores, planning weights, and ToleranceForNudging

**Workflows:**
1. Select a user
2. View **Trait Scores** (-1.0 to 1.0 based on helpful/not helpful feedback)
3. Review **Planning Weights** (0.5-1.5 multipliers for motivator planning)
4. Check **Tolerance for Nudging** (emergent trait from accept/dismiss/undo patterns)

**Example:**
```
User: bstest
Trait: PhotoPreferences.lighting_style
Score: 0.75 (15↑ helpful, 5↓ not helpful)
Planning Weight: 1.38 (boost by 38%)
```

#### 🧪 Testing & QA
**Purpose:** Run tests and validate system health

**Workflows:**
1. **Golden Path Test**: End-to-end regression (enqueue → accept → undo → Draft Chat)
2. **Loop Test**: Full pipeline (ingest → UCN → RR → motivator)
3. **Prompt Source Checks**: Validate all persona prompts are accessible

---

## 6️⃣ Governance & Audit

### Purpose
Audit logging, governance protocols, rollback capability, and provenance tracking.

### Sub-Tabs

#### 📋 Audit Logs
**Purpose:** View change history with before/after comparison

**Workflows:**
1. Select **Audit Log Type** (RR Baselines, CReDNA Imports, Nudge Actions, Head Coach Ops)
2. Set **Max entries** (default: 50)
3. Expand entries to see before/after diffs
4. Use **Rollback Interface** to restore previous states (if `WRITE_PROTECT=false`)

**Example:**
```
Change #1 — RR Baselines — 2025-10-04 14:32:15 UTC
Before:
  defaults.mean_ucn: 0.45
After:
  defaults.mean_ucn: 0.50
[Rollback] button available
```

#### ⏳ Dormancy Management
**Purpose:** Manage user lifecycle states and heir transfer

**Workflows:**
1. **View Lifecycle States**: See user states (active, dormant_3m/6m/12m, deceased)
2. **Update State**: Transition user to new lifecycle state
3. **Execute Heir Transfer**: Transfer ReDNA traits from deceased user to heir
4. **View Transfer History**: Review past inheritance operations

**Lifecycle States:**
- `active`: Normal operation
- `dormant_3m`: Inactive for 3 months
- `dormant_6m`: Inactive for 6 months
- `dormant_12m`: Inactive for 12 months
- `deceased`: Permanent state, enables heir transfer

#### 🔒 Sensitivity Gating
**Purpose:** Manage consent and UCN threshold unlocking for sensitive traits

**Workflows:**
1. **View Consent Records**: See consent status (granted/pending/revoked) per user × trait
2. **Grant/Revoke Consent**: Manually update consent for sensitive traits
3. **Configure Sensitivity Levels**: Edit sensitivity registry (PUBLIC, STANDARD, SENSITIVE, RESTRICTED, PRIVATE)
4. **Check Visibility**: Test if a trait is visible to a user given current UCN

**Example:**
```
User: bstest
Trait: HealthData.medical_history
Sensitivity Level: SENSITIVE
UCN Threshold: 0.8
Consent Required: Yes
Current UCN: 0.65
Result: ⚠️ HIDDEN (UCN below threshold AND no consent)
```

#### 🔍 Provenance Explorer
**Purpose:** Diff viewer and replay capability for state changes

**Workflows:**
1. Select two snapshots to compare
2. View side-by-side diff
3. Replay state changes for debugging

---

## 7️⃣ Developer Tools

### Purpose
Testing, artifact browsing, HTTP request building, and system configuration.

### Sub-Tabs

#### 🧪 Test Runner
**Purpose:** Run pytest tests from the Dev Explorer UI

**Workflows:**
1. Select test file (e.g., `test_nudge_store.py`)
2. Choose **Run All** or select specific test function
3. View results (status, passed, failed, duration)
4. Review full output and errors

#### 📁 Artifact Browser
**Purpose:** Browse and view user data files and automation logs

**Workflows:**
1. Use search to filter artifacts
2. Click file to view contents
3. Download artifact for offline analysis

#### 🌐 HTTP Request Builder
**Purpose:** Send HTTP requests to ReDNA APIs

**Workflows:**
1. Select endpoint (e.g., `/hc/say`, `/hc/tasks/queue`)
2. Enter **User ID** and **Base URL**
3. Edit request body (JSON)
4. Click **Send Request**
5. View response (formatted JSON or raw)

**Example:**
```json
POST http://localhost:8001/hc/say?user_id=bstest
{
  "message": "What should I do next?",
  "role": "user"
}
```

#### ⚙️ System Settings
**Purpose:** Configure holistic scheduler, soft imports, and view environment variables

**Workflows:**
1. **Holistic Scheduler**: Enable/disable, set cadence (hours)
2. **Soft Import Settings**: Configure PaDNA import behavior
3. **Write Protect**: View current write-protect status
4. **Environment Variables**: Review all ReDNA-related env vars

---

## 🔧 Common Operations

### Pre-Demo Checklist

1. **Run Golden Path Test** (Observability → Testing & QA)
   - Ensures nudge workflow is functional
2. **Check Service Health** (Observability → Service Health)
   - Ping UCNRR, Core, LLM
3. **Review Audit Logs** (Governance & Audit → Audit Logs)
   - Ensure no unexpected changes
4. **Verify RR Baselines** (RR Baselines Lab)
   - Confirm demo mode enabled/disabled as needed
5. **Test Trace Viewer** (Observability → Trace Viewer)
   - Run loop test and verify waterfall rendering

### Post-Demo Cleanup

1. **Disable Write-Protect** (set `WRITE_PROTECT=false`)
2. **Clear Test User Data** (Artifact Browser → delete test users)
3. **Review Feedback Data** (Observability → Feedback Analytics)
4. **Export Audit Logs** (Governance & Audit → download JSONL files)

### Troubleshooting

#### "Service unreachable" errors
- Check **Service Health** tab for ping results
- Verify base URLs in **System Settings → Environment Variables**
- Ensure microservices are running (use `ps aux | grep uvicorn`)

#### "Write-protect ON" prevents saves
- Set `WRITE_PROTECT=false` environment variable
- Restart Streamlit app
- Verify status in **System Settings → Write Protect**

#### Trace Viewer shows no results
- Check **Log Tailer** to see if ORS logs are being written
- Verify trace ID matches format (e.g., `trace_abc123`)
- Ensure time range filters are correct

#### Feedback Analytics shows "No data"
- Run nudge workflow first (enqueue → accept → feedback)
- Check `data/users/{user_id}/feedback_aggregates.json` exists
- Verify user ID matches actual user directory

---

## 🚀 Advanced Usage

### Scripting with Dev Explorer

While Dev Explorer is a UI tool, you can automate common operations:

```bash
# Run golden path test via script
python scripts/golden_path_test.py

# Run full test suite
./scripts/run_tests.sh

# Export RR baselines
python -c "from ExplorerDev import rr_baseline_utils; print(rr_baseline_utils.export_baselines())"
```

### Integrating with CI/CD

Dev Explorer modules can be imported for automated checks:

```python
from ExplorerDev.diag_utils import run_prompt_source_checks

issues = run_prompt_source_checks()
if issues:
    raise RuntimeError(f"Prompt validation failed: {issues}")
```

### Custom Workflows

Create custom workflows by combining Dev Explorer tools:

**Example: Bulk User Lifecycle Update**
1. Export user list from Artifact Browser
2. Script lifecycle state updates using `dormancy.py` API
3. Verify in Governance & Audit → Dormancy Management

---

## 📚 Related Documentation

- [Dev_Explorer_Audit.md](Dev_Explorer_Audit.md) — Analysis of redesign
- [Dev_Explorer_Architecture.md](Dev_Explorer_Architecture.md) — Technical architecture
- [Testing_Guide.md](Testing_Guide.md) — Comprehensive testing documentation
- [Rollback_Procedures.md](Rollback_Procedures.md) — Rollback paths for major changes
- [Core_Benchmarks_Roadmap.md](Core_Benchmarks_Roadmap.md) — Project roadmap

---

## 🆘 Support

For issues or questions:

1. Check **Troubleshooting** section above
2. Review audit logs for unexpected changes
3. Consult architecture documentation
4. Reach out to the ReDNA development team

---

**Version History:**
- **2.0** (2025-10-04): Streamlined to 7-section navigation, added Observability and Governance tabs
- **1.0** (2025-09-28): Initial version with 9+ sections
