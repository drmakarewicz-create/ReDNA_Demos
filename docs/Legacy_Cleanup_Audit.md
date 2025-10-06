# Legacy Code Cleanup Audit

**Date:** 2025-10-04
**Status:** Analysis Complete → Ready for Cleanup

---

## 🎯 Executive Summary

The Demo Root has accumulated significant technical debt:
- **24 markdown files** in root (should be in `docs/`)
- **27 Python scripts** in root (should be organized by purpose)
- **2 legacy control panels** (`control_panel_plus.py`, `control_panel_plus_plus.py`)
- **3 deprecated directories** (`ExplorerFinal_broken_*`, `2025-09-19_*`, legacy test dirs)
- **Duplicate utilities** (multiple AI clients, test harnesses)

**Impact:** Confusion for onboarding, difficulty finding active code, cluttered git history

---

## 📊 Current State

### Root Directory Files (by category)

#### Control Panels (2 files)
1. `control_panel_plus.py` — Legacy v1 control panel
2. `control_panel_plus_plus.py` — **ACTIVE** (current entrypoint per roadmap)

**Action:** Archive `control_panel_plus.py`, keep `control_panel_plus_plus.py`

#### Documentation (24 .md files in root, should be in docs/)
```
ARCHITECTURE_REFACTOR.md
BACKUP_README.md
CP_PLUS_PLUS_DEV_EXPLORER_INTEGRATION.md
CURIOSITY_CPLUSPLUS_INTEGRATION.md
DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md
HC_CONVERSATION_REVIEW_SETUP.md
HC_FUTURE_IMPROVEMENTS.md
HC_TESTING_GUIDE.md
HC_V1_COMPLETE.md
HC_V2_SPRINT1A_COMPLETE.md
HC_V2_SPRINT1B_COMPLETE.md
HC_V2_SPRINT1B_SUMMARY.md
HEAD_COACH_UCN_INTEGRATION_SUMMARY.md
HEAD_COACH_UI_IMPROVEMENTS.md
IMPLEMENTATION_SUMMARY.md
INDEX.md
PHOTO_IMPORT_TROUBLESHOOTING.md
QUICK_START_RENDERING.md
README.md  ← KEEP IN ROOT
READY_FOR_SPRINT_1B.md
SAFE_UI_FIXES_MANUAL.md
SESSION_SUMMARY.md
SESSION_SUMMARY_SPRINT1B.md
UI_CLEANUP_SUMMARY.md
```

**Action:** Move 23 files to `docs/historical/` (keep README.md in root)

#### Python Scripts (27 files in root)

**AI/LLM Clients (potential duplicates):**
- `llama3_client.py` — LLM client implementation
- `ai_control_panel.py` — AI-powered control panel (legacy?)
- `ai_control_panel_agent.py` — AI agent for control panel
- `prompt_loader.py` — Prompt loading utility

**Services:**
- `ucnrr_service.py` — UCN/RR service (likely superseded by ReDNACoreDemo)
- `ucnrr_app.py` — UCN/RR app entrypoint
- `ucn_rr_ai.py` — UCN/RR with AI integration

**Core Operations:**
- `core_ai_propagation.py` — AI-powered Core operations
- `batch_rescore.py` — Batch rescoring utility

**Testing (many in root, should be in tests/ or scripts/):**
- `test_hc_acceptance.py`
- `test_hc_v2_acceptance.py`
- `test_debug_task.py`
- `test_check_state.py`
- `test_debug_test5.py`
- `test_hc_v2_sprint1b_acceptance.py`
- `test_hc_v2_sprint1c_acceptance.py`
- `test_hc_v2_sprint2a_acceptance.py`
- `test_padna_delta_wiring.py`
- `test_photo_coach_acceptance.py`
- `test_hc_conversations.py`
- `test_bidirectional_traits.py`
- `test_container_discovery.py`

**Viewers/Tools:**
- `resolved_viewer.py` — ReDNA resolved state viewer
- `golden_path_harness.py` — Golden path test harness
- `TestExplorer.py` — Test explorer (legacy?)

**Action:** Categorize and move to appropriate directories

#### Deprecated Directories (3)
1. `ExplorerFinal_broken_1758381738/` — Broken backup from Sep 24
2. `2025-09-19_20-38-36/` — Timestamped backup directory
3. Potentially: `SingleCoach/`, `RSC_Sandbox/` (if unused)

**Action:** Archive to `archive/old_versions/`

---

## 🗂️ Proposed Directory Structure

### After Cleanup

```
ReDNA_Demos/
├── README.md                          ← ONLY markdown in root
├── .env, .gitignore, Makefile        ← Config files
├── control_panel_plus_plus.py        ← ACTIVE entrypoint
│
├── ExplorerFinal/                    ← Production explorer
├── ExplorerDev/                      ← Dev console
├── ReDNACoreDemo/                    ← Core backend
│
├── docs/                             ← ALL documentation
│   ├── Core_Benchmarks_Roadmap.md
│   ├── Dev_Explorer_Guide.md
│   ├── Analytics_Guide.md
│   ├── historical/                   ← 🆕 Moved from root
│   │   ├── ARCHITECTURE_REFACTOR.md
│   │   ├── HC_V1_COMPLETE.md
│   │   ├── SESSION_SUMMARY.md
│   │   └── ... (23 historical .md files)
│   └── sprint_summaries/             ← 🆕 Optional organization
│       ├── HC_V2_SPRINT1A_COMPLETE.md
│       ├── HC_V2_SPRINT1B_COMPLETE.md
│       └── ...
│
├── scripts/                          ← Utility scripts
│   ├── batch_rescore.py             ← 🆕 Moved from root
│   ├── golden_path_test.py
│   ├── run_tests.sh
│   └── utilities/                    ← 🆕 Helper scripts
│       ├── resolved_viewer.py
│       └── prompt_loader.py
│
├── tests/                            ← 🆕 All test files
│   ├── acceptance/
│   │   ├── test_hc_acceptance.py
│   │   ├── test_hc_v2_acceptance.py
│   │   ├── test_photo_coach_acceptance.py
│   │   └── ...
│   └── integration/
│       ├── test_bidirectional_traits.py
│       ├── test_container_discovery.py
│       └── ...
│
├── archive/                          ← Deprecated code
│   ├── control_panels/               ← From Batch 3
│   │   └── deprecated/
│   │       └── README.md
│   ├── dev_explorer/                 ← From Batch 3
│   │   └── deprecated/
│   │       └── README.md
│   ├── old_versions/                 ← 🆕 This cleanup
│   │   ├── ExplorerFinal_broken_1758381738/
│   │   ├── 2025-09-19_20-38-36/
│   │   └── README.md
│   └── legacy_services/              ← 🆕 Superseded services
│       ├── control_panel_plus.py
│       ├── ucnrr_service.py
│       ├── ucnrr_app.py
│       ├── ai_control_panel.py
│       └── README.md
│
└── [other active directories...]
```

---

## 🚀 Cleanup Plan

### Phase 1: Create Archive Structure

```bash
mkdir -p archive/old_versions
mkdir -p archive/legacy_services
mkdir -p docs/historical
mkdir -p docs/sprint_summaries
mkdir -p tests/acceptance
mkdir -p tests/integration
mkdir -p scripts/utilities
```

### Phase 2: Archive Legacy Control Panels

**Files to archive:**
- `control_panel_plus.py` → `archive/legacy_services/`

**Files to keep:**
- `control_panel_plus_plus.py` (active entrypoint)

**Document:**
- Create `archive/legacy_services/README.md` explaining what was archived

### Phase 3: Move Documentation

**Move to `docs/historical/`:**
All .md files EXCEPT:
- `README.md` (stays in root)

**Optional: Further organize into:**
- `docs/sprint_summaries/` — HC sprint summaries
- `docs/historical/architecture/` — Architecture docs
- `docs/historical/sessions/` — Session summaries

### Phase 4: Organize Test Files

**Move to `tests/acceptance/`:**
- `test_hc_acceptance.py`
- `test_hc_v2_acceptance.py`
- `test_hc_v2_sprint*.py`
- `test_photo_coach_acceptance.py`
- `test_hc_conversations.py`
- `test_padna_delta_wiring.py`

**Move to `tests/integration/`:**
- `test_bidirectional_traits.py`
- `test_container_discovery.py`
- `test_debug_task.py`
- `test_check_state.py`
- `test_debug_test5.py`

### Phase 5: Organize Utility Scripts

**Move to `scripts/`:**
- `batch_rescore.py`

**Move to `scripts/utilities/`:**
- `resolved_viewer.py`
- `golden_path_harness.py`
- `prompt_loader.py`

**Archive to `archive/legacy_services/`:**
- `ucnrr_service.py` (superseded by ReDNACoreDemo)
- `ucnrr_app.py`
- `ucn_rr_ai.py`
- `ai_control_panel.py`
- `ai_control_panel_agent.py`
- `TestExplorer.py`
- `core_ai_propagation.py`
- `llama3_client.py` (if not used)

### Phase 6: Archive Old Directories

**Move to `archive/old_versions/`:**
- `ExplorerFinal_broken_1758381738/`
- `2025-09-19_20-38-36/`

**Investigate and potentially archive:**
- `SingleCoach/` (if not actively used)
- `RSC_Sandbox/` (if demo/experimental only)
- `PaDNAOutboundDemo/` (if superseded)
- `PhotoRefinementCoach/` (if demo/experimental only)
- `UCN_RR_Demo/` (if superseded by ReDNACoreDemo)
- `test_imports/` (if temporary)

### Phase 7: Update Imports

**Check and update imports in:**
- `control_panel_plus_plus.py`
- `ExplorerFinal/` modules
- `ExplorerDev/` modules
- `ReDNACoreDemo/` modules

**Search for references to moved files:**
```bash
grep -r "test_hc_acceptance" --include="*.py"
grep -r "batch_rescore" --include="*.py"
grep -r "resolved_viewer" --include="*.py"
```

---

## ✅ Success Criteria

After cleanup:
- ✅ Root contains **ONLY** README.md and config files
- ✅ All .md docs in `docs/` (organized by purpose)
- ✅ All tests in `tests/` (organized by type)
- ✅ All scripts in `scripts/` (organized by purpose)
- ✅ All deprecated code in `archive/` (documented)
- ✅ No broken imports

---

## 🔍 Investigation Needed

### Directories to Investigate

**Purpose unclear — check if active:**
1. `SingleCoach/` — Single coach demo or legacy?
2. `RSC_Sandbox/` — Active RSC development or experimental?
3. `PaDNAOutboundDemo/` — Active demo or superseded?
4. `PhotoRefinementCoach/` — Active or experimental?
5. `UCN_RR_Demo/` — Superseded by ReDNACoreDemo?
6. `test_imports/` — Temporary testing directory?
7. `ComfyUI/` — External dependency or integrated?
8. `snapshots/` — Active snapshot storage or legacy?
9. `cpplusplus/` — CP++ implementation or temporary?

**Action:** Check last modified dates, search for references, consult user

---

## 📋 Implementation Checklist

### Phase 1: Archive Structure ✅
- [ ] `mkdir -p archive/old_versions`
- [ ] `mkdir -p archive/legacy_services`
- [ ] `mkdir -p docs/historical`
- [ ] `mkdir -p tests/acceptance tests/integration`
- [ ] `mkdir -p scripts/utilities`

### Phase 2: Archive Control Panels ✅
- [ ] Move `control_panel_plus.py` → `archive/legacy_services/`
- [ ] Create `archive/legacy_services/README.md`

### Phase 3: Move Documentation ✅
- [ ] Move 23 .md files to `docs/historical/`
- [ ] Keep `README.md` in root
- [ ] Update INDEX.md (if exists) with new locations

### Phase 4: Organize Tests ✅
- [ ] Move acceptance tests to `tests/acceptance/`
- [ ] Move integration tests to `tests/integration/`
- [ ] Update test runner scripts

### Phase 5: Organize Scripts ✅
- [ ] Move utilities to `scripts/` and `scripts/utilities/`
- [ ] Archive superseded services to `archive/legacy_services/`

### Phase 6: Archive Old Directories ✅
- [ ] Move broken/timestamped backups to `archive/old_versions/`
- [ ] Create `archive/old_versions/README.md`

### Phase 7: Validate Imports ✅
- [ ] Search for broken imports
- [ ] Update references
- [ ] Run smoke tests

### Phase 8: Documentation ✅
- [ ] Update README.md with new structure
- [ ] Create "Where to Find What" guide
- [ ] Update Core_Benchmarks_Roadmap

---

**Estimated Impact:**
- **Files moved:** ~50+
- **Directories archived:** ~3-6
- **Documentation reorganized:** 23 .md files
- **Clarity improvement:** 10x easier to navigate

**Risk Level:** Low (all moves, no deletions; can revert if needed)
