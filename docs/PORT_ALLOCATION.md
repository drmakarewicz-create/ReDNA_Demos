# ReDNA Port Allocation Strategy

**Last Updated:** 2025-10-20
**Phase:** 10 (Post Port Drift Fix)

## Overview

This document describes the port allocation strategy for all ReDNA services to prevent port conflicts and drift.

## Port Map

| Service | Port | Range | Environment Variable | Notes |
|---------|------|-------|---------------------|-------|
| **Control Panel++** | 8502 | Fixed | `CP_PORT` | Orchestrator, must be outside Streamlit service range |
| **Core API** | 8004 | Fixed | `CORE_PORT` | Main FastAPI backend |
| **UCN/RR Service** | 8017 | Fixed | `UCNRR_PORT` | Statistical validation service |
| **DevX Backend** | 8100 | Fixed | `DEVX_PORT`, `DEVX_BACKEND_PORT` | Developer experience API |
| **DevX Frontend** | 8100 | Fixed | (served by backend) | React UI served by DevX Backend |
| **React Web UI** | 3000 | Fixed | `REACT_PORT` | Main user-facing Next.js app |
| **Photo Coach** | 8510 | Fixed | `STREAMLIT_PHOTO_PORT` | Streamlit photo analysis |
| **PaDNA Coach** | 8511 | Fixed | `STREAMLIT_PADNA_PORT` | Streamlit PaDNA export |
| **Streamlit Services** | 8503-8515 | Dynamic | (fallback range) | Available for other Streamlit services |

## Key Design Decisions

### 1. CP++ on Port 8502 (Fixed, Outside Service Range)

**Why:** Control Panel++ (the orchestrator) must have a stable, predictable port that doesn't conflict with the services it manages.

**Implementation:**
- `.env`: `CP_PORT=8502`
- Startup: `STREAMLIT_SERVER_PORT=8502 streamlit run control_panel_plus_plus.py --server.port 8502`
- Port 8502 is **outside** the 8503-8515 range used by other Streamlit services

### 2. DevX Port Consolidation (8100)

**Problem (Pre-Fix):**
- `DEVX_BACKEND_PORT=8100` used by bootstrap script
- `DEVX_PORT=8018` used by DevX backend app
- Bootstrap started server on 8100, but app tried to bind to 8018
- Result: Health checks failed, "port drift" warnings

**Fix:**
- Both `DEVX_BACKEND_PORT` and `DEVX_PORT` set to `8100` in `.env`
- DevX Frontend is served by DevX Backend on the same port (no separate binding)

### 3. Streamlit Service Range (8503-8515)

**Reserved for:**
- Photo Coach (8510)
- PaDNA Coach (8511)
- Future Streamlit services (8503-8509, 8512-8515)

**Important:** CP++ is **not** in this range (it's on 8502) to avoid conflicts.

## Starting CP++ Correctly

**Option 1: Use the dedicated script (recommended)**
```bash
./scripts/start_cp.sh
```

This script:
- Loads `CP_PORT` from `.env` (defaults to 8502)
- Kills any existing CP++ instances
- Starts CP++ with explicit port binding
- Auto-opens browser

**Option 2: Manual start**
```bash
export CP_PORT=8502
env STREAMLIT_SERVER_PORT=$CP_PORT streamlit run control_panel_plus_plus.py --server.port $CP_PORT
```

**Option 3: Via start_all.sh**
```bash
./scripts/start_all.sh
```

## Verifying Port Configuration

**Check .env is correct:**
```bash
grep -E "^CP_PORT|^DEVX.*PORT|^CORE_PORT" .env
```

Expected output:
```
CP_PORT=8502
CORE_PORT=8004
UCNRR_PORT=8017
DEVX_BACKEND_PORT=8100
DEVX_PORT=8100
```

**Check running services:**
```bash
lsof -i :8502 -i :8004 -i :8017 -i :8100 -i :3000 | grep LISTEN
```

**Check for port drift:**
```bash
./scripts/verify_ports.sh  # If this exists
```

Or use CP++'s built-in port scanner (Port Inspector tab).

## Common Issues

### Issue 1: CP++ Running on Wrong Port (8503 instead of 8502)

**Cause:** CP++ was started before `.env` was updated, or environment variables are cached.

**Fix:**
```bash
pkill -f "streamlit run control_panel_plus_plus.py"
./scripts/start_cp.sh
```

### Issue 2: DevX Backend Health Check Fails

**Cause:** Port drift between `DEVX_BACKEND_PORT` and `DEVX_PORT`.

**Fix:**
1. Verify both variables are set to 8100 in `.env`:
   ```bash
   grep DEVX .env
   ```
2. Restart all services (Nuclear Reset in CP++ or `./scripts/start_all.sh`)

### Issue 3: "Port Already in Use"

**Cause:** A service crashed but the port is still held by a zombie process.

**Fix:**
```bash
# Find what's using the port (example: 8502)
lsof -i :8502

# Kill the process
kill -9 <PID>

# Or kill all Streamlit processes
pkill -f streamlit
```

## Environment Variable Caching

**Important:** Python processes (including Streamlit apps) cache environment variables when they start. Changes to `.env` **do not** take effect until the process is restarted.

**When you update .env:**
1. Kill the affected service: `pkill -f "name"`
2. Restart the service
3. For CP++: Use `./scripts/start_cp.sh` which handles this automatically

## Port Allocation Guidelines (Future Services)

When adding new services:

1. **Fixed Ports (Recommended):**
   - Choose a port outside the dynamic ranges
   - Add to `.env` with a descriptive variable name
   - Document in this file and `docs/Intel/ServicesAndPorts.json`

2. **Dynamic Ports (Not Recommended):**
   - If using dynamic allocation, ensure port detection is reliable
   - Log the actual port at startup
   - Update CP++ to track the service's actual port

3. **Streamlit Services:**
   - Use ports in 8503-8515 range (not 8502!)
   - Set `STREAMLIT_<SERVICE>_PORT` in `.env`
   - Ensure CP++ can track it via `STREAMLIT_SERVER_PORT` env var

## References

- [Services and Ports (Intel)](Intel/ServicesAndPorts.json) - Complete service inventory
- [start_cp.sh](../scripts/start_cp.sh) - Dedicated CP++ launcher
- [start_all.sh](../scripts/start_all.sh) - Full stack launcher
- `.env` - Port configuration source of truth
