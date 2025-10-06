# Photo Import Troubleshooting Guide

## Overview

The Photo Import feature allows flexible ingestion of PaDNA traits from JSON files or plain text descriptions. This guide helps resolve common issues.

## Issue: "Photo Import Feature Unavailable" Warning

### Symptoms
- Yellow warning banner appears in the Photo Import section
- Import buttons are disabled
- Message says "The Core API photo import endpoint is not available"

### Root Cause
The `/ui/photo/import` endpoint was not available when you tried to use it. This happens when:

1. **Server started before code was added** - The Core API was running when the photo import endpoint code was added
2. **PhotoRefinementCoach import failed** - The Python module couldn't be imported
3. **Wrong Python environment** - Server started with system Python instead of venv

### Solution

#### Option 1: Restart Core API (Recommended)

```bash
# Stop the current Core API process (find PID first)
ps aux | grep uvicorn | grep 8015

# Kill the process
kill <PID>

# Start with correct Python environment
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
.venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015 --reload
```

#### Option 2: Use Control Panel++

If you're using the Control Panel++ (Streamlit on port 8501):
1. Go to the Control Panel++ interface
2. Restart the Core API from there

### Verification

After restarting, verify the feature is available:

```bash
# Check health endpoint
curl -s http://127.0.0.1:8015/health | python3 -m json.tool
```

Look for:
```json
{
  "features": {
    "photo_import": true
  }
}
```

If `photo_import` is `false`:
1. Check server logs for import errors
2. Verify PhotoRefinementCoach module exists at: `../PhotoRefinementCoach/src/importer.py`
3. Check Python path in server startup logs

## Issue: 404 Not Found Error

### Symptoms
- Import fails with "Request failed (404): Not Found"
- No warning banner appears (happens if UI cached old health check)

### Solution
1. Restart the Core API as described above
2. Hard refresh the web app (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
3. Check that Core API is running on correct port (8015)

## Issue: Import Succeeds but No Traits Show

### Symptoms
- Import reports success
- "Imported 0 traits"
- Quarantined items list shows your data

### Common Causes

1. **Unrecognized paths** - Your JSON uses paths that don't map to PaDNA traits
   ```json
   // ❌ Won't work
   {"person.hair": "brown"}

   // ✅ Works
   {"Hair.Color": "brown"}
   // or
   {"PaDNA.HairDNA.Color": "brown"}
   ```

2. **Missing LLM assist** - Plain text needs LLM to be configured
   - Check if `ENABLE_SOFT_IMPORT_ASSIST=true` in environment
   - Verify `llama_chat` client is available

3. **Wrong data structure** - Data not in expected format
   ```json
   // ❌ Won't work (missing observations wrapper)
   {"user_id": "test"}

   // ✅ Works
   {
     "user_id": "test",
     "observations": {
       "Hair.Color": "brown"
     }
   }
   ```

### Solution
Check the `quarantined` array in the response for reasons why items were rejected.

## Monitoring & Prevention

### 1. Health Check Integration

The system now automatically checks feature availability:
- Health check runs when Photo Import Panel loads
- Shows warning if feature is unavailable
- Disables import buttons until available

### 2. Feature Flags

The Core API `/health` endpoint now reports:
```json
{
  "features": {
    "photo_import": true,
    "ucnrr_enabled": false,
    "curiosity_enabled": false
  }
}
```

Monitor these flags to detect issues early.

### 3. Server Startup

Always use the virtual environment:
```bash
# ✅ Correct
.venv/bin/python -m uvicorn ...

# ❌ Wrong
python3 -m uvicorn ...
```

### 4. Development Mode

Run with `--reload` flag to automatically pick up code changes:
```bash
.venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015 --reload
```

## Test Files

Example files are in `test_imports/`:

1. **structured_example.json** - Full PaDNA format with observations, UCN, reasons
2. **unstructured_example.json** - Simple key-value pairs
3. **plain_text_example.txt** - Natural language description

Test import with:
```bash
curl -X POST http://127.0.0.1:8015/ui/photo/import \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "TEST",
    "data": {
      "Hair.Color": "Brown",
      "Eye.Color": "Blue"
    }
  }'
```

## Additional Resources

- **Path Mappings**: See `PhotoRefinementCoach/src/importer.py` lines 78-124 for supported path aliases
- **Traits Registry**: `ReDNACoreDemo/data/config/traits_registry.yaml` defines valid PaDNA paths
- **Core API Logs**: Check terminal where Core API is running for detailed error messages

## Quick Checklist

When photo import isn't working:

- [ ] Core API is running on port 8015
- [ ] Health endpoint shows `photo_import: true`
- [ ] Using correct Python environment (.venv)
- [ ] PhotoRefinementCoach module is present
- [ ] Web app can reach http://127.0.0.1:8015
- [ ] Browser cache is cleared (if needed)
- [ ] User is selected in web interface

## Getting Help

If issues persist:
1. Check Core API server logs for Python errors
2. Verify the import endpoint exists: `curl -X POST http://127.0.0.1:8015/ui/photo/import`
3. Test with the provided example files first
4. Check browser console for JavaScript errors
