# ReDNA Troubleshooting Quick Reference

**Last Updated:** 2025-10-20

## Quick Diagnostic Commands

### Check All Services Status
```bash
# Core API
curl -s http://127.0.0.1:8004/health | python3 -m json.tool

# UCNRR Service
curl -s http://127.0.0.1:8017/health | python3 -m json.tool

# DevX Backend
curl -s http://127.0.0.1:8100/health | python3 -m json.tool

# React UI
curl -s -I http://localhost:3000 | head -5

# CP++
curl -s http://127.0.0.1:8502/_stcore/health
```

### Check What's Running on Ports
```bash
lsof -i :8004 -i :8017 -i :8100 -i :3000 -i :8502 | grep LISTEN
```

### Test Specific Endpoints
```bash
# Unabridged snapshot (for Northstar UI)
curl -s "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe" | python3 -m json.tool

# AI Readiness (DevX)
curl -s "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'✓ {d[\"count\"]} traits')"
```

## Common Issues and Fixes

### Issue 1: "Failed to fetch" in Northstar UI

**Symptoms:**
- Red "Failed to fetch" errors in RR BY DNA or UNABRIDGED panels
- Browser console shows 500 errors

**Diagnosis:**
```bash
# Test the endpoint directly
curl -v "http://127.0.0.1:8004/ui/unabridged?user_id=ai_ready_probe"

# If returns "Internal Server Error", test Python function:
python3 -c "
from ReDNACoreDemo.core import ui_readonly
try:
    ui_readonly.unabridged_snapshot('ai_ready_probe')
    print('✓ OK')
except Exception as e:
    import traceback
    traceback.print_exc()
"
```

**Common Causes:**
1. Import error (see [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md))
2. Missing user data
3. Code changes not reloaded

**Fix:**
1. Check logs: `tail -50 ~/.redna/devx_supervisor/logs/core.stdout.log`
2. Fix any import errors
3. Restart Core API via CP++ Nuclear Reset

### Issue 2: Port Drift Warning in CP++

**Symptoms:**
- Yellow warning banner in CP++: "Port drift detected..."
- Services may be green but port mismatch shown

**Diagnosis:**
```bash
# Check .env configuration
grep -E "PORT" .env | grep -v "^#"

# Check what's actually running
ps aux | grep -E "uvicorn|streamlit|next" | grep -v grep
```

**Fix:**
- See [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md) for complete guide
- Quick fix: Nuclear Reset in CP++

### Issue 3: Service Won't Start

**Symptoms:**
- CP++ shows service as red/failed
- "Address already in use" errors

**Diagnosis:**
```bash
# Find what's using the port (example: 8004)
lsof -i :8004

# Check logs
tail -50 ~/.redna/devx_supervisor/logs/core.stdout.log
```

**Fix:**
```bash
# Kill process using the port
kill -9 <PID>

# Or kill all services and restart
pkill -f uvicorn
pkill -f streamlit
# Then: Nuclear Reset in CP++
```

### Issue 4: DevX Backend Failed

**Symptoms:**
- DevX Backend fails health check
- CP++ shows "DevX backend started but failed health check on 8100"

**Diagnosis:**
```bash
# Check if DEVX ports match
grep DEVX .env

# Should both be 8100:
# DEVX_BACKEND_PORT=8100
# DEVX_PORT=8100
```

**Fix:**
1. Ensure both DEVX port variables are set to 8100 in .env
2. Restart services (Nuclear Reset)
3. See [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md)

### Issue 5: Code Changes Not Taking Effect

**Symptoms:**
- Fixed Python code but still getting same error
- Changed .env but config hasn't updated

**Cause:** Python processes cache code and environment at startup

**Fix:**
```bash
# Option 1: Restart specific service via CP++
# (Use Restart button next to service)

# Option 2: Nuclear Reset (all services)
# (Click red Nuclear Reset button in CP++)

# Option 3: Manual restart
pkill -f "uvicorn.*8004"  # Kill Core API
# CP++ will auto-restart, or start manually
```

### Issue 6: Import Errors

**Symptoms:**
```
ImportError: cannot import name 'X' from 'module'
ModuleNotFoundError: No module named 'X'
```

**Diagnosis:**
```bash
# Check if function exists
grep "^def function_name" path/to/module.py

# Check if module exists
ls -la path/to/module/__init__.py

# Test import directly
python3 -c "from module import function; print('OK')"
```

**Fix:**
1. Find correct function name: `grep "^def " module.py`
2. Update import to use correct name
3. Restart service
4. See [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md) for example

## Service Restart Matrix

| Service | Port | Restart Method | Logs Location |
|---------|------|----------------|---------------|
| Core API | 8004 | CP++ → Restart Core | `~/.redna/devx_supervisor/logs/core.stdout.log` |
| UCNRR | 8017 | CP++ → Restart UCNRR | `~/.redna/devx_supervisor/logs/ucnrr.stdout.log` |
| DevX Backend | 8100 | CP++ → Restart DevX Backend | `~/.redna/devx_backend.log` |
| DevX UI | 8100 | (same as DevX Backend) | `~/.redna/devx_ui.log` |
| React UI | 3000 | CP++ → Restart React | Check CP++ logs |
| CP++ | 8502 | `./scripts/start_cp.sh` | Terminal output |

## Log Files Reference

```bash
# Core API
tail -f ~/.redna/devx_supervisor/logs/core.stdout.log

# UCNRR Service
tail -f ~/.redna/devx_supervisor/logs/ucnrr.stdout.log

# DevX Backend
tail -f ~/.redna/devx_backend.log

# DevX UI
tail -f ~/.redna/devx_ui.log

# Stack rebuild (after Nuclear Reset)
tail -f ~/.redna/stack_rebuild.log

# Nuclear reset events
tail -f ~/.redna/nuclear_reset.log
```

## Environment Variables Quick Check

```bash
# Show all port-related config
grep -E "PORT|BASE" .env | grep -v "^#" | sort

# Expected values:
# CP_PORT=8502
# CORE_PORT=8004
# DEVX_BACKEND_PORT=8100
# DEVX_PORT=8100
# REACT_PORT=3000
# STREAMLIT_PADNA_PORT=8511
# STREAMLIT_PHOTO_PORT=8510
# UCNRR_PORT=8017
```

## Python Testing Templates

### Test Import
```python
python3 -c "
from ReDNACoreDemo.core.storage import ensure_dirs_for_user
print('✓ Import OK')
"
```

### Test Function
```python
python3 -c "
from ReDNACoreDemo.core import ui_readonly
result = ui_readonly.unabridged_snapshot('ai_ready_probe')
print(f'✓ Returned {result.get(\"count\")} traits')
"
```

### Test With Error Details
```python
python3 -c "
import traceback
try:
    from ReDNACoreDemo.core import ui_readonly
    result = ui_readonly.unabridged_snapshot('ai_ready_probe')
    print(f'✓ Success: {result}')
except Exception as e:
    print(f'✗ {type(e).__name__}: {e}')
    traceback.print_exc()
"
```

## CP++ Access

```bash
# Start CP++
./scripts/start_cp.sh

# Or manually
env STREAMLIT_SERVER_PORT=8502 streamlit run control_panel_plus_plus.py --server.port 8502

# Access in browser
open http://127.0.0.1:8502
```

## Nuclear Reset Workflow

When everything is broken:

1. **Open CP++:** http://127.0.0.1:8502
2. **Click:** Red "NUCLEAR RESET & REBUILD ENTIRE STACK" button
3. **Wait:** All 5 services should turn green (30-60 seconds)
4. **Check:** No port drift warnings
5. **Test:** Open Northstar http://127.0.0.1:3000

If Nuclear Reset fails:
```bash
# Check diagnostic log
tail -50 ~/.redna/stack_rebuild.log

# Look for:
# - "Address already in use" → kill processes manually
# - "ImportError" → fix Python code
# - "Port drift" → check .env configuration
```

## Consent Service Health Check

### Quick Test
```bash
# Check Consent JWT service status
curl -s http://127.0.0.1:8004/core/consent/health | jq .

# Expected healthy response:
{
  "status": "healthy",
  "has_secret": true,
  "ttl_minutes": 15,
  "roundtrip_ok": true,
  "warning": null,
  "error_reason": null,
  "config": {
    "algorithm": "HS256",
    "secret_encoding": "hex",
    "leeway_seconds": 30,
    "has_audience": false,
    "has_issuer": false
  }
}
```

### Status Meanings
- **healthy**: Production secret configured, JWT working
- **degraded**: Dev secret in use (functional but insecure)
- **error**: JWT roundtrip failed (check `error_reason`)

### Common error_reason Values

**Secret Issues:**
```
"Secret parsing failed: Failed to decode base64 secret: Invalid base64-encoded string"
```
Fix: Check CONSENT_JWT_SECRET is valid base64, or set CONSENT_JWT_SECRET_B64=false

**Algorithm Issues:**
```
"Asymmetric algorithm RS256 not supported in health check roundtrip"
```
Fix: Use HS256, HS384, or HS512 for symmetric keys

**Verification Errors:**
```
"JWT verify failed: InvalidSignatureError (key or algorithm mismatch)"
```
Fix: Secret or algorithm changed - ensure consistency

```
"JWT verify failed: ExpiredSignatureError (leeway=30s)"
```
Fix: System clock drift - sync time or increase CONSENT_JWT_LEEWAY_SECONDS

### Configuration
```bash
# Check current config
grep CONSENT_JWT .env

# Required for production:
CONSENT_JWT_SECRET=<64-char-hex-string>
CONSENT_JWT_TTL_MINUTES=15
CONSENT_JWT_ALG=HS256
CONSENT_JWT_LEEWAY_SECONDS=30
```

### Secret Rotation (Make Targets)

**Generate new secret:**
```bash
make consent-secret
# Appends new hex secret to .env
# ⚠️  Restart Core API via CP++ Nuclear to apply
```

**Check consent health:**
```bash
make consent-health
# Calls /core/consent/health endpoint
# Returns JSON with status, roundtrip_ok, error_reason, etc.
```

**Manual rotation:**
```bash
# Generate 32-byte (256-bit) hex secret
openssl rand -hex 32 >> .env.tmp
echo "CONSENT_JWT_TTL_MINUTES=15" >> .env.tmp

# Edit .env to replace old CONSENT_JWT_SECRET
# Restart Core API
```

## Related Documentation

- [CONSENT_HEALTH_IMPLEMENTATION.md](CONSENT_HEALTH_IMPLEMENTATION.md) - Consent health endpoint guide
- [FETCH_ERROR_FIX.md](FETCH_ERROR_FIX.md) - Import error fix example
- [PORT_DRIFT_FIX_SUMMARY.md](PORT_DRIFT_FIX_SUMMARY.md) - Port configuration guide
- [PORT_ALLOCATION.md](PORT_ALLOCATION.md) - Complete port strategy
- [Intel/ServicesAndPorts.json](Intel/ServicesAndPorts.json) - Service inventory
- [OPERATIONS.md](OPERATIONS.md) - Operational procedures
