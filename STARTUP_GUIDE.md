# ReDNA Services - Startup Guide

## 🚀 Quick Start (Recommended)

**One command to start everything:**

```bash
./scripts/start_all_services.sh
```

This will:
- ✅ Kill any conflicting processes on ports 8000, 8011, 3001
- ✅ Start Core API (port 8000)
- ✅ Start UCNRR API (port 8011)
- ✅ Start Next.js UI (port 3001)
- ✅ Wait for each service to be healthy before continuing
- ✅ Display service URLs and direct links to coaches

**Expected output:**
```
🚀 Starting ReDNA Services
================================

1. Cleaning up existing processes
   ✓ Cleanup complete

2. Starting Core API (port 8000)
   PID: 12345
   Waiting for Core API to be ready.... ✓
   ✓ Core API started successfully

3. Starting UCNRR API (port 8011)
   PID: 12346
   Waiting for UCNRR API to be ready.... ✓
   ✓ UCNRR API started successfully

4. Starting Next.js (port 3001)
   PID: 12347
   Waiting for Next.js to be ready.... ✓
   ✓ Next.js started successfully

================================
✓ All services started successfully!

📍 Service URLs:
   Core API:  http://127.0.0.1:8000
   UCNRR API: http://127.0.0.1:8011
   Web UI:    http://127.0.0.1:3001

📋 Quick links:
   BeliefDNA Coach (Utilitarian): http://127.0.0.1:3001/?user=persona_utilitarian&persona=beliefdna_coach
   ChatDNA Coach (Obama):         http://127.0.0.1:3001/?user=persona_obama&persona=chatdna_coach
   Head Coach (TEST):             http://127.0.0.1:3001/?user=TEST
```

---

## 🛑 Stop All Services

```bash
./scripts/stop_all_services.sh
```

**Output:**
```
🛑 Stopping all ReDNA services
================================

Stopping core (PID 12345)... ✓
Stopping ucnrr (PID 12346)... ✓
Stopping next (PID 12347)... ✓

✓ All services stopped
```

---

## 📊 Check Service Status

```bash
./scripts/check_services.sh
```

**Output:**
```
📊 ReDNA Services Status
================================

Core API (port 8000)
   Process: ✓ Running (PID 12345)
   Port:    ✓ In use (PID 12345)
   Health:  ✓ Responding

UCNRR API (port 8011)
   Process: ✓ Running (PID 12346)
   Port:    ✓ In use (PID 12346)
   Health:  ✓ Responding

Next.js (port 3001)
   Process: ✓ Running (PID 12347)
   Port:    ✓ In use (PID 12347)
   Health:  ✓ Responding
```

---

## 📝 View Logs

Logs are stored in `.run/` directory:

```bash
# Core API logs
tail -f .run/core.log

# UCNRR API logs
tail -f .run/ucnrr.log

# Next.js logs
tail -f .run/next.log

# All logs at once
tail -f .run/*.log
```

---

## 🔧 Manual Startup (Old Way - Not Recommended)

If you prefer to start services individually:

### 1. Core API
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
PYTHONPATH=".:ReDNACoreDemo:$PYTHONPATH" \
  .venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app \
  --factory --reload --port 8000
```

### 2. UCNRR API
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos/UCN_RR_Demo
../.venv/bin/python -m uvicorn ucnrr_app:app \
  --host 0.0.0.0 --port 8011 --reload
```

### 3. Next.js
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos/web
rm -rf .next  # Fresh build
PORT=3001 npx next dev
```

---

## 🐛 Troubleshooting

### Services won't start - ports already in use

**Solution:** Use the start script, which auto-kills conflicting processes:
```bash
./scripts/start_all_services.sh
```

**Or manually:**
```bash
# Kill specific port
lsof -ti:8000 | xargs kill -9  # Core API
lsof -ti:8011 | xargs kill -9  # UCNRR
lsof -ti:3001 | xargs kill -9  # Next.js
```

### Next.js shows 404 errors for API calls

**Symptoms:** ChatDNA/BeliefDNA panels show "HTTP 404: Not Found"

**Solutions:**
1. Verify Core API is running: `curl http://127.0.0.1:8000/health`
2. Check `.env.local` has correct API base: `NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:8000`
3. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
4. Restart all services: `./scripts/stop_all_services.sh && ./scripts/start_all_services.sh`

### UCNRR keeps going offline

**Solution:** The startup script includes health checks - if UCNRR fails to start, it's logged but won't block the other services. Check logs:
```bash
tail -f .run/ucnrr.log
```

UCNRR is optional - Core and Next.js will work without it (some panels will show warnings).

### Next.js won't compile

**Symptoms:** "Timeout" error when starting Next.js

**Solutions:**
1. Check logs: `tail -f .run/next.log`
2. Look for TypeScript errors or dependency issues
3. Clear Next.js cache: `rm -rf web/.next web/node_modules/.cache`
4. Reinstall dependencies: `cd web && npm install`

### Services start but pages are blank

**Solutions:**
1. Check browser console (F12) for JavaScript errors
2. Verify all services are healthy: `./scripts/check_services.sh`
3. Check network tab for failed API requests
4. Try incognito/private browsing mode (clears cache)

---

## 🌟 Benefits of the New Startup System

### Before (Fragile)
- ❌ Multiple terminal tabs required
- ❌ Services crash if ports already in use
- ❌ No health checks - don't know when services are ready
- ❌ Hard to debug which service failed
- ❌ Manual port cleanup required

### After (Robust)
- ✅ Single command startup
- ✅ Auto-kills conflicting processes
- ✅ Health checks ensure services are ready
- ✅ Clear success/failure messages for each service
- ✅ Centralized logging in `.run/` directory
- ✅ PID tracking for easy management
- ✅ Status command to check what's running

---

## 📂 Files Created

```
scripts/
├── start_all_services.sh   # Start all services with health checks
├── stop_all_services.sh    # Stop all services gracefully
└── check_services.sh       # Check status of all services

.run/                       # Log directory (auto-created)
├── core.log               # Core API logs
├── ucnrr.log              # UCNRR API logs
├── next.log               # Next.js logs
├── core.pid               # Core API process ID
├── ucnrr.pid              # UCNRR API process ID
└── next.pid               # Next.js process ID
```

---

## 🎯 Recommended Workflow

**Starting work:**
```bash
./scripts/start_all_services.sh
```

**During development:**
```bash
# Check if everything is still healthy
./scripts/check_services.sh

# Watch logs for errors
tail -f .run/core.log
```

**Finished working:**
```bash
./scripts/stop_all_services.sh
```

**Service crashed? Just restart:**
```bash
./scripts/start_all_services.sh
# Auto-kills old processes and starts fresh
```

---

## 💡 Next Steps

After starting services, try these:

1. **Test BeliefDNA Coach**:
   - URL: http://127.0.0.1:3001/?user=persona_utilitarian&persona=beliefdna_coach
   - Ask: "Is lying ever morally acceptable?"
   - See transparency features showing which ReDNA traits influenced the response

2. **Test ChatDNA Coach**:
   - URL: http://127.0.0.1:3001/?user=persona_obama&persona=chatdna_coach
   - See language style analysis

3. **Run Evaluation Benchmarks**:
   ```bash
   python3 eval/beliefdna/harness.py --limit 3
   cat eval/beliefdna/results.md
   ```

---

**Made with ❤️ to solve the fragile multi-service startup problem**
