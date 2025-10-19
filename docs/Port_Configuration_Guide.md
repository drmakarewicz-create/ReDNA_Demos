# ReDNA Port Configuration Guide

**Critical System Documentation**
**Version**: 1.0.0
**Last Updated**: 2025-10-19
**Purpose**: Prevent port mismatches and configuration drift across the ReDNA stack

---

## Table of Contents

1. [Port Assignment Reference](#port-assignment-reference)
2. [Configuration File Hierarchy](#configuration-file-hierarchy)
3. [How Ports Are Resolved](#how-ports-are-resolved)
4. [Common Issues & Fixes](#common-issues--fixes)
5. [Port Verification Checklist](#port-verification-checklist)
6. [Troubleshooting Guide](#troubleshooting-guide)

---

## Port Assignment Reference

### Standard Port Assignments (Canonical)

| Service | Port | Config Key | Health Endpoint | Notes |
|---------|------|------------|-----------------|-------|
| **Core API** | **8004** | `core_port` | `/health` | Primary backend service |
| **UCNRR** | **8017** | `ucnrr_port` | `/health` or `/api/health` | UCN/RR service |
| **React (Next.js)** | **3000** | `react_port` | `/api/health` | Head Coach UI |
| **DevX Backend** | **8100** | `DEVX_BACKEND_PORT` | `/health` | Developer tools API |
| **DevX Frontend** | **3100** | `DEVX_PORT` | `/` | Developer tools UI |
| **CP++ (Streamlit)** | **8501** | `streamlit_port` | `/_stcore/health` | Control Panel |
| **Photo Import Streamlit** | **8510** | `streamlit_photo_port` | `/_stcore/health` | Photo refinement coach |
| **PaDNA Streamlit** | **8511** | `streamlit_padna_port` | `/_stcore/health` | PaDNA explorer |

### Reserved Port Ranges

- **Core Services**: 8004-8019
- **React/Next.js**: 3000-3009
- **DevX Services**: 8100-8109 (Backend), 3100-3109 (Frontend)
- **Streamlit Apps**: 8501, 8510-8599

---

## Configuration File Hierarchy

### Priority Order (Highest to Lowest)

1. **`.cpplusplus_env.json`** (CP++ session config)
   - Location: Project root
   - Used by: Control Panel Plus Plus
   - Keys: `core_port`, `react_port`, `ucnrr_port`, `streamlit_port`
   - **⚠️ WARNING**: This overrides everything else for CP++

2. **`.env`** (Environment variables)
   - Location: Project root
   - Used by: Core, UCNRR, React, DevX
   - Keys: `CORE_PORT`, `REACT_PORT`, `UCNRR_PORT`, etc.
   - **⚠️ NOTE**: Uses UPPERCASE keys

3. **`cpplusplus/envstore.py`** (CP++ defaults)
   - Location: `cpplusplus/envstore.py`
   - Used by: CP++ if no session config exists
   - Keys: `core_port`, `react_port`, etc. (lowercase)
   - Default values: Core=8004, React=3000, UCNRR=8017

4. **`control_panel_plus_plus.py`** (Hardcoded defaults)
   - Location: `control_panel_plus_plus.py` lines 100-105
   - Used by: CP++ as final fallback
   - Constants: `CORE_DEFAULT_PORT`, `REACT_DEFAULT_PORT`, etc.

### File Locations

```
ReDNA_Demos/
├── .env                           # System-wide environment (UPPERCASE keys)
├── .cpplusplus_env.json          # CP++ session config (lowercase keys)
├── .cp_state.json                # CP++ process state (PIDs, ports, timestamps)
├── control_panel_plus_plus.py    # CP++ main app with defaults
└── cpplusplus/
    └── envstore.py               # CP++ default config
```

---

## How Ports Are Resolved

### For Control Panel Plus Plus

```
1. Read .cpplusplus_env.json
   ↓ (if missing key)
2. Read .env file
   ↓ (if missing key)
3. Use DEFAULT_ENV from envstore.py
   ↓ (if missing key)
4. Use CORE_DEFAULT_PORT/REACT_DEFAULT_PORT constants
```

**Example Resolution**:
```python
# In CP++, when determining core_port:
env = load_env_config()  # Reads .cpplusplus_env.json + .env
core_port = int(env.get("core_port", CORE_DEFAULT_PORT))
# Result: .cpplusplus_env.json value OR .env value OR 8004
```

### For Core API

```
1. Read CORE_PORT from .env
   ↓ (if missing)
2. Use hardcoded default (8004)
```

### For React (Next.js)

```
1. Read REACT_PORT from .env
   ↓ (if missing)
2. Use package.json script (PORT=3000)
   ↓ (if missing)
3. Use Next.js default (3000)
```

### For UCNRR

```
1. Read UCNRR_PORT from .env
   ↓ (if missing)
2. Read command-line --port argument
   ↓ (if missing)
3. Use hardcoded default (8017)
```

---

## Common Issues & Fixes

### Issue 1: CP++ Shows Yellow Status (Services Running But Unreachable)

**Symptom**: CP++ shows 🟡 Yellow for Core/React, but services are running and healthy

**Root Cause**: `.cpplusplus_env.json` has stale/incorrect port values

**Diagnosis**:
```bash
# Check what CP++ thinks the ports are
cat .cpplusplus_env.json | grep -E "core_port|react_port"

# Check what ports services are actually on
lsof -i :8004 -i :3000 -i :8017 | grep LISTEN
```

**Fix**:
```bash
# Option 1: Delete CP++ config (forces reload from .env)
rm .cpplusplus_env.json

# Option 2: Manually fix the ports in .cpplusplus_env.json
# Edit and set:
#   "core_port": 8004
#   "react_port": 3000
#   "NEXT_PUBLIC_CORE_API_BASE": "http://127.0.0.1:8004"
```

**Prevention**: After any port change, restart CP++ or delete `.cpplusplus_env.json`

---

### Issue 2: Port Mismatch After Nuclear Button

**Symptom**: After hitting Nuclear button, services start on different ports than expected

**Root Cause**: Stale `.cp_state.json` with old PIDs and ports

**Diagnosis**:
```bash
# Check state file
cat .cp_state.json | python3 -m json.tool

# Look for mismatches between "port" and "actual_port"
```

**Fix**:
```bash
# Delete stale state file
rm .cp_state.json

# Refresh CP++ in browser
# Services will be re-detected on correct ports
```

**Prevention**: The Nuclear button should clean this automatically, but verify after use

---

### Issue 3: Services Start on Wrong Ports

**Symptom**: Core starts on 8015 instead of 8004, React on 3001 instead of 3000

**Root Cause**: Wrong values in `.cpplusplus_env.json`

**Diagnosis**:
```bash
# Check CP++ config
cat .cpplusplus_env.json | jq '.core_port, .react_port, .ucnrr_port'

# Should show:
# 8004
# 3000
# 8017
```

**Fix**:
```bash
# Edit .cpplusplus_env.json and update:
{
  "core_port": 8004,
  "react_port": 3000,
  "ucnrr_port": 8017,
  "NEXT_PUBLIC_CORE_API_BASE": "http://127.0.0.1:8004",
  "UCNRR_BASE_URL": "http://127.0.0.1:8017"
}
```

---

### Issue 4: Port Conflicts (Port Already In Use)

**Symptom**: Service fails to start with "Address already in use"

**Diagnosis**:
```bash
# Find what's using the port
lsof -i :8004

# Check all ReDNA ports
for port in 8004 8017 3000 8100 8501; do
  echo -n "Port $port: "
  lsof -i :$port | grep LISTEN || echo "available"
done
```

**Fix**:
```bash
# Kill the conflicting process
lsof -ti :8004 | xargs kill

# Or use CP++ Nuclear button to clean all services
```

---

### Issue 5: Environment Variable Case Mismatch

**Symptom**: `.env` has `CORE_PORT` but CP++ uses `core_port`

**Root Cause**: Different systems use different case conventions

**Solution**:
- **`.env`**: Use UPPERCASE (`CORE_PORT`, `REACT_PORT`)
- **`.cpplusplus_env.json`**: Use lowercase (`core_port`, `react_port`)
- CP++ automatically converts between them when reading `.env`

**Example**:
```bash
# .env (UPPERCASE)
CORE_PORT=8004
REACT_PORT=3000

# .cpplusplus_env.json (lowercase)
{
  "core_port": 8004,
  "react_port": 3000
}
```

---

## Port Verification Checklist

### After Changing Ports

- [ ] Update `.env` with UPPERCASE keys
- [ ] Update `.cpplusplus_env.json` with lowercase keys (or delete it)
- [ ] Delete `.cp_state.json` to clear stale state
- [ ] Update `NEXT_PUBLIC_CORE_API_BASE` in both files
- [ ] Update `UCNRR_BASE_URL` in both files
- [ ] Restart all services via CP++ Nuclear button
- [ ] Verify all services show 🟢 Green in CP++
- [ ] Test health endpoints manually

### Quick Verification Script

```bash
#!/bin/bash
# Save as scripts/verify_ports.sh

echo "=== Port Configuration Verification ==="

# Check .env
echo ""
echo "1. .env ports:"
grep -E "^(CORE_PORT|REACT_PORT|UCNRR_PORT)" .env

# Check .cpplusplus_env.json
echo ""
echo "2. CP++ config ports:"
cat .cpplusplus_env.json | jq -r '{core_port, react_port, ucnrr_port}'

# Check actual running services
echo ""
echo "3. Actually running services:"
for port in 8004 8017 3000; do
  echo -n "  Port $port: "
  lsof -i :$port | grep LISTEN | awk '{print $1}' || echo "Nothing"
done

# Check health endpoints
echo ""
echo "4. Health checks:"
curl -sf http://127.0.0.1:8004/health > /dev/null && echo "  ✅ Core (8004)" || echo "  ❌ Core (8004)"
curl -sf http://127.0.0.1:8017/health > /dev/null && echo "  ✅ UCNRR (8017)" || echo "  ❌ UCNRR (8017)"
curl -sf http://127.0.0.1:3000/api/health > /dev/null && echo "  ✅ React (3000)" || echo "  ❌ React (3000)"

echo ""
echo "=== Verification Complete ==="
```

---

## Troubleshooting Guide

### Quick Diagnostic Commands

```bash
# 1. Check what CP++ thinks ports are
cat .cpplusplus_env.json | jq '{core_port, react_port, ucnrr_port}'

# 2. Check what .env says
grep -E "PORT=" .env | grep -v "^#"

# 3. Check what's actually running
lsof -i :8004 -i :8017 -i :3000 -i :8100 -i :8501 | grep LISTEN

# 4. Check CP++ state
cat .cp_state.json | python3 -m json.tool

# 5. Test health endpoints
for port in 8004 8017 3000; do
  curl -sf http://127.0.0.1:$port/health -o /dev/null && echo "Port $port: OK" || echo "Port $port: DOWN"
done
```

### Nuclear Reset (When All Else Fails)

```bash
# 1. Stop all services
pkill -f "uvicorn ReDNACoreDemo"
pkill -f "next-server"
pkill -f "ucnrr_app"

# 2. Clear all state
rm -f .cp_state.json

# 3. Reset CP++ config (optional - only if ports are wrong)
rm -f .cpplusplus_env.json

# 4. Verify ports are free
for port in 8004 8017 3000 8100; do
  lsof -ti :$port && echo "WARNING: Port $port still in use!" || echo "Port $port: available"
done

# 5. Restart via CP++ Nuclear button
# Open CP++, click Nuclear, then start services
```

### Debug Mode (Verbose Port Information)

Add to `.env` for verbose logging:
```bash
# Enable debug logging
DEBUG=true
LOG_LEVEL=DEBUG
```

Then check logs:
```bash
# Core logs
tail -f /tmp/core*.log | grep -i port

# React logs
tail -f web/.next/server/*.log | grep -i port

# CP++ logs (in terminal where CP++ is running)
```

---

## Best Practices

1. **Single Source of Truth**: Use `.env` as primary config, let CP++ read from it
2. **Avoid Manual Edits**: Use CP++ UI to change ports when possible
3. **Clean State**: Delete `.cp_state.json` after major changes
4. **Verify After Changes**: Always run health checks after port changes
5. **Document Deviations**: If you must use non-standard ports, document why
6. **Consistent Naming**:
   - `.env` → UPPERCASE (`CORE_PORT`)
   - `.cpplusplus_env.json` → lowercase (`core_port`)
7. **Nuclear Button**: Use it to cleanly restart all services after config changes

---

## Emergency Recovery Procedure

If CP++ is stuck showing yellow/red and you can't fix it:

```bash
# 1. FULL STOP
pkill -f uvicorn
pkill -f next-server
pkill -f streamlit

# 2. CLEAN SLATE
rm .cp_state.json
rm .cpplusplus_env.json

# 3. VERIFY .env HAS CORRECT PORTS
cat .env | grep -E "^(CORE|REACT|UCNRR)_PORT"
# Should show:
# CORE_PORT=8004
# REACT_PORT=3000
# UCNRR_PORT=8017

# 4. RESTART CP++
streamlit run control_panel_plus_plus.py

# 5. USE NUCLEAR BUTTON
# Click Nuclear button in CP++

# 6. START SERVICES
# Use CP++ Start buttons (recommended order: UCNRR → Core → React)

# 7. VERIFY ALL GREEN
# All services should show 🟢 Green
```

---

## Related Documentation

- [DEVX_PORT_SAFETY.md](./DEVX_PORT_SAFETY.md) - DevX-specific port safety
- [Northstar_Stack_Startup_Guide.md](./Northstar_Stack_Startup_Guide.md) - Full stack startup
- [AI_Readiness_Probe.md](./AI_Readiness_Probe.md) - Health check system

---

**Critical Reminder**: After ANY port change, always:
1. Update both `.env` and `.cpplusplus_env.json` (or delete the latter)
2. Delete `.cp_state.json`
3. Restart services via Nuclear button
4. Verify all services show green in CP++

**Version**: 1.0.0
**Maintained By**: ReDNA Core Team
**Last Incident**: 2025-10-19 (CP++ showing yellow due to stale port config)
