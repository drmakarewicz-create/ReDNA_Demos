# Legacy Services Archive

**Date Archived:** 2025-10-04
**Reason:** Code cleanup - these services have been superseded or consolidated

---

## Archived Services

### Control Panels

**`control_panel_plus.py`**
- **Archived:** 2025-10-04
- **Reason:** Superseded by `control_panel_plus_plus.py` (CP++)
- **Status:** Legacy v1 control panel
- **Active Replacement:** `control_panel_plus_plus.py` (in root)

### UCN/RR Services

**`ucnrr_service.py`**
- **Archived:** 2025-10-04
- **Reason:** Superseded by `ReDNACoreDemo/core/ucn_rr_service.py`
- **Status:** Standalone service, now integrated into Core

**`ucnrr_app.py`**
- **Archived:** 2025-10-04
- **Reason:** Superseded by ReDNACoreDemo API
- **Status:** Legacy app entrypoint

**`ucn_rr_ai.py`**
- **Archived:** 2025-10-04
- **Reason:** AI integration now in ReDNACoreDemo
- **Status:** Legacy AI-powered UCN/RR

### AI/LLM Clients

**`ai_control_panel.py`**
- **Archived:** 2025-10-04
- **Reason:** Superseded by CP++ with integrated AI
- **Status:** Legacy AI-powered control panel

**`ai_control_panel_agent.py`**
- **Archived:** 2025-10-04
- **Reason:** AI agent now integrated into CP++
- **Status:** Legacy AI agent implementation

**`llama3_client.py`**
- **Archived:** 2025-10-04
- **Reason:** LLM client now in `ReDNACoreDemo/core/chat_providers.py`
- **Status:** Legacy LLaMA 3 client

### Core Operations

**`core_ai_propagation.py`**
- **Archived:** 2025-10-04
- **Reason:** AI propagation now in ReDNACoreDemo/core modules
- **Status:** Legacy core AI operations

### Test/Debug Tools

**`TestExplorer.py`**
- **Archived:** 2025-10-04
- **Reason:** Functionality replaced by ExplorerDev
- **Status:** Legacy test explorer

### Demo/Test Files

**`core_service_with_ai.py`**
- **Archived:** 2025-10-04
- **Reason:** Legacy AI demo using archived core_ai_propagation
- **Status:** Standalone demo file (imports archived code)

**`ucnrr_service_with_ai.py`**
- **Archived:** 2025-10-04
- **Reason:** Legacy AI demo using archived ucn_rr_ai
- **Status:** Standalone demo file (imports archived code)

---

## Recovery Instructions

If any archived service is needed:

1. Check if functionality exists in active codebase:
   - Control Panel: `control_panel_plus_plus.py`
   - UCN/RR: `ReDNACoreDemo/core/ucn_rr_service.py`
   - AI/LLM: `ReDNACoreDemo/core/chat_providers.py`
   - Explorer: `ExplorerDev/explorer_dev.py`

2. If not available, copy from this archive and update imports

3. Test thoroughly before integrating

---

## Active Codebase Locations

| Old Location | New Location |
|--------------|--------------|
| `control_panel_plus.py` | `control_panel_plus_plus.py` (root) |
| `ucnrr_service.py` | `ReDNACoreDemo/core/ucn_rr_service.py` |
| `llama3_client.py` | `ReDNACoreDemo/core/chat_providers.py` |
| `TestExplorer.py` | `ExplorerDev/explorer_dev.py` |

---

*For questions, consult Core_Benchmarks_Roadmap.md or Legacy_Cleanup_Audit.md*
