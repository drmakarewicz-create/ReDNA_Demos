# RR > 100 Issue - Root Cause and Fix

**Date:** 2025-10-06
**Status:** IDENTIFIED - FIX AVAILABLE

---

## 🐛 Issue

RR (Resolution Rate) values are showing as > 100 in the UI:
- Example: RR 120, RR 132
- **Expected:** RR should always be 0-100 (it's a percentile)

---

## 🔍 Root Cause

The `resolved.json` files contain incorrect RR values that are actually UCN values:

```json
{
  "BioDNA.Race": {
    "rr": 120.0,  // ❌ This is actually a UCN value (0-1000 scale)
    "curiosity": 0.495
  }
}
```

**How this happened:**
1. During early development, some rescore endpoints were using UCN values as placeholder RR values
2. These were written to `resolved.json` before the proper RR system was implemented
3. The UI correctly reads from `resolved.json`, so it displays these incorrect values

**Evidence:**
- `data/users/TEST/resolved.json` contains: `"rr": 132.0`, `"rr": 120.0`, etc.
- These values match typical UCN scores (0-1000 range)
- Proper RR values should be 0-100 (percentiles)

---

## ✅ Fix

Run **Holistic Review** to recompute all RR values using the proper RR system:

### Option 1: Via UI (Recommended)
1. Open the app at http://localhost:3001
2. Click Settings (⚙️)
3. Toggle **Developer Mode** ON
4. Scroll to "Holistic Review" section
5. Click "Run Holistic Review"
6. Wait for completion
7. Refresh the Unabridged panel

### Option 2: Via API
```bash
# Start the backend if not running
cd ReDNACoreDemo
../.venv/bin/python -m uvicorn core.api:app --reload --port 8000

# In another terminal, trigger holistic review
curl -X POST "http://localhost:8000/holistic-review?user_id=TEST"
```

### Option 3: Via Python Script
```python
import requests

response = requests.post("http://localhost:8000/holistic-review?user_id=TEST")
print(response.json())
```

---

## 🔧 What Holistic Review Does

The holistic review endpoint will:

1. ✅ Load all traits for the user
2. ✅ Call UCN/RR rescore endpoint with proper trait data
3. ✅ Receive correct RR values (0-100 percentiles) from the RR system
4. ✅ Update `resolved.json` with proper RR values
5. ✅ Compute correct curiosity scores (100 - RR)

**After running holistic review:**
- All RR values will be 0-100
- Curiosity scores will be correctly derived
- UI will display accurate percentiles

---

## 🛡️ Prevention

The RR calculation system already has proper clamping:

**File:** `ReDNACoreDemo/core/rr_per_trait.py:196`
```python
percentile = _norm_cdf(z_score) * 100
return max(0.0, min(100.0, percentile))  # ✅ Clamped to 0-100
```

**Root issue was:**
- Old code that put UCN values directly into the `rr` field
- This has been fixed in the current codebase
- Just need to recompute existing data

---

## 📊 Verification

After running the fix, verify RR values are correct:

```bash
# Check a few RR values in resolved.json
cat data/users/TEST/resolved.json | python3 -m json.tool | grep -A 2 '"rr"' | head -20
```

**Expected output:**
```json
"rr": 45.3,     // ✅ 0-100 range
"rr": 67.8,     // ✅ 0-100 range
"rr": 23.1,     // ✅ 0-100 range
```

**NOT:**
```json
"rr": 132.0,    // ❌ UCN value, not RR
"rr": 120.0,    // ❌ UCN value, not RR
```

---

## 🔗 Related Files

- `core/api.py:5172` - Holistic review endpoint
- `core/rr_per_trait.py` - RR calculation with proper clamping
- `core/ui_readonly.py:416-443` - Unabridged snapshot (reads from resolved.json)
- `data/users/TEST/resolved.json` - User data file containing incorrect RR values

---

**Status:** Ready to fix. Just need to run holistic review on affected users.
