# Where to Find What - ReDNA Demos

**Last Updated:** 2025-10-04 (after Batch 4B cleanup)

This guide helps you navigate the reorganized ReDNA Demos codebase.

---

## 📂 Directory Structure Overview

```
ReDNA_Demos/
├── README.md                          ← Project overview
├── control_panel_plus_plus.py        ← ACTIVE entrypoint (CP++)
│
├── ExplorerFinal/                    ← Production Explorer UI
├── ExplorerDev/                      ← Developer Console
├── ReDNACoreDemo/                    ← Core backend services
│
├── docs/                             ← ALL documentation
│   ├── Core_Benchmarks_Roadmap.md
│   ├── Dev_Explorer_Guide.md
│   ├── Analytics_Guide.md
│   ├── Where_To_Find_What.md         ← You are here
│   ├── historical/                   ← Historical docs (moved from root)
│   └── sprint_summaries/             ← Sprint completion docs
│
├── scripts/                          ← Utility scripts
│   ├── batch_rescore.py
│   ├── golden_path_test.sh
│   ├── run_tests.sh
│   └── utilities/                    ← Helper scripts
│       ├── resolved_viewer.py
│       ├── golden_path_harness.py
│       └── prompt_loader.py
│
├── tests/                            ← ALL test files
│   ├── acceptance/                   ← Acceptance tests
│   │   ├── test_hc_acceptance.py
│   │   ├── test_hc_v2_acceptance.py
│   │   ├── test_photo_coach_acceptance.py
│   │   └── ...
│   └── integration/                  ← Integration tests
│       ├── test_bidirectional_traits.py
│       ├── test_container_discovery.py
│       └── ...
│
├── archive/                          ← Deprecated code
│   ├── legacy_services/              ← Superseded services
│   │   ├── control_panel_plus.py     (replaced by CP++)
│   │   ├── ucnrr_service.py          (now in ReDNACoreDemo)
│   │   ├── ai_control_panel.py       (integrated into CP++)
│   │   └── README.md
│   └── old_versions/                 ← Old backups
│       ├── ExplorerFinal_broken_*/
│       ├── 2025-09-19_*/
│       └── README.md
│
└── [Active Demos & Services...]
    ├── SingleCoach/
    ├── RSC_Sandbox/
    ├── PaDNAOutboundDemo/
    ├── PhotoRefinementCoach/
    └── UCN_RR_Demo/
```

---

## 🔍 Quick Reference: Where to Find...

### Control Panels
- **Active Control Panel:** [`control_panel_plus_plus.py`](../control_panel_plus_plus.py) (root)
- **Legacy v1:** `archive/legacy_services/control_panel_plus.py`

### Developer Tools
- **Dev Explorer:** [`ExplorerDev/explorer_dev.py`](../ExplorerDev/explorer_dev.py)
- **Production Explorer:** [`ExplorerFinal/explorer.py`](../ExplorerFinal/explorer.py)
- **Legacy TestExplorer:** `archive/legacy_services/TestExplorer.py`

### UCN/RR Services
- **Active UCN/RR:** [`ReDNACoreDemo/core/ucn_rr_service.py`](../ReDNACoreDemo/core/ucn_rr_service.py)
- **Legacy standalone:** `archive/legacy_services/ucnrr_service.py`
- **Legacy AI version:** `archive/legacy_services/ucn_rr_ai.py`

### AI/LLM Integration
- **Active chat providers:** [`ReDNACoreDemo/core/chat_providers.py`](../ReDNACoreDemo/core/chat_providers.py)
- **Legacy LLaMA client:** `archive/legacy_services/llama3_client.py`
- **Legacy AI control panel:** `archive/legacy_services/ai_control_panel.py`

### Analytics & Observability
- **Analytics backend:** [`ReDNACoreDemo/core/analytics_collector.py`](../ReDNACoreDemo/core/analytics_collector.py)
- **Analytics UI:** [`ExplorerDev/tabs/analytics.py`](../ExplorerDev/tabs/analytics.py)
- **Observability UI:** [`ExplorerDev/tabs/observability.py`](../ExplorerDev/tabs/observability.py)

### Testing
- **Acceptance tests:** [`tests/acceptance/`](../tests/acceptance/)
  - Head Coach: `test_hc_acceptance.py`, `test_hc_v2_acceptance.py`
  - Photo Coach: `test_photo_coach_acceptance.py`
  - Sprint tests: `test_hc_v2_sprint*.py`
- **Integration tests:** [`tests/integration/`](../tests/integration/)
  - Traits: `test_bidirectional_traits.py`
  - Discovery: `test_container_discovery.py`
- **Test utilities:** [`scripts/golden_path_test.sh`](../scripts/golden_path_test.sh)

### Utilities & Scripts
- **Batch operations:** [`scripts/batch_rescore.py`](../scripts/batch_rescore.py)
- **Data viewers:** [`scripts/utilities/resolved_viewer.py`](../scripts/utilities/resolved_viewer.py)
- **Test harness:** [`scripts/utilities/golden_path_harness.py`](../scripts/utilities/golden_path_harness.py)

### Documentation
- **Project roadmap:** [`docs/Core_Benchmarks_Roadmap.md`](../docs/Core_Benchmarks_Roadmap.md)
- **Dev Explorer guide:** [`docs/Dev_Explorer_Guide.md`](../docs/Dev_Explorer_Guide.md)
- **Analytics guide:** [`docs/Analytics_Guide.md`](../docs/Analytics_Guide.md)
- **Historical docs:** [`docs/historical/`](../docs/historical/) (Sprint summaries, architecture notes)

---

## 🚀 Common Workflows

### Running the Control Panel
```bash
# Main entrypoint
python control_panel_plus_plus.py
```

### Running Dev Explorer
```bash
cd ExplorerDev
streamlit run explorer_dev.py
```

### Running Tests
```bash
# Acceptance tests
.venv/bin/pytest tests/acceptance/test_hc_acceptance.py -v

# Integration tests
.venv/bin/pytest tests/integration/ -v

# All tests
.venv/bin/pytest tests/ -v
```

### Running Utilities
```bash
# Batch rescoring
python scripts/batch_rescore.py

# View resolved ReDNA state
python scripts/utilities/resolved_viewer.py
```

### Analytics & Monitoring
```bash
# Launch Dev Explorer and navigate to Analytics tab
cd ExplorerDev && streamlit run explorer_dev.py
# Then: Select "Analytics" from sidebar
```

---

## 📊 Active Components

### Production-Ready
- ✅ **Control Panel:** `control_panel_plus_plus.py`
- ✅ **Dev Explorer:** `ExplorerDev/explorer_dev.py` (8 sections)
- ✅ **Core Backend:** `ReDNACoreDemo/core/`
- ✅ **Analytics:** `analytics_collector.py` + Analytics UI

### Demos & Sandboxes
- **SingleCoach/**: Single coach demo
- **RSC_Sandbox/**: Relationship/Social/Career sandbox
- **PaDNAOutboundDemo/**: PaDNA outbound demo
- **PhotoRefinementCoach/**: Photo refinement coach
- **UCN_RR_Demo/**: UCN/RR demo

### Archived (Not Active)
- 🗄️ **Legacy control panels:** `archive/legacy_services/control_panel_plus.py`
- 🗄️ **Legacy UCN/RR:** `archive/legacy_services/ucnrr_*.py`
- 🗄️ **Legacy AI integrations:** `archive/legacy_services/ai_*.py`
- 🗄️ **Old backups:** `archive/old_versions/`

---

## 🔧 Troubleshooting

### "File not found" errors
**Problem:** Import or script fails with file not found
**Solution:** Check this guide - file may have been reorganized

**Common moves:**
- Tests: Root → `tests/acceptance/` or `tests/integration/`
- Docs: Root → `docs/historical/`
- Scripts: Root → `scripts/` or `scripts/utilities/`
- Legacy code: Root → `archive/legacy_services/`

### Import errors after cleanup
**Problem:** `ModuleNotFoundError` for moved modules
**Solution:** Update import paths

**Examples:**
```python
# OLD (no longer works)
from batch_rescore import rescore_all

# NEW
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from batch_rescore import rescore_all
```

### Finding old documentation
**Problem:** Can't find sprint summary or session notes
**Solution:** Check [`docs/historical/`](../docs/historical/)

**Examples:**
- `HC_V1_COMPLETE.md` → `docs/historical/HC_V1_COMPLETE.md`
- `SESSION_SUMMARY.md` → `docs/historical/SESSION_SUMMARY.md`

---

## 📋 File Migration Map

### Documentation Files (Root → docs/historical/)
All 23 historical .md files moved from root to `docs/historical/`:
- Architecture: `ARCHITECTURE_REFACTOR.md`
- Sprint summaries: `HC_V*_COMPLETE.md`, `SESSION_SUMMARY*.md`
- Integration notes: `HEAD_COACH_UCN_INTEGRATION_SUMMARY.md`
- UX improvements: `DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md`

### Test Files (Root → tests/)
**Acceptance tests:**
- `test_hc_acceptance.py` → `tests/acceptance/`
- `test_hc_v2_*.py` → `tests/acceptance/`
- `test_photo_coach_acceptance.py` → `tests/acceptance/`

**Integration tests:**
- `test_bidirectional_traits.py` → `tests/integration/`
- `test_container_discovery.py` → `tests/integration/`
- `test_debug_*.py` → `tests/integration/`

### Scripts (Root → scripts/)
**Main scripts:**
- `batch_rescore.py` → `scripts/`

**Utilities:**
- `resolved_viewer.py` → `scripts/utilities/`
- `golden_path_harness.py` → `scripts/utilities/`
- `prompt_loader.py` → `scripts/utilities/`

### Archived Services (Root → archive/legacy_services/)
**Control panels:**
- `control_panel_plus.py` → `archive/legacy_services/`

**UCN/RR services:**
- `ucnrr_service.py` → `archive/legacy_services/`
- `ucnrr_app.py` → `archive/legacy_services/`
- `ucn_rr_ai.py` → `archive/legacy_services/`

**AI/LLM clients:**
- `ai_control_panel.py` → `archive/legacy_services/`
- `ai_control_panel_agent.py` → `archive/legacy_services/`
- `llama3_client.py` → `archive/legacy_services/`

**Core operations:**
- `core_ai_propagation.py` → `archive/legacy_services/`

**Test/Debug:**
- `TestExplorer.py` → `archive/legacy_services/`

**Demo files:**
- `ReDNACoreDemo/core_service_with_ai.py` → `archive/legacy_services/`
- `UCN_RR_Demo/ucnrr_service_with_ai.py` → `archive/legacy_services/`

---

## 📚 Related Documentation

- **Project Roadmap:** [Core_Benchmarks_Roadmap.md](Core_Benchmarks_Roadmap.md)
- **Dev Explorer Guide:** [Dev_Explorer_Guide.md](Dev_Explorer_Guide.md)
- **Analytics Guide:** [Analytics_Guide.md](Analytics_Guide.md)
- **Legacy Cleanup Audit:** [Legacy_Cleanup_Audit.md](Legacy_Cleanup_Audit.md)
- **Legacy Services Archive:** [archive/legacy_services/README.md](../archive/legacy_services/README.md)
- **Old Versions Archive:** [archive/old_versions/README.md](../archive/old_versions/README.md)

---

**Questions?** Consult the roadmap or open an issue with your team.
