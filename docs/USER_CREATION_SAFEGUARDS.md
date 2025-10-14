# User Creation Safeguards

**Purpose**: Prevent duplicate or confusingly-similar users that can cause data mixing, incorrect holistic reviews, and user confusion.

## The Problem

Previously, users could be created with identical or similar labels/IDs:
- `"AB Test"` (with space, capitals) - Empty user
- `"abtest"` (lowercase, no space) - User with 51 traits

Both displayed as "AB Test" in the UI, causing:
- User viewed data from `abtest` but ran holistic review on empty `"AB Test"`
- Result: "No changes detected" when 51 traits should have been rescored
- Confusion about which user holds the actual data

## Three-Layer Protection System

### Layer 1: Backend Validation (storage.py)

**Location**: `ReDNACoreDemo/core/storage.py` lines 1067-1095

**Checks performed during user creation:**

1. **Exact duplicate labels** (case-insensitive)
   - Prevents: `"AB Test"` when `"ab test"` exists
   - Error: `duplicate_label`

2. **Similar ID patterns** (fuzzy matching)
   - Normalizes by removing spaces, hyphens, underscores
   - Prevents confusing variations like:
     - `"AB Test"` vs `"abtest"`
     - `"user-1"` vs `"user_1"` vs `"user 1"`
     - `"john-doe"` vs `"johndoe"`
   - Error: `similar_id`

**Algorithm**:
```python
normalized = id.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
# "AB Test" → "abtest"
# "user-1" → "user1"
# "john_doe" → "johndoe"
```

### Layer 2: API Error Handling (api.py)

**Location**: `ReDNACoreDemo/core/api.py` lines 4953-4970

**Endpoint**: `POST /ui/user/create`

**Returns structured errors:**
```json
{
  "error": "DUPLICATE_LABEL",
  "message": "A user with label 'AB Test' already exists (ID: abtest)",
  "conflicting_user_id": "abtest"
}
```

Or:
```json
{
  "error": "SIMILAR_ID",
  "message": "User ID 'AB Test' is too similar to existing user 'abtest'",
  "conflicting_user_id": "abtest"
}
```

### Layer 3: UI Disambiguation (user-switcher.tsx)

**Location**: `web/src/components/user-switcher.tsx` lines 298-299

**Visual display**: Shows both label AND ID for each user
```
AB Test (abtest)
John Doe (john-doe)
```

**Frontend error handling**: `web/src/components/onboard-user-modal.tsx` line 653
- Displays backend error messages to user
- Prevents form submission until conflict resolved

## Error Messages You Might See

### "A user with label 'X' already exists"
**Cause**: Attempting to create user with duplicate label (case-insensitive match)

**Example**:
- Existing user: `john-doe` with label `"John Doe"`
- Attempted: New user with label `"john doe"`
- **Blocked**: Labels match when compared case-insensitively

**Solution**: Choose a different label or use the existing user

### "User ID 'X' is too similar to existing user 'Y'"
**Cause**: ID normalization detected confusing variation

**Examples**:
- Existing: `abtest`
- Attempted: `AB Test` → Normalized to `abtest` → **Blocked**

- Existing: `user-1`
- Attempted: `user_1` → Normalized to `user1` → **Blocked**

**Solution**: Choose a meaningfully different ID (not just different formatting)

## Best Practices

### ✅ Good User Naming

**Use distinct, meaningful IDs:**
- `alpha-tester`, `beta-tester`, `gamma-tester`
- `john-smith`, `jane-doe`, `bob-wilson`
- `scenario-1`, `scenario-2`, `scenario-3`

**Use clear labels:**
- Label: `"Alpha Tester (Jan 2025)"`, ID: `alpha-jan-2025`
- Label: `"John Smith - Marketing"`, ID: `john-smith-mkt`
- Label: `"Test User #1"`, ID: `test-user-01`

### ❌ Avoid These Patterns

**Don't use formatting variations of same name:**
- ❌ `"AB Test"`, `"ab-test"`, `"abtest"` (all normalize to `abtest`)
- ❌ `"user_1"`, `"user-1"`, `"user 1"` (all normalize to `user1`)

**Don't reuse labels:**
- ❌ Two users both labeled `"Test User"` (even with different IDs)

**Don't use ambiguous labels:**
- ❌ `"User"`, `"Test"`, `"Default"` (too generic)

## Resolving Existing Duplicates

If you already have duplicate users in your system:

### Step 1: Identify the duplicates
Use user switcher dropdown - look for identical labels with different IDs:
```
AB Test (AB Test)
AB Test (abtest)
```

### Step 2: Determine which user has the data
1. Switch to first user, check trait count in PaDNA/HC
2. Switch to second user, check trait count
3. The one with traits is your "real" user

### Step 3: Delete the empty user
Use Settings → User Management → Delete User (for the empty one)

### Step 4: Rename if needed
Update the label of the remaining user to be more descriptive:
- Old: `"AB Test"` (abtest)
- New: `"AB Test - Photo Analysis Jan 2025"` (abtest)

## Technical Reference

### Files Modified for Safeguards

| File | Lines | Purpose |
|------|-------|---------|
| `ReDNACoreDemo/core/storage.py` | 1067-1095 | Duplicate detection in `create_user()` |
| `ReDNACoreDemo/core/api.py` | 4953-4970 | Error handling in `/ui/user/create` |
| `web/src/components/user-switcher.tsx` | 298-299 | Display label + ID for disambiguation |
| `web/src/components/onboard-user-modal.tsx` | 653 | Frontend error display |

### Testing the Safeguards

**Test Case 1: Exact duplicate label**
```bash
# Create first user
POST /ui/user/create
{ "user_id": "test1", "label": "Test User" }
# ✅ Success

# Attempt duplicate label
POST /ui/user/create
{ "user_id": "test2", "label": "test user" }
# ❌ Error: DUPLICATE_LABEL
```

**Test Case 2: Similar ID**
```bash
# Create first user
POST /ui/user/create
{ "user_id": "ab-test", "label": "Alpha Beta Test" }
# ✅ Success

# Attempt similar ID
POST /ui/user/create
{ "user_id": "AB Test", "label": "Different Label" }
# ❌ Error: SIMILAR_ID (both normalize to "abtest")
```

**Test Case 3: Legitimately different users**
```bash
# Create first user
POST /ui/user/create
{ "user_id": "alpha-tester", "label": "Alpha Tester" }
# ✅ Success

# Create different user
POST /ui/user/create
{ "user_id": "beta-tester", "label": "Beta Tester" }
# ✅ Success (sufficiently different)
```

## Integration with Holistic Review

The duplicate prevention system directly prevents the holistic review bug:

**Bug scenario (now prevented):**
1. ❌ Create `"abtest"` with 51 traits
2. ❌ Create `"AB Test"` (empty, but same label)
3. ❌ UI shows both as "AB Test"
4. ❌ User views data from `abtest` but runs holistic on `"AB Test"`
5. ❌ Result: "No changes detected" (correct for empty user, wrong from user perspective)

**With safeguards:**
1. ✅ Create `"abtest"` with 51 traits
2. ❌ **BLOCKED**: Cannot create `"AB Test"` (similar_id error)
3. ✅ User must choose different ID: `"ab-test-2"` or `"beta-test"`
4. ✅ No confusion, holistic review works correctly

## Related Documentation

- **[HOLISTIC_REVIEW_BUG_FIX.md](./HOLISTIC_REVIEW_BUG_FIX.md)**: Original bug that prompted this safeguard
- **[CRITICAL_DATA_FLOW_ARCHITECTURE.md](./CRITICAL_DATA_FLOW_ARCHITECTURE.md)**: Complete data flow for all user data
- **[README_DATA_FLOW.md](./README_DATA_FLOW.md)**: Quick reference for sacred principle

## Future Enhancements

Potential improvements to consider:

1. **Levenshtein distance**: Detect typos (e.g., `"jhon-doe"` vs `"john-doe"`)
2. **Alias system**: Allow multiple labels for same user
3. **Archive instead of delete**: Soft-delete users to prevent accidental data loss
4. **Import/export**: Merge duplicate users automatically
5. **Admin dashboard**: View all users, detect potential duplicates after the fact

---

**Last Updated**: 2025-10-06
**Related Issue**: Duplicate "AB Test" users causing holistic review confusion
**Status**: ✅ Implemented and tested
