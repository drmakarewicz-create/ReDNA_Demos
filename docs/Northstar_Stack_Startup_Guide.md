# Northstar Stack Startup Guide

## Overview

This guide provides a reliable procedure for starting the Northstar stack without running into circular dependency issues, fetch errors, or missing LLM configuration.

## The Problem

The Northstar stack consists of multiple interdependent services:
- **Core API** (port 8004): Main backend with PaDNA, promotion logic, HC Chat
- **UCNRR API** (port 8017): UCN/RR scoring service with LLM integration
- **DevX Backend** (port 8100): Developer experience tools, diagnostics
- **Next.js Frontend** (port 3000): React-based UI

Common issues when starting these services manually:
1. **Multiple duplicate processes** running on different ports (e.g., Next.js on 3000 AND 3001)
2. **Missing LLM configuration** in UCNRR (starts without Ollama connection)
3. **Port conflicts** from previous instances
4. **Import errors** when starting services from wrong directory
5. **Stale browser cache** showing "Core unreachable" even when services are healthy

## The Solution

### Automated Startup Script

Use the provided startup script for consistent, reliable launches:

```bash
./scripts/start_northstar_stack.sh
```

This script:
1. ✅ Checks all ports are free before starting
2. ✅ Starts services in correct dependency order
3. ✅ Waits for health checks before proceeding
4. ✅ Verifies LLM configuration in UCNRR
5. ✅ Cleans Next.js build cache to avoid stale state
6. ✅ Provides clear logs and troubleshooting info

### Manual Startup (If Needed)

If you need to start services manually, follow this exact order:

#### Step 1: Clean Shutdown

```bash
# Kill all existing services
pkill -9 -f "uvicorn.*core"
pkill -9 -f "uvicorn.*ucnrr"
pkill -9 -f "uvicorn.*devx"
pkill -9 -f "next dev"
pkill -9 -f "next-server"

# Verify ports are free
lsof -i :8004 -i :8017 -i :8100 -i :3000
# Should return nothing
```

#### Step 2: Start Core API

```bash
source .venv/bin/activate
nohup uvicorn ReDNACoreDemo.core.api:app \
    --host 127.0.0.1 \
    --port 8004 \
    --log-level info \
    > /tmp/core_api.log 2>&1 &

# Wait for health
curl -s http://127.0.0.1:8004/health | jq '.status'
# Should return "healthy"
```

#### Step 3: Start UCNRR API

**IMPORTANT**: Run uvicorn from project root, NOT from UCN_RR_Demo directory, to avoid import errors.

```bash
# Make sure Ollama is running first (if you want LLM configured)
curl -s http://127.0.0.1:11434/api/version

# Start UCNRR from project root
nohup uvicorn UCN_RR_Demo.ucnrr_app:app \
    --host 127.0.0.1 \
    --port 8017 \
    --log-level info \
    > /tmp/ucnrr_api.log 2>&1 &

# Wait for health and verify LLM
curl -s http://127.0.0.1:8017/health | jq '{status, llm_configured, llm_model}'
# Should show llm_configured: true if Ollama is running
```

#### Step 4: Start DevX Backend

```bash
export DEVX_CORE_BASE=http://127.0.0.1:8004
export DEVX_UCNRR_BASE=http://127.0.0.1:8017

nohup uvicorn ReDNACoreDemo.devx.backend.api:app \
    --host 127.0.0.1 \
    --port 8100 \
    --log-level info \
    > /tmp/devx_api.log 2>&1 &

# Wait for health
curl -s http://127.0.0.1:8100/health | jq '.status'
# Should return "healthy"
```

#### Step 5: Start Next.js Frontend

```bash
cd web

# Ensure .env.local exists with correct configuration
cat .env.local
# Should contain:
# NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:8004
# NEXT_PUBLIC_UCNRR_API_BASE=http://127.0.0.1:8017
# NEXT_PUBLIC_DEVX_API_BASE=http://127.0.0.1:8100

# Clean build cache
rm -rf .next

# Start Next.js
nohup npm run dev > /tmp/nextjs.log 2>&1 &

# Wait for ready
sleep 10
tail /tmp/nextjs.log
# Should show "Ready in XXXXms"

# Verify connectivity
curl -s http://127.0.0.1:3000/api/health | jq '{core, react}'
# Should show core: true, react: true
```

## Verification

Run the comprehensive verification:

```bash
/tmp/verify_stack.sh
```

Expected output:
```
=== Service Status Verification ===

1. Core API (8004):
{
  "status": "healthy",
  "rr_mode": "online",
  "llm": "ollama"
}

2. UCNRR API (8017):
{
  "status": "healthy",
  "llm_configured": true,
  "llm_provider": "ollama",
  "llm_model": "llama3.1:8b"
}

3. DevX Backend (8100):
{
  "status": "healthy",
  "service": "devx-backend",
  "version": "1.0.0"
}

4. Next.js (3000):
✓ Serving HTML

5. Next.js -> Core connectivity:
{
  "react": true,
  "core": true,
  "base": "http://127.0.0.1:8004"
}

=== Summary ===
✅ ALL SERVICES HEALTHY
```

## Troubleshooting

### Issue: "Core unreachable" in Browser

**Symptom**: Northstar UI shows "Showing cached data — Core unreachable"

**Root Causes**:
1. Multiple Next.js instances running on different ports
2. Browser accessing wrong port (e.g., 3001 instead of 3000)
3. Stale browser cache

**Fix**:
```bash
# Kill ALL Next.js processes
pkill -9 -f "next dev"
pkill -9 -f "next-server"

# Verify no Next.js running
lsof -i :3000 -i :3001

# Clean and restart
cd web
rm -rf .next
npm run dev

# Access ONLY http://localhost:3000 (not 3001!)
# Hard refresh browser (Cmd+Shift+R on Mac)
```

### Issue: UCNRR Without LLM

**Symptom**: UCNRR starts but `llm_configured: false`

**Root Causes**:
1. Ollama not running
2. Wrong LLM model not available

**Fix**:
```bash
# Check if Ollama is running
curl -s http://127.0.0.1:11434/api/version

# If not, start Ollama
ollama serve &

# Check available models
ollama list

# If llama3.1:8b is missing, pull it
ollama pull llama3.1:8b

# Restart UCNRR
pkill -f "uvicorn.*ucnrr"
uvicorn UCN_RR_Demo.ucnrr_app:app --host 127.0.0.1 --port 8017 &

# Verify LLM configured
curl -s http://127.0.0.1:8017/health | jq '.llm_configured'
```

### Issue: Port Already in Use

**Symptom**: Startup script fails with "Port XXXX is already in use"

**Fix**:
```bash
# Find process on port
lsof -i :XXXX

# Kill specific process
kill -9 <PID>

# Or use the kill script
/tmp/kill_all_services.sh
```

### Issue: Module Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'ReDNACoreDemo'`

**Root Cause**: Running uvicorn from wrong directory

**Fix**:
Always run uvicorn commands from the project root (`/Users/davidmakarewicz/Documents/ReDNA_Demos`), not from subdirectories.

```bash
# ❌ WRONG (from UCN_RR_Demo directory)
cd UCN_RR_Demo
uvicorn ucnrr_app:app --port 8017

# ✅ CORRECT (from project root)
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
uvicorn UCN_RR_Demo.ucnrr_app:app --port 8017
```

## Log Files

All services log to `/tmp/`:
- Core: `/tmp/core_api.log`
- UCNRR: `/tmp/ucnrr_api.log`
- DevX: `/tmp/devx_api.log`
- Next.js: `/tmp/nextjs.log`

View logs in real-time:
```bash
tail -f /tmp/core_api.log
tail -f /tmp/ucnrr_api.log
tail -f /tmp/devx_api.log
tail -f /tmp/nextjs.log
```

## Service Dependencies

```
┌─────────────────────┐
│   Next.js (3000)    │
│   Frontend + API    │
└──────────┬──────────┘
           │
           ├──────────────────┬──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │   Core   │      │  UCNRR   │      │   DevX   │
    │  (8004)  │◄─────┤  (8017)  │◄─────┤  (8100)  │
    └──────────┘      └────┬─────┘      └──────────┘
                           │
                           ▼
                      ┌──────────┐
                      │  Ollama  │
                      │ (11434)  │
                      └──────────┘
```

**Startup Order**: Core → UCNRR → DevX → Next.js

**Why This Order Matters**:
1. UCNRR needs ReDNACoreDemo modules (Core repo)
2. DevX needs to probe Core and UCNRR health
3. Next.js needs all APIs available for API routes

## Quick Reference

### Start Everything
```bash
./scripts/start_northstar_stack.sh
```

### Stop Everything
```bash
/tmp/kill_all_services.sh
```

### Check Status
```bash
/tmp/verify_stack.sh
```

### Access Points
- Northstar UI: http://localhost:3000
- Core API: http://localhost:8004
- UCNRR API: http://localhost:8017
- DevX API: http://localhost:8100
- Control Panel++: http://localhost:8501

## Common CP++ Issues

### Issue: CP++ Can't Start/Stop Services

**Symptom**: Errors in CP++ when launching Core or UCNRR

**Root Causes** (Fixed in this session):
1. `NameError: name 'last_launch_env' is not defined` - Fixed by adding variable initialization
2. `NameError: name '_next_free_port' is not defined` - Fixed by using `ports.find_free_port()`

**Verify Fix**:
```bash
python3 -m py_compile control_panel_plus_plus.py
# Should return no errors
```

### Issue: UCNRR Starts Without LLM in CP++

**Symptom**: UCNRR shows "Checking..." or starts but llm_configured=false

**Fix**:
1. Start Ollama first: `ollama serve`
2. Use CP++ to stop UCNRR
3. Use CP++ to start UCNRR again
4. CP++ will automatically retry with clean LLM env if first attempt fails

## Success Criteria

✅ All four services showing healthy status
✅ UCNRR has `llm_configured: true`
✅ UCNRR shows actual model (e.g., `llama3.1:8b`)
✅ Next.js on port 3000 (not 3001!)
✅ Next.js API route `/api/health` returns `core: true`
✅ Browser shows Northstar UI without "Core unreachable" errors
✅ No duplicate processes running

## Notes

- **Always** use the startup script for consistent results
- **Always** access Northstar at `http://localhost:3000` (not 3001)
- **Always** start Ollama before UCNRR if you want LLM configured
- **Always** run uvicorn commands from project root
- **Never** have multiple Next.js instances running
- **Clean** Next.js build cache (`.next`) when troubleshooting

## See Also

- [Phase 7 Progress Documentation](./Phase7_Progress.md)
- [AI Readiness Probe](./AI_Readiness_Probe.md)
- [UCNRR System Verification](../scripts/verify_ucnrr_system.sh)
