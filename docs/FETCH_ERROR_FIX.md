# Fetch Error Fix - Import Error in Reference Population Module

**Date:** 2025-10-20
**Status:** ✅ Fixed
**Symptom:** "Failed to fetch" errors in Northstar UI (RR BY DNA and UNABRIDGED panels)

## Problem

The Northstar UI was showing "Failed to fetch" errors when loading the Head Coach page. The Core API endpoint `/ui/unabridged` was returning 500 Internal Server Error.

### Error Trace

```
ImportError: cannot import name 'get_user_data_dir' from 'ReDNACoreDemo.core.storage'
  File: ReDNACoreDemo/core/reference_pop/reference_pop.py:134
  Function: get_user_ucn()
```

### Root Cause

The `reference_pop.py` module was trying to import a function `get_user_data_dir()` that doesn't exist in `storage.py`.

**Incorrect import:**
```python
from ReDNACoreDemo.core.storage import get_user_data_dir
user_dir = get_user_data_dir(user_id)
```

**Correct function in storage.py:**
```python
def ensure_dirs_for_user(user_id: str) -> Dict[str, Path]:
    """Returns dict with 'udir' key containing user's data directory"""
    udir = USERS_DIR / user_id
    # ... creates dirs if needed ...
    return {"udir": udir, ...}
```

## Fix Applied

**File:** [ReDNACoreDemo/core/reference_pop/reference_pop.py](../ReDNACoreDemo/core/reference_pop/reference_pop.py#L128-L138)

**Changed lines 134-137:**

```python
# BEFORE (broken):
from ReDNACoreDemo.core.storage import get_user_data_dir

user_dir = get_user_data_dir(user_id)
resolved_path = user_dir / "resolved.json"

# AFTER (fixed):
from ReDNACoreDemo.core.storage import ensure_dirs_for_user

user_dirs = ensure_dirs_for_user(user_id)
user_dir = user_dirs["udir"]
resolved_path = user_dir / "resolved.json"
```

## How to Diagnose Similar Issues

### 1. Check Browser Console
Open DevTools → Console tab. Look for failed network requests showing 500 errors.

### 2. Test API Endpoint Directly
```bash
curl -v "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe"
```

If you see "Internal Server Error" instead of JSON, there's a server-side Python error.

### 3. Test Python Function Directly
```bash
python3 -c "
from ReDNACoreDemo.core import ui_readonly
try:
    result = ui_readonly.unabridged_snapshot('ai_ready_probe')
    print(f'✓ Success: {result.get(\"count\", 0)} traits')
except Exception as e:
    print(f'✗ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
"
```

This will show the full Python traceback with line numbers.

### 4. Check Core API Logs
```bash
tail -50 /Users/davidmakarewicz/.redna/devx_supervisor/logs/core.stdout.log
```

Look for "Traceback", "Exception", or "ERROR" messages.

## Common Import Errors in ReDNA

### Pattern 1: Function Doesn't Exist
**Error:** `ImportError: cannot import name 'function_name' from 'module'`

**Fix:** Check what functions are actually exported from the module:
```bash
grep "^def " ReDNACoreDemo/core/storage.py
```

### Pattern 2: Circular Import
**Error:** `ImportError: cannot import name 'X' from partially initialized module 'Y'`

**Fix:** Move the import inside the function (late import):
```python
def my_function():
    from ReDNACoreDemo.core.storage import ensure_dirs_for_user  # Import here
    # ... use it ...
```

### Pattern 3: Module Not Found
**Error:** `ModuleNotFoundError: No module named 'ReDNACoreDemo.core.graph'`

**Fix:** Check if the directory exists and has `__init__.py`:
```bash
ls -la ReDNACoreDemo/core/graph/__init__.py
```

## Testing the Fix

After fixing an import error, test at multiple levels:

### Level 1: Python Import Test
```bash
python3 -c "from ReDNACoreDemo.core.reference_pop.reference_pop import get_user_ucn; print('✓ Import OK')"
```

### Level 2: Function Call Test
```bash
python3 -c "
from ReDNACoreDemo.core import ui_readonly
result = ui_readonly.unabridged_snapshot('ai_ready_probe')
print(f'✓ Function returned {result.get(\"count\")} traits')
"
```

### Level 3: API Endpoint Test
```bash
curl -s "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe" | python3 -m json.tool | head -20
```

Should return JSON like:
```json
{
  "user_id": "ai_ready_probe",
  "traits": [...],
  "count": 4
}
```

### Level 4: UI Test
1. Open http://127.0.0.1:3000/?user=ai_ready_probe
2. Navigate to "Head Coach" tab
3. Check that "RR BY DNA" and "UNABRIDGED" panels load without "Failed to fetch" errors

## Restarting Services After Code Changes

**Important:** Python code changes don't always auto-reload in FastAPI/Uvicorn.

### Option 1: Restart Individual Service (via CP++)
1. Open CP++ at http://127.0.0.1:8502
2. Find "Core API" in service list
3. Click "Restart" button

### Option 2: Nuclear Reset (All Services)
1. Open CP++ at http://127.0.0.1:8502
2. Click red "NUCLEAR RESET & REBUILD ENTIRE STACK" button
3. Wait for all 5 services to show green

### Option 3: Manual Restart (Terminal)
```bash
# Kill Core API
pkill -f "uvicorn.*8004"

# Let CP++ auto-restart it, or start manually:
cd ReDNACoreDemo
python3 -m uvicorn core.api:build_app --factory --host 127.0.0.1 --port 8004 --reload
```

## Prevention

To prevent similar import errors:

1. **Use IDE autocomplete:** Let your IDE verify imports exist before writing them
2. **Test imports early:** After writing an import, test it with `python3 -c "import ..."`
3. **Check storage.py exports:** Before importing from storage.py, check what's available:
   ```bash
   grep "^def " ReDNACoreDemo/core/storage.py | grep -v "^def _"
   ```
4. **Use late imports:** For functions only called occasionally, import inside the function to avoid circular deps

## Related Issues

- **Port Drift:** See [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md)
- **Storage API:** See [ReDNACoreDemo/core/storage.py](../ReDNACoreDemo/core/storage.py) for available functions
- **Reference Population:** See [ReDNACoreDemo/core/reference_pop/](../ReDNACoreDemo/core/reference_pop/) for RR percentile logic

## Quick Reference: Common Storage Functions

```python
from ReDNACoreDemo.core.storage import (
    ensure_dirs_for_user,  # Returns {"udir": Path, ...}
    load_user_info,        # Load user.json
    save_user_info,        # Save user.json
    load_why_cards,        # Load why_cards.jsonl
    append_why_card,       # Append to why_cards.jsonl
)

# Get user's data directory
dirs = ensure_dirs_for_user("ai_ready_probe")
user_dir = dirs["udir"]  # Path to data/users/ai_ready_probe/
```

---

**Status:** Fixed and documented.
**Verification:** ✅ Northstar UI loads without fetch errors.
