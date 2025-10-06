# Developer Explorer Audit & Redesign Plan

**Date:** 2025-10-04
**Status:** Analysis Complete → Implementation Ready

---

## 🎯 Executive Summary

The Developer Explorer (`ExplorerDev/explorer_dev.py`, 6,274 lines) has grown organically and now contains:
- **Multiple overlapping diagnostic tools** (ORS Console, Diagnostics, Developer Tools)
- **Unclear separation of concerns** between modules
- **Missing UI implementations** for recently built backend infrastructure (trace consolidation, audit logs, feedback analytics)
- **Scattered navigation** across 9+ sections with unclear purposes

**Goal:** Streamline Dev Explorer into a focused, production-ready developer console with clear purpose for each module and full UI coverage for existing backend capabilities.

---

## 📊 Current State Analysis

### Existing Sections (9 total)

| Section | Purpose | Lines | Clarity | Utility | Action |
|---------|---------|-------|---------|---------|--------|
| **Coach Workshop** | Persona registry, CReDNA preview, template testing | ~800 | ⚠️ Medium | ✅ High | **KEEP + REFACTOR** |
| **CReDNA Studio** | CReDNA import/export, trait graph, coverage | ~400 | ✅ High | ✅ High | **KEEP** |
| **Container Studio** | Trait container editing, AI suggestions | ~600 | ✅ High | ✅ High | **KEEP** |
| **RR Baselines Lab** | RR baseline configuration, import/export | ~300 | ✅ High | ✅ High | **KEEP** |
| **Provenance Lab** | Diff viewer, replay (basic) | ~200 | ⚠️ Medium | ⚠️ Medium | **ENHANCE** |
| **UI Contracts Card** | Shell contract validation | ~100 | ✅ High | ⚠️ Low | **ARCHIVE** (dev-only) |
| **Regression Card** | Quick regression checks | ~80 | ⚠️ Medium | ⚠️ Medium | **MERGE** into Testing |
| **System Settings** | Holistic scheduler, soft imports | ~150 | ⚠️ Medium | ✅ High | **KEEP + RENAME** |
| **User Management** | User ops (basic placeholders) | ~120 | ❌ Low | ❌ Low | **REMOVE** (not implemented) |
| **Diagnostics** | Service health, loop testing, ORS console | ~900 | ❌ Low | ✅ High | **SPLIT + REFACTOR** |
| **Developer Tools** | Test runner, log tails, artifact browser, HTTP helpers | ~540 | ✅ High | ✅ High | **KEEP** |

### Missing UI for Existing Backend

| Backend Module | Purpose | Status | Missing UI |
|----------------|---------|--------|------------|
| `trace_consolidation.py` | Unified ORS trace schema | ✅ Built | **Waterfall Viewer** |
| `audit_viewer.py` | Audit log viewer (Streamlit stub) | ⚠️ Stub | **Full UI Integration** |
| `feedback_analytics.py` | Trait scores, planning weights | ✅ Built | **Analytics Dashboard** |
| `dormancy.py` | Lifecycle states, heir transfer | ✅ Built | **Governance Dashboard** |
| `sensitivity_gating.py` | Consent, UCN thresholds | ✅ Built | **Gating Config UI** |
| `trace_viewer.py` | Waterfall HTML renderer | ⚠️ Stub | **Dev Explorer Tab** |

### Overlapping Functionality

**Problem:** Three separate sections handle diagnostics/observability:
1. **ORS Console** (`ors_console.py`) — Service pings, log tailer, trace explorer
2. **Diagnostics** (in `explorer_dev.py`) — Loop testing, ingest RT, prompt checks, snapshot viewer
3. **Developer Tools** (`dev_tools_ui.py`) — Test runner, log tails, artifact browser

**Confusion:** Users don't know where to go for logs, traces, or service health.

---

## 🚀 Proposed Redesign

### New Navigation Structure (7 sections)

```
🛠️ Developer Explorer
├── 1️⃣ Coach Workshop          [Persona registry, CReDNA preview, template testing]
├── 2️⃣ CReDNA Studio           [Import/export, trait graph, coverage, versioning]
├── 3️⃣ Container Studio        [Trait editing, AI suggestions, schema validation]
├── 4️⃣ RR Baselines Lab        [Baseline config, demo mode, import/export]
├── 5️⃣ Observability            [🆕 UNIFIED: Traces, Logs, Service Health, Feedback Analytics]
├── 6️⃣ Governance & Audit       [🆕 Audit logs, Dormancy, Sensitivity, Rollback]
└── 7️⃣ Developer Tools          [Testing, Artifacts, HTTP Helpers, System Settings]
```

### Detailed Module Breakdown

#### 1️⃣ Coach Workshop (Keep + Refactor)
**Purpose:** Persona registry management and CReDNA template testing
**Current Issues:** Unclear navigation, mixed responsibilities
**Changes:**
- Separate into clear sub-tabs: **Registry | Templates | Live Preview**
- Move system settings (scheduler, soft imports) to Developer Tools
- Add persona analytics (switch frequency, usage patterns)
- Streamline CReDNA preview integration

#### 2️⃣ CReDNA Studio (Keep)
**Purpose:** CReDNA import/export, trait graph, coverage analysis
**Status:** ✅ Already well-designed
**Changes:** Minimal — add coverage badges to status strip

#### 3️⃣ Container Studio (Keep)
**Purpose:** Trait container editing with AI assistance
**Status:** ✅ Already well-designed
**Changes:** None

#### 4️⃣ RR Baselines Lab (Keep)
**Purpose:** RR baseline configuration and management
**Status:** ✅ Already well-designed
**Changes:** Add validation heuristics UI

#### 5️⃣ Observability (NEW — Unified Diagnostics)
**Purpose:** Single source for all observability needs
**Sub-tabs:**
- **Trace Viewer** 🆕
  - Waterfall visualization using `trace_viewer.py`
  - Trace search by ID or time range
  - Component filtering (Dev Explorer, UCN/RR, Core)
  - Export to JSON
- **Service Health**
  - Service pings (UCNRR, Core, LLM)
  - Health dashboard with uptime
  - Endpoint configuration
- **Log Tailer**
  - Multi-source log viewer (diagnostics, scheduler, traces)
  - Auto-refresh with 5s cadence
  - Download capability
- **Feedback Analytics** 🆕
  - Trait score dashboard (helpful/not helpful aggregates)
  - Planning weights visualization
  - ToleranceForNudging trend chart
  - Per-user feedback history
- **Testing & QA**
  - Golden path test runner
  - Loop test (ingest → UCN → RR → motivator)
  - Prompt source validation

#### 6️⃣ Governance & Audit (NEW)
**Purpose:** Audit logging, governance protocols, rollback capability
**Sub-tabs:**
- **Audit Log Viewer** 🆕
  - RR Baselines change history
  - CReDNA import audit trail
  - Head Coach Ops (nudge actions)
  - User state modifications
  - Rollback interface with safety checks
- **Dormancy Management** 🆕
  - Lifecycle state viewer (active, dormant_3m/6m/12m, deceased)
  - Heir transfer interface
  - Batch lifecycle updates
- **Sensitivity Gating** 🆕
  - Consent record viewer
  - UCN threshold configuration
  - Sensitive trait registry
  - Grayed preview settings
- **Provenance Explorer**
  - Enhanced diff viewer
  - Replay capability (from existing Provenance Lab)
  - Before/after comparison

#### 7️⃣ Developer Tools (Keep + Expand)
**Purpose:** Testing, artifacts, HTTP helpers, system configuration
**Sub-tabs:**
- **Test Runner** (existing)
- **Artifact Browser** (existing)
- **HTTP Request Builder** (existing)
- **System Settings** 🆕 (moved from "System Settings" section)
  - Holistic scheduler config
  - Soft import settings
  - Write-protect toggle
  - Environment variable viewer

---

## 🗑️ Modules to Remove/Archive

### Immediate Removal
- **User Management section** — Not implemented, placeholders only
- **UI Contracts Card** — Developer-only, not user-facing (move to archive or Developer Tools)
- **Regression Card** — Merge into Observability → Testing & QA

### Archive to `archive/dev_explorer/`
- Legacy diagnostic functions that are now covered by unified Observability
- Redundant health check implementations
- Old snapshot viewer code (if superseded)

---

## 🛠️ Implementation Plan (Overnight Megabatch)

### Phase 1: Create Missing UI (Priority 1)

**Task 1.1:** Build Trace Viewer UI
- File: `ExplorerDev/tabs/observability.py` (new)
- Integrate `trace_viewer.py` waterfall rendering
- Add trace search, filtering, export
- Component color coding

**Task 1.2:** Build Audit Viewer UI
- Integrate `audit_viewer.py` into Governance tab
- Add rollback interface with safety checks
- Before/after diff visualization
- Filter by log type, date range, user

**Task 1.3:** Build Feedback Analytics Dashboard
- Visualize trait scores from `feedback_analytics.py`
- Planning weights table (0.5-1.5 multipliers)
- ToleranceForNudging trend line
- Export to CSV/JSON

**Task 1.4:** Build Dormancy Management UI
- Lifecycle state viewer (table view)
- Heir transfer interface with validation
- Batch update capability
- Deceased user exclusion preview

**Task 1.5:** Build Sensitivity Gating UI
- Consent record table (user × trait)
- UCN threshold config editor
- Grayed preview settings
- Bulk consent operations

### Phase 2: Refactor Navigation (Priority 2)

**Task 2.1:** Create Tab Structure Files
```
ExplorerDev/tabs/
├── __init__.py
├── coach_workshop.py          (refactored from explorer_dev.py)
├── observability.py           (NEW — unified diagnostics)
├── governance.py              (NEW — audit + dormancy + sensitivity)
└── developer_tools.py         (refactored from dev_tools_ui.py)
```

**Task 2.2:** Refactor Coach Workshop
- Extract from `explorer_dev.py` main function
- Separate sub-tabs: Registry | Templates | Live Preview
- Move system settings to Developer Tools
- Add persona analytics

**Task 2.3:** Consolidate Diagnostics
- Merge ORS Console, Diagnostics, and relevant Developer Tools functions
- Create unified Observability tab with 5 sub-tabs
- Remove duplicated code

**Task 2.4:** Update Main Navigation
- Reduce from 9-11 sections to 7
- Update sidebar radio with new structure
- Add section descriptions/help text

### Phase 3: Remove/Archive (Priority 3)

**Task 3.1:** Archive Deprecated Code
- Create `archive/dev_explorer/deprecated/`
- Move User Management placeholder
- Move UI Contracts (or integrate into Developer Tools)
- Document what was archived and why

**Task 3.2:** Remove Dead Code
- Identify unused helper functions
- Remove duplicated health checks
- Clean up imports

### Phase 4: Documentation (Priority 4)

**Task 4.1:** Create Dev Explorer User Guide
- File: `docs/Dev_Explorer_Guide.md`
- Purpose of each section
- Common workflows (e.g., "How to review audit logs", "How to analyze traces")
- Screenshots/examples
- Troubleshooting

**Task 4.2:** Update Architecture Docs
- Document new tab structure
- Explain observability flow
- Governance protocol usage

**Task 4.3:** Update Roadmap
- Mark Dev Explorer rework as complete
- Update progress tracker

---

## 🎯 Success Metrics

After implementation, Dev Explorer should achieve:

✅ **Clarity**: Every section has a clear, distinct purpose
✅ **Coverage**: All backend modules have functional UIs
✅ **Efficiency**: No overlapping or redundant functionality
✅ **Discoverability**: Users can find features without confusion
✅ **Documentation**: Comprehensive guide for all workflows

---

## 📋 Task Checklist

### Phase 1: Create Missing UI
- [ ] `ExplorerDev/tabs/observability.py` — Trace Viewer sub-tab
- [ ] `ExplorerDev/tabs/observability.py` — Feedback Analytics sub-tab
- [ ] `ExplorerDev/tabs/governance.py` — Audit Viewer sub-tab
- [ ] `ExplorerDev/tabs/governance.py` — Dormancy Management sub-tab
- [ ] `ExplorerDev/tabs/governance.py` — Sensitivity Gating sub-tab

### Phase 2: Refactor Navigation
- [ ] `ExplorerDev/tabs/coach_workshop.py` — Extracted and refactored
- [ ] `ExplorerDev/tabs/observability.py` — Unified diagnostics
- [ ] `ExplorerDev/tabs/developer_tools.py` — System Settings integration
- [ ] `ExplorerDev/explorer_dev.py` — Updated main navigation (7 sections)

### Phase 3: Remove/Archive
- [ ] `archive/dev_explorer/deprecated/user_management.py`
- [ ] `archive/dev_explorer/deprecated/ui_contracts.py`
- [ ] `archive/dev_explorer/deprecated/regression_card.py`
- [ ] Clean up unused imports and helper functions

### Phase 4: Documentation
- [ ] `docs/Dev_Explorer_Guide.md` — Complete user guide
- [ ] `docs/Dev_Explorer_Architecture.md` — Technical architecture
- [ ] `docs/Core_Benchmarks_Roadmap.md` — Updated progress tracker

---

## 🚦 Execution Readiness

**Status:** ✅ **APPROVED FOR OVERNIGHT MEGABATCH**

All analysis complete. Implementation can proceed immediately with clear specifications for each task.
