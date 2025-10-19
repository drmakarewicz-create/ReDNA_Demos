# ⚠️ DEPRECATED: ExplorerDev (Legacy Developer Explorer)

**Status**: Retired as of October 2025
**Replacement**: [DevX (Developer Experience)](/ReDNACoreDemo/devx/)

---

## Migration Notice

This directory contains the **legacy ExplorerDev** (Streamlit-based developer tools) which has been **retired** in favor of the new **DevX** (React-based developer tools).

### What Changed

| Legacy (ExplorerDev) | New (DevX) |
|---------------------|------------|
| **Port**: 8550 | **Port**: 3100 |
| **Framework**: Streamlit | **Framework**: React + Vite |
| **Backend**: Integrated | **Backend**: Dedicated FastAPI (port 8100) |
| **Status**: ❌ Deprecated | **Status**: ✅ Active |

### Why the Change?

ExplorerDev was a prototype/sandbox tool built with Streamlit. DevX is the production-ready replacement with:
- Modern React UI with better performance
- Dedicated FastAPI backend for better separation of concerns
- Comprehensive developer tools:
  - Trait Workshop
  - Coach Workshop
  - User Ops
  - System Monitor
  - Narrator Timeline
  - Privacy Dashboard
  - And more...

### How to Use DevX Instead

**Option 1: Via Control Panel Plus Plus (CP++)**
```bash
streamlit run control_panel_plus_plus.py
```
- In sidebar → Quick Launch → Click "▶️ Start" to start DevX
- Click "🚀 Open" to open DevX UI

**Option 2: Via Scripts**
```bash
./scripts/start_devx.sh
```
Opens: http://localhost:3100

**Option 3: Manual Start**
```bash
# Backend
cd ReDNACoreDemo
PYTHONPATH=$(pwd):$PYTHONPATH python3 -m uvicorn ReDNACoreDemo.devx.backend.api:app --port 8100

# Frontend
cd ReDNACoreDemo/devx/frontend
npm install
npm run dev -- --port 3100
```

### Documentation

- **DevX README**: [ReDNACoreDemo/devx/README.md](/ReDNACoreDemo/devx/README.md)
- **DevX Docs**: [docs/DEVX_*.md](/docs/)
- **Start Script**: [scripts/start_devx.sh](/scripts/start_devx.sh)

### For Maintainers

This directory is kept for:
1. Historical reference
2. Potential script utilities that haven't been migrated yet
3. Avoiding breaking changes for external dependencies

**Do NOT**:
- Start new development in ExplorerDev
- Reference ExplorerDev in new documentation
- Add ExplorerDev to Control Panel Plus Plus

**DO**:
- Use DevX for all new dev tool features
- Migrate any useful utilities to DevX
- Update references to point to DevX

---

## Migration Complete

As of commit `881a270`, all CP++ references have been updated to use DevX:
- ✅ Sidebar "Open Developer Explorer" → Opens DevX (port 3100)
- ✅ Launch tab "Open DevX" → Opens DevX (port 3100)
- ✅ SERVICE_DEV_EXPLORER constant → Retired
- ✅ AUTO_OPEN_DEVEXPLORER setting → Removed
- ✅ dev_explorer_port setting → Removed

**Questions?** See [ReDNACoreDemo/devx/README.md](/ReDNACoreDemo/devx/README.md)
