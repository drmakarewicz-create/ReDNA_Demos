# Port Drift Fix Summary

**Date:** 2025-10-20
**Status:** ✅ Complete - Ready for Testing

## Problems Fixed

### 1. DevX Backend Port Drift
**Problem:** Bootstrap script and DevX app were using different port variables:
- Bootstrap: `DEVX_BACKEND_PORT=8100`
- DevX App: `DEVX_PORT=8018`
- Result: Server started on 8100 but tried to bind to 8018 → health checks failed

**Fix:** Unified both variables to `8100` in `.env`:
```bash
DEVX_BACKEND_PORT=8100
DEVX_PORT=8100
DEVX_BASE=http://127.0.0.1:8100
```

### 2. CP++ Port Conflict
**Problem:** CP++ was using port 8503 (within Streamlit service range 8503-8515), which could conflict with Photo Coach (8510) and PaDNA Coach (8511).

**Fix:** Assigned CP++ dedicated port `8502` (outside service range):
```bash
CP_PORT=8502  # Added to .env
```

## Files Changed

### Configuration
- `.env` - Added `CP_PORT=8502`, unified `DEVX_*_PORT` to 8100

### Scripts
- `scripts/start_cp.sh` - **NEW** dedicated CP++ launcher that respects `.env`

### Documentation
- `docs/Intel/ServicesAndPorts.json` - Added CP++ as service, updated DevX Frontend port
- `docs/PORT_ALLOCATION.md` - **NEW** comprehensive port allocation guide

## Next Steps

### 1. Start CP++ (Recommended Method)
```bash
./scripts/start_cp.sh
```

This will:
- Kill any old CP++ instances on wrong ports
- Load `CP_PORT=8502` from `.env`
- Start CP++ with explicit port binding
- Open browser automatically

### 2. Nuclear Reset to Test All Services
Once CP++ is running on port 8502:
1. Open CP++ in browser: http://127.0.0.1:8502
2. Hit the "Nuclear Reset" button
3. All 5 services should start successfully:
   - ✅ Core API (8004)
   - ✅ UCN/RR Service (8017)
   - ✅ DevX Backend (8100)
   - ✅ DevX UI (served on 8100)
   - ✅ React UI (3000)

### 3. Verify No Port Drift Warnings
- Check CP++ dashboard for port drift warnings
- Should show all services on correct ports
- No "target → actual" mismatches

## Why This Fix Works

### DevX Port Drift
The port drift happened because:
1. `.env` had two different variables for the same service
2. Bootstrap script read `DEVX_BACKEND_PORT=8100`
3. DevX app config read `DEVX_PORT=8018`
4. Health check probed 8100, but server was on 8018

**Solution:** Use single port (8100) for both variables. DevX Frontend is served by the backend on the same port.

### CP++ Port Conflict
CP++ was dynamically allocated port 8503 from Streamlit's fallback range (8503-8515). This range is intended for other Streamlit services like Photo Coach (8510) and PaDNA Coach (8511).

**Solution:** Give CP++ a dedicated port (8502) **outside** the service range to ensure stability and avoid conflicts.

### Environment Variable Caching
Changes to `.env` don't take effect for running processes because Python caches environment variables at startup.

**Solution:**
- Killed all CP++ instances before restart
- `start_cp.sh` script handles this automatically
- Nuclear Reset will restart all services with fresh environment

## Validation Commands

### Check .env Configuration
```bash
grep -E "^CP_PORT|^DEVX.*PORT" .env
```

Expected:
```
CP_PORT=8502
DEVX_BACKEND_PORT=8100
DEVX_PORT=8100
```

### Check Running Services
```bash
lsof -i :8502 -i :8004 -i :8017 -i :8100 -i :3000 | grep LISTEN
```

Should show:
- CP++ on 8502
- Core on 8004
- UCNRR on 8017
- DevX on 8100
- React on 3000

### Check CP++ Port
```bash
ps aux | grep "streamlit run control_panel_plus_plus.py" | grep -o "STREAMLIT_SERVER_PORT=[0-9]*"
```

Should show: `STREAMLIT_SERVER_PORT=8502`

## Troubleshooting

### If Nuclear Reset Still Fails

1. **Check CP++ is on correct port:**
   ```bash
   lsof -i :8502 | grep LISTEN
   ```
   If not, run `./scripts/start_cp.sh`

2. **Check .env is correct:**
   ```bash
   cat .env | grep -E "PORT"
   ```

3. **Check for port conflicts:**
   ```bash
   lsof -i :8100 -i :8004 -i :8017 | grep LISTEN
   ```
   If anything is running, kill it before Nuclear Reset

4. **Check diagnostic log:**
   ```bash
   cat ~/.redna/stack_rebuild.log | tail -50
   ```

### If Services Start on Wrong Ports

This means environment variables are cached. Fix:
```bash
# Stop all services
pkill -f "uvicorn"
pkill -f "streamlit"
pkill -f "next"

# Restart CP++ to pick up new .env
./scripts/start_cp.sh

# Try Nuclear Reset again
```

## Technical Details

### Port Allocation Strategy

| Port Range | Purpose | Fixed/Dynamic |
|------------|---------|---------------|
| 8502 | CP++ (orchestrator) | Fixed |
| 8503-8515 | Streamlit services | Dynamic |
| 8004, 8017, 8100 | Core APIs | Fixed |
| 3000 | React UI | Fixed |

### Why These Ports?

- **8502 for CP++:** Just below the Streamlit service range, easy to remember
- **8100 for DevX:** Round number, easy to remember, well outside other ranges
- **8510-8511 for Streamlit services:** In the middle of the dynamic range
- **8004, 8017:** Legacy ports, preserved for compatibility

### Environment Variable Precedence

1. Command-line explicit: `--server.port 8502`
2. Environment variable: `STREAMLIT_SERVER_PORT=8502`
3. `.env` file: `CP_PORT=8502`
4. Default fallback: 8510 (old behavior - no longer used)

The `start_cp.sh` script sets both (1) and (2) to ensure consistency.

## References

- [Port Allocation Guide](docs/PORT_ALLOCATION.md) - Comprehensive port strategy
- [Services and Ports (Intel)](docs/Intel/ServicesAndPorts.json) - Service inventory
- [start_cp.sh](scripts/start_cp.sh) - CP++ launcher script
- [Debug API Stub](ReDNACoreDemo/core/graph/debug_api.py) - Temporarily stubbed, auth implementation pending

---

**Status:** All configuration changes complete. Ready to test.
**Next Action:** Run `./scripts/start_cp.sh` and then Nuclear Reset to verify all services start correctly.
