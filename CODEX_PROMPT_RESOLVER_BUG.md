# Codex Prompt: Fix Critical Python Import Errors Breaking Chat Ingestion

## Problem Summary

The ReDNA chat ingestion pipeline is **completely broken** due to Python import errors in the resolver module. When users type factual statements like "I am 6 feet tall" or "I have blue eyes" into the chat:

1. ✅ LLM extraction works (detects the trait)
2. ✅ Evidence is stored to `evidence.json`
3. ❌ **Pipeline crashes with `ModuleNotFoundError`**
4. ❌ `resolved.json` is never updated
5. ❌ Traits never appear in the UI

This affects **ALL users** and has been happening since the resolver module was added.

---

## Root Cause

**Multiple files in the resolver module are using ABSOLUTE imports instead of RELATIVE imports.**

When Python imports the resolver as `ReDNACoreDemo.core.resolver`, absolute imports like `from core.resolver.contracts import X` fail because `core.resolver` is not at the top-level module path.

---

## Current Error from Logs

```
File "/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/resolver/impl.py", line 14
    from core.resolver.contracts import Evidence, Resolved, ResolvedTrait
ModuleNotFoundError: No module named 'core.resolver'
```

**Log location**: `/tmp/core_pipeline.log`

**Search for**: `CRITICAL: Failed to process chat evidence`

---

## Files That Need Fixing

All files in `/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/resolver/` directory need to be audited for absolute imports.

### Known problematic imports:

**In `resolver/__init__.py`** (already partially fixed):
```python
# WRONG
from core.resolver.impl import resolve_roundtrip
from core.resolver.contracts import Evidence

# CORRECT
from .impl import resolve_roundtrip
from .contracts import Evidence
```

**In `resolver/impl.py`** (currently broken):
```python
# Line 14 - WRONG
from core.resolver.contracts import Evidence, Resolved, ResolvedTrait

# NEEDS TO BE
from .contracts import Evidence, Resolved, ResolvedTrait
```

**Other files to check**:
- `resolver/contracts.py`
- `resolver/resolved_io.py`
- `resolver/debug.py`
- Any other `.py` files in the resolver directory

---

## Task for Codex

1. **Find all Python files** in `/Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/resolver/`

2. **Search each file** for import statements that reference `core.resolver.*`

3. **Replace ALL occurrences** of:
   - `from core.resolver.X import Y` → `from .X import Y`
   - `import core.resolver.X` → `from . import X`

4. **Verify the pattern**: Within the `resolver` package, all imports of sibling modules should use relative imports (starting with `.`)

---

## Example Fixes Needed

### File: `resolver/impl.py`
```python
# BEFORE (Line 14)
from core.resolver.contracts import Evidence, Resolved, ResolvedTrait

# AFTER
from .contracts import Evidence, Resolved, ResolvedTrait
```

### File: `resolver/__init__.py`
```python
# BEFORE
from core.resolver.impl import resolve_roundtrip, resolve_traits
from core.resolver.contracts import Evidence, ResolvedTrait, Resolved

# AFTER
from .impl import resolve_roundtrip, resolve_traits
from .contracts import Evidence, ResolvedTrait, Resolved
```

### File: `resolver/resolved_io.py` (example if it has issues)
```python
# BEFORE
from core.resolver.contracts import Resolved

# AFTER
from .contracts import Resolved
```

---

## Testing the Fix

After making changes, the server needs a hard restart:

```bash
# Kill server
pkill -9 -f "uvicorn ReDNACoreDemo.core.api"

# Restart
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
nohup python3 -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8015 > /tmp/uvicorn.log 2>&1 &

# Wait 5 seconds
sleep 5

# Test
curl -X POST http://127.0.0.1:8015/ui/chat/send \
  -H "Content-Type: application/json" \
  -d '{"user_id":"CODEX_TEST","persona":"head_coach","text":"I am 6 feet tall","client_ts":1760500000000}'

# Check if it worked
cat /Users/davidmakarewicz/Documents/ReDNA_Demos/data/users/CODEX_TEST/resolved.json
```

**Expected**: Should contain a height trait with `"6 feet tall"`

**Check logs for errors**:
```bash
grep "CRITICAL\|ModuleNotFoundError" /tmp/core_pipeline.log | tail -10
```

**Should be empty** (no critical errors)

---

## Success Criteria

1. ✅ No `ModuleNotFoundError` in logs
2. ✅ Chat messages like "I am 6 feet tall" update `resolved.json`
3. ✅ Traits appear in UI within 5 seconds
4. ✅ Logs show: `chat_resolve{wrote_resolved=true}`

---

## Additional Context

### Why This Matters

This is a **CRITICAL** bug affecting the core functionality of ReDNA. Without trait resolution:
- No user profiles are built
- No AI learning occurs
- The entire system is non-functional from the user perspective

### Pipeline Flow

```
User message
  ↓
Extract (LLM) ✅
  ↓
Store evidence ✅
  ↓
Resolve traits ❌ CRASHES HERE
  ↓
Update resolved.json ❌ NEVER HAPPENS
  ↓
UI displays ❌ NO TRAITS SHOWN
```

### Files Overview

```
ReDNACoreDemo/core/resolver/
├── __init__.py          ← Export public API
├── impl.py              ← Main resolution logic (KNOWN ISSUE)
├── contracts.py         ← Type definitions
├── resolved_io.py       ← File I/O for resolved.json
├── debug.py             ← Debug utilities
└── tests/               ← Test fixtures
```

---

## Verification Checklist

After fix:
- [ ] All `from core.resolver.*` changed to `from .*`
- [ ] Server restarted successfully
- [ ] Test message processed without errors
- [ ] `resolved.json` contains new trait
- [ ] No `CRITICAL` errors in `/tmp/core_pipeline.log`
- [ ] Grep confirms no remaining `from core.resolver` in resolver directory:
  ```bash
  grep -r "from core.resolver" /Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo/core/resolver/
  ```
  Should return: **no results**

---

## Related Commits

- `864040f` - Previous partial fix to `resolver/__init__.py`
- Need new commit for complete fix across all resolver files

---

## Contact

If issues persist after fixing imports, check:
1. `/tmp/core_pipeline.log` - Full stack traces
2. `data/users/ob10/evidence.json` - Evidence should be accumulating
3. `data/users/ob10/resolved.json` - Should update after fix

---

**Priority**: CRITICAL
**Impact**: ALL users
**Estimated Fix Time**: 5-10 minutes (find/replace imports + restart)
