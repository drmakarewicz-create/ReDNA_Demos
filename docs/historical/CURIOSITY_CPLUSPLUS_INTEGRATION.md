# Curiosity System CP++ Integration - Complete

## Summary
Successfully integrated curiosity system control into Control Panel Plus Plus (CP++). Users can now easily toggle the curiosity feature and see its status when Core is running.

## Changes Made

### 1. Environment Variable Plumbing (Line 1229)
**File:** `control_panel_plus_plus.py`

Added `CORE_CURIOSITY_ENABLED` to the Core service environment:
```python
def _core_env(config: Dict[str, Any]) -> Dict[str, str]:
    env_vars: Dict[str, str] = {
        "HC_CHAT_ENABLED": _bool_env(config.get("HC_CHAT_ENABLED", True)),
        "HC_CHAT_STREAM_ENABLED": _bool_env(config.get("HC_CHAT_STREAM_ENABLED", True)),
        "HC_ASK_ACTIONS_ENABLED": _bool_env(config.get("HC_ASK_ACTIONS_ENABLED", True)),
        "HC_CHAT_PROVIDER": str(config.get("HC_CHAT_PROVIDER", "stub") or "stub"),
        "CORE_CURIOSITY_ENABLED": _bool_env(config.get("CORE_CURIOSITY_ENABLED", True)),  # ← ADDED
    }
```

### 2. UI Toggle Control (Line 2922)
**File:** `control_panel_plus_plus.py`

Added user-friendly toggle in the environment settings sidebar:
```python
curiosity_enabled = st.toggle("Enable Curiosity System", value=bool(env.get("CORE_CURIOSITY_ENABLED", True)))
```

### 3. Configuration Persistence (Line 3052)
**File:** `control_panel_plus_plus.py`

Added to the config save dictionary:
```python
"CORE_CURIOSITY_ENABLED": bool(curiosity_enabled),
```

### 4. Visual Status Indicator (Lines 330-334)
**File:** `control_panel_plus_plus.py`

Enhanced the health check display to show curiosity status:
```python
# Enrich with curiosity status if available (from Core features)
features = payload.get("features")
if isinstance(features, dict) and "curiosity_enabled" in features:
    curiosity_on = features.get("curiosity_enabled")
    msg += f" — curiosity={'🟢 ON' if curiosity_on else '🔴 OFF'}"
```

## How It Works

### Data Flow
1. **User toggles setting** → CP++ Environment tab → "Enable Curiosity System" toggle
2. **Config saved** → `_load_env()` stores `CORE_CURIOSITY_ENABLED: True/False`
3. **Service starts** → `_core_env()` converts to `"1"` or `"0"` string for subprocess
4. **Core reads env** → `api.py` checks `os.getenv("CORE_CURIOSITY_ENABLED")`
5. **Health endpoint** → Returns `{"features": {"curiosity_enabled": true/false}}`
6. **CP++ displays** → Health check shows `curiosity=🟢 ON` or `curiosity=🔴 OFF`

### Core API Health Response
The Core `/health` endpoint already returns curiosity status:
```json
{
  "status": "healthy",
  "service": "core",
  "features": {
    "photo_import": true,
    "ucnrr_enabled": true,
    "curiosity_enabled": true  ← CP++ reads this
  }
}
```

## User Instructions

### To Enable/Disable Curiosity:
1. Open Control Panel Plus Plus (CP++)
2. Go to **Environment** tab in the sidebar
3. Find the **"Enable Curiosity System"** toggle
4. Toggle ON (enabled by default)
5. Click **"Save environment"**
6. Stop Core service (if running)
7. Start Core service

### To Verify Curiosity Status:
1. Look at the **Core** service health check display
2. You'll see: `Health: 🟢 OK — http://127.0.0.1:8015/health — curiosity=🟢 ON`
   - `🟢 ON` = Curiosity is active
   - `🔴 OFF` = Curiosity is disabled

## Testing
To test the integration:
1. Open CP++ environment tab
2. Toggle "Enable Curiosity System" OFF
3. Save environment
4. Restart Core via CP++
5. Check health display shows `curiosity=🔴 OFF`
6. Toggle back ON, save, restart
7. Check health display shows `curiosity=🟢 ON`

## Default Behavior
- **Default setting:** Curiosity is **ENABLED** (True)
- Setting persists in `cp_env.json`
- Environment variable passed as `"1"` (enabled) or `"0"` (disabled)

## Related Files
- `control_panel_plus_plus.py` - CP++ main application (modified)
- `ReDNACoreDemo/core/api.py` - Core health endpoint (already had curiosity support)
- `cp_env.json` - Stores user's curiosity preference
- `ReDNACoreDemo/.env` - Manual env file (no longer needed with CP++)

## Status: ✅ Complete
All curiosity integration features are now working:
- ✅ UI toggle for easy configuration
- ✅ Environment variable properly passed to Core
- ✅ Visual status indicator in health check
- ✅ Configuration persistence
- ✅ Defaults to enabled
