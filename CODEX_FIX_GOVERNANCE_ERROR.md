# Codex Task: Fix Governance Module ROLLBACK_FILENAME Error

## Problem Description

All coach panel API endpoints are failing with the same Python error:

```json
{"detail":"module 'ReDNACoreDemo.core.governance' has no attribute 'ROLLBACK_FILENAME'"}
```

### Affected Endpoints

- `/api/coach/career_coach/panel?user_id=TEST` - Returns HTTP 500 with governance error
- `/api/coach/personality_test_coach/panel?user_id=TEST` - Returns HTTP 500 with governance error
- `/api/coach/chatdna_coach/panel?user_id=TEST` - Returns HTTP 500 with governance error
- Likely affects other coach panel endpoints and media endpoints

### User Impact

When users switch to Career Coach, Personality Test Coach, or ChatDNA Coach in the UI, they see error messages like:
- "Career Snapshot Unavailable - HTTP 500: Internal Server Error"
- "Error Loading Personality - API error: 500"
- "ChatDNA Snapshot Unavailable - HTTP 500: Internal Server Error"

The frontend is working correctly - it's making the right API calls and handling errors gracefully. The backend is crashing.

## Root Cause

Something in the API request handling chain is trying to import or access `ROLLBACK_FILENAME` from the governance module, but this attribute doesn't exist.

Possible causes:
1. Missing constant definition in `ReDNACoreDemo/core/governance.py`
2. Import statement trying to access non-existent attribute
3. Code refactoring that removed `ROLLBACK_FILENAME` but left references to it
4. Missing initialization in governance module

## Tasks

### 1. Find the Error Source

**Search for ROLLBACK_FILENAME references:**
```bash
grep -r "ROLLBACK_FILENAME" ReDNACoreDemo/core/ --include="*.py"
```

**Check where governance is imported:**
```bash
grep -r "from.*governance import" ReDNACoreDemo/ --include="*.py"
grep -r "import.*governance" ReDNACoreDemo/ --include="*.py"
```

### 2. Identify the Missing Attribute

**Check the governance module:**
```bash
cat ReDNACoreDemo/core/governance.py | head -50
```

Look for:
- Is `ROLLBACK_FILENAME` supposed to be defined here?
- Are there other similar constants (like `CHECKPOINT_FILENAME`, `STATE_FILENAME`, etc.)?
- Is there a pattern for how filenames are defined?

### 3. Fix the Issue

**Option A: Add the missing constant**

If `ROLLBACK_FILENAME` should exist, add it to the governance module:
```python
# In ReDNACoreDemo/core/governance.py
ROLLBACK_FILENAME = "rollback.json"  # or whatever the appropriate name is
```

**Option B: Remove stale references**

If `ROLLBACK_FILENAME` is no longer needed, remove all references to it:
- Find files importing it
- Remove or update the import statements
- Update code that was using it

**Option C: Fix the import**

If it's defined elsewhere, fix the import path:
```python
# Change from:
from ReDNACoreDemo.core.governance import ROLLBACK_FILENAME

# To (if it's in a different module):
from ReDNACoreDemo.core.some_other_module import ROLLBACK_FILENAME
```

### 4. Test the Fix

**Test each affected endpoint:**
```bash
# Career Coach
curl "http://localhost:8000/api/coach/career_coach/panel?user_id=TEST" | python3 -m json.tool

# Personality Test Coach
curl "http://localhost:8000/api/coach/personality_test_coach/panel?user_id=TEST" | python3 -m json.tool

# ChatDNA Coach
curl "http://localhost:8000/api/coach/chatdna_coach/panel?user_id=TEST" | python3 -m json.tool
```

**Expected successful response structure:**
```json
{
  "snapshot": {
    // Coach-specific data here
  }
}
```

### 5. Verify in UI

1. Start the web frontend (if not already running)
2. Navigate to http://localhost:3001 (or whatever port)
3. Open Coach Catalog
4. Switch to Career Coach → Should see "Career Snapshot" panel load successfully
5. Switch to Personality Test Coach → Should see "Personality Snapshot" panel load
6. Switch to ChatDNA Coach → Should see "ChatDNA Profile" panel load

All panels should show data (or graceful "no data yet" messages) instead of HTTP 500 errors.

## Additional Context

### Recent Changes

- Frontend coach switching was just fixed and is working correctly
- Added persona-panels-config system to dynamically load coach-specific UI panels
- All coach modes now properly switch and render their specialized panels
- The only issue is that backend APIs are returning 500 errors due to this governance bug

### Related Files

- `ReDNACoreDemo/core/governance.py` - Main governance module
- `ReDNACoreDemo/core/governance/` - Governance submodules (if it's a package)
- `ReDNACoreDemo/core/api.py` - Main API router (may have middleware using governance)
- Any coach-specific API files that implement the `/api/coach/{coach_id}/panel` endpoints

### Success Criteria

- [ ] No more `ROLLBACK_FILENAME` attribute errors in API responses
- [ ] Career Coach panel endpoint returns valid JSON (even if empty data)
- [ ] Personality Test Coach panel endpoint returns valid JSON
- [ ] ChatDNA Coach panel endpoint returns valid JSON
- [ ] Photo Coach media list endpoint returns valid JSON
- [ ] UI displays coach-specific panels without error states

## Priority

**HIGH** - This is blocking all coach-specific features in the UI. Users can switch coaches but can't see any of their specialized tools/data.

## Estimated Effort

15-30 minutes - This should be a simple fix once the source of the error is identified.

---

**Note to Codex:** Please investigate thoroughly and provide a detailed explanation of what was wrong and how you fixed it. Include the full traceback if you can find it in the logs.
