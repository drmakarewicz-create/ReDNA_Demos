# Deprecated Dev Explorer Code

**Date Archived:** 2025-10-04
**Reason:** Developer Explorer streamlined from 9-11 sections to 7 focused sections

## Archived Components

### 1. User Management Section
**File:** `user_management_DEPRECATED.py`
**Reason:** Not implemented beyond placeholder functions. User management should be handled by Core, not Dev Explorer.
**Status:** Placeholder-only, no loss of functionality

### 2. UI Contracts Card
**File:** `ui_contracts_DEPRECATED.py`
**Reason:** Developer-only contract validation. Not user-facing. Can be optionally integrated into Developer Tools if needed.
**Status:** Functional but niche use case

### 3. Regression Card (standalone)
**File:** `regression_card_DEPRECATED.py`
**Reason:** Merged into Observability → Testing & QA tab for better organization
**Status:** Functionality preserved in new Observability tab

### 4. System Settings (standalone section)
**File:** `system_settings_DEPRECATED.py`
**Reason:** Moved to Developer Tools → System Settings tab to consolidate developer-facing utilities
**Status:** Functionality preserved in new Developer Tools tab

## What Was Kept

All core functionality was preserved in the new 7-section structure:

| Old Section | New Location |
|-------------|-------------|
| Coach Workshop | Coach Workshop (unchanged) |
| CReDNA Studio | CReDNA Studio (unchanged) |
| Container Studio | Container Studio (unchanged) |
| RR Baselines Lab | RR Baselines Lab (unchanged) |
| Provenance Lab | Governance & Audit → Provenance Explorer |
| Diagnostics + ORS Console | Observability (unified) |
| Developer Tools | Developer Tools (expanded with System Settings) |
| User Management | REMOVED (not implemented) |
| UI Contracts | ARCHIVED (developer-only) |
| Regression Card | Observability → Testing & QA |
| System Settings | Developer Tools → System Settings |

## Recovery Instructions

If any archived functionality is needed:

1. Locate the relevant file in this directory
2. Review the code and extract needed functions
3. Integrate into the appropriate new tab structure
4. Update imports and dependencies
5. Test thoroughly before deploying

## New Tab Structure

### Observability (`ExplorerDev/tabs/observability.py`)
- Trace Viewer (waterfall visualization)
- Service Health (pings, uptime)
- Log Tailer (multi-source)
- Feedback Analytics (trait scores, planning weights, ToleranceForNudging)
- Testing & QA (golden path, loop test, prompt checks)

### Governance & Audit (`ExplorerDev/tabs/governance.py`)
- Audit Logs (RR, CReDNA, Nudges, Head Coach Ops)
- Dormancy Management (lifecycle states, heir transfer)
- Sensitivity Gating (consent, UCN thresholds)
- Provenance Explorer (diff viewer, replay)

### Developer Tools (enhanced)
- Test Runner
- Log Tails
- Artifact Browser
- HTTP Request Builder
- **System Settings** (NEW — holistic scheduler, soft imports, write-protect, env vars)

---

*For questions or to restore archived functionality, consult the Dev Explorer User Guide and Architecture docs.*
