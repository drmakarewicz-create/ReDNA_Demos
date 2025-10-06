# Safe Manual Steps for UI Improvements

## Issue: Automated process was causing VS Code crashes

The automated restart of services with environment variables was causing VS Code to crash with exit code 15.

## Current State After Crashes

### ✅ Completed:
1. **Created `.env` file** at `ReDNACoreDemo/.env` with:
   ```bash
   CORE_CURIOSITY_ENABLED=true
   ```

2. **Created analysis document**: `HEAD_COACH_UI_IMPROVEMENTS.md`

### ❌ Not Completed:
1. Core API not running with curiosity enabled
2. React UI changes not started
3. Head Coach not wired to AI

---

## Safe Manual Steps to Complete

### Step 1: Start Core API with Curiosity Enabled

**Option A: Using Terminal (Recommended)**

```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos

# Stop any running Core API
pkill -f "uvicorn.*core.api"

# Start with curiosity enabled
export CORE_CURIOSITY_ENABLED=true
.venv/bin/python3 -m uvicorn ReDNACoreDemo.core.api:app --host 0.0.0.0 --port 8001 --reload
```

**Option B: Modify startup script**

Edit your Core API startup script to include:
```bash
export CORE_CURIOSITY_ENABLED=true
```

**Verify it worked:**
```bash
curl http://localhost:8001/health | python3 -m json.tool
```

Look for: `"curiosity_enabled": true`

---

### Step 2: Hide Quick Actions Panel (Optional - Dev Feature)

The "Head Coach quick actions" panel at the top is primarily for development/testing. To hide it:

**File**: `web/src/app/page-client.tsx`

**Find** (around line 1100-1200):
```typescript
<HeadCoachToolbar
  userId={activeUser}
  asks={asks}
  ...
/>
```

**Option A: Comment it out:**
```typescript
{/* Development toolbar - hidden in production
<HeadCoachToolbar
  userId={activeUser}
  asks={asks}
  ...
/>
*/}
```

**Option B: Add conditional rendering:**
```typescript
{process.env.NODE_ENV === 'development' && (
  <HeadCoachToolbar
    userId={activeUser}
    asks={asks}
    ...
  />
)}
```

---

### Step 3: Reorganize Top Navigation (More Complex)

This requires editing the header layout in `web/src/app/page-client.tsx`.

**Current layout** (around line 800-900):
- Workspace label
- User switcher (large)
- Action buttons (Import, Settings, etc.)
- Status badges (Core, UCN/RR, Curiosity)

**Proposed changes:**
1. Make status badges more compact (dot + label)
2. Move status badges next to workspace
3. Group action buttons on the right

**This is optional** - it's a visual improvement but not critical.

---

### Step 4: Wire Head Coach to AI

**This is the complex one.** Need to:

1. Find where Head Coach generates responses (likely in `ExplorerFinal/core/head_coach_runtime.py`)
2. Replace template responses with actual LLM calls
3. Use the Head Coach decision framework we built

**Files to investigate:**
- `ExplorerFinal/core/head_coach_runtime.py`
- `ReDNACoreDemo/core/head_coach.py`
- Web API route that handles chat

**This needs careful investigation** to avoid breaking the existing chat system.

---

## What I Recommend Now

### Immediate (Do This First):
1. **Manually start Core API with curiosity enabled** (Step 1 above)
2. **Verify curiosity is working** in the UI

### Optional (Nice to Have):
3. **Hide the Quick Actions panel** if it's bothering you (Step 2)

### Later (Requires More Work):
4. **Top nav reorganization** - optional visual improvement
5. **Wire to AI** - this is complex and needs investigation

---

## Files Created During Failed Automation

1. **`ReDNACoreDemo/.env`** - Contains `CORE_CURIOSITY_ENABLED=true`
   - ✅ Keep this file
   - It's not being read automatically, need to export the var manually

2. **`HEAD_COACH_UI_IMPROVEMENTS.md`** - Analysis document
   - ✅ Keep for reference

3. **Background processes** - All terminated after crashes
   - ✅ Nothing to clean up

---

## Quick Recovery Commands

If things get stuck, run these:

```bash
# Kill all Python/uvicorn processes
pkill -f uvicorn
pkill -f "python.*api"

# Check what's on port 8001
lsof -ti:8001

# Check what's on port 3001 (web app)
lsof -ti:3001

# Restart Core API manually
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
export CORE_CURIOSITY_ENABLED=true
.venv/bin/python3 -m uvicorn ReDNACoreDemo.core.api:app --host 0.0.0.0 --port 8001 --reload
```

---

## Summary

**The crashes were caused by** my attempts to automatically restart the Core API with environment variables using background processes.

**What's safe to do:**
- ✅ Manually start/stop services in your own terminal
- ✅ Edit React files (but test changes incrementally)
- ✅ Edit Python files (reload happens automatically)

**What caused crashes:**
- ❌ Using `&` background processes in bash commands
- ❌ Trying to export env vars and restart services programmatically

**Next step:** Start the Core API manually with `export CORE_CURIOSITY_ENABLED=true` and verify curiosity works in the UI.
