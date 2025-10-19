# 🔴 READ THIS FIRST: Critical Data Flow Architecture

## The Sacred Principle

**EVERY piece of data about a User MUST flow through Head Coach orchestration as if it was given directly to the Head Coach, regardless of the data source.**

This is not a suggestion - it's the foundational architectural principle that ensures:
- ✅ Consistent data validation across all sources
- ✅ Proper RR (Refinement Rating) scoring
- ✅ Holistic profile building
- ✅ System integrity and accuracy

## Quick Reference: The Flow

```
Photo Coach        ─┐
Relationship Coach ─┤
PaDNA Coach        ─┤
Direct Chat        ─┼─→ HEAD COACH ─→ Core ─→ UCN/RR ─→ Core (with RR) ─→ UI
Onboarding         ─┤   ORCHESTRATION   Storage   Scoring    Updated
Future Sources     ─┘
```

## Why This Matters

### ❌ What Happens When You Bypass Head Coach:
- RR scores are `null` (shows 0.0 in UI)
- Curiosity values missing
- Inconsistent data quality
- Profile accuracy degrades
- System appears "broken" to users

### ✅ What Happens When You Follow The Flow:
- All traits get proper RR scores automatically
- Curiosity drives intelligent nudges
- Data quality is validated
- Profile builds holistically
- System works as designed

## For Developers: Quick Start

### Adding a New Data Source? Use This Template:

```python
@app.post("/your_new_source/ingest")
def ingest_your_source(payload: Dict[str, Any]):
    # 1. Extract raw data
    user_id = payload.get("user_id")
    raw_data = payload.get("data")

    # 2. ✅ MANDATORY: Head Coach orchestration
    hc_result = head_coach.shape_your_source_import(
        raw_data=raw_data,
        user_id=user_id
    )

    # 3. Store in Core
    write_user_state(user_id, resolved, evidence, observations)

    # 4. Trigger UCN/RR rescore
    ucnrr_base = _ucnrr_base_url()
    if ucnrr_base:
        response = requests.post(
            f"{ucnrr_base}/api/rescore",
            json={"user_id": user_id, "traits": traits_payload}
        )

        # 5. Update with RR scores
        for trait_id, rr_value in response.json()["rr_by_trait"].items():
            resolved[trait_id]["rr"] = rr_value

        # 6. Save updated state
        write_user_state(user_id, resolved, evidence, observations)

    return {"ok": True, "rescore_triggered": bool(ucnrr_base)}
```

### Verifying Your Implementation:

```bash
# 1. Check your endpoint response includes this
{
  "ok": true,
  "rescore_triggered": true  # ← Must be true!
}

# 2. Verify RR scores were saved
curl "http://127.0.0.1:8015/ui/unabridged?user_id=YOUR_USER"

# 3. Look for non-null RR values
{
  "traits": [
    {
      "trait_id": "SomePath",
      "rr": 85.0,        # ← Must NOT be null
      "curiosity": 0.65  # ← Must be present
    }
  ]
}
```

## For Product/Business: What You Need to Know

### The User Experience Impact:

**When data flows correctly:**
- Users see accurate "Refinement Ratings" for all their traits
- System provides smart, curiosity-driven questions
- Profile quality improves over time
- Trust in the system increases

**When data bypasses Head Coach:**
- Users see "0.0" ratings (looks broken)
- No intelligent nudges or questions
- System appears to not understand them
- User confidence decreases

### Real Example from Today:

**Problem:** User saw "51 traits" but all showed "RR: 0.0"
**Root Cause:** Old data predated RR implementation
**Solution:** Holistic Review button rescores all traits
**Result:** All traits now show proper RR scores and curiosity values

## Quick Troubleshooting

### "Why are my RR scores null/0.0?"

1. **Check UCN/RR is running:**
   ```bash
   curl http://127.0.0.1:8011/api/health
   ```

2. **Check Core can reach UCN/RR:**
   ```bash
   curl http://127.0.0.1:8015/health
   # Look for: "ucnrr_enabled": true
   ```

3. **Fix legacy data with Holistic Review:**
   - Go to Settings in UI
   - Click "Initiate Holistic Review"
   - All traits will be rescored

### "New data source not getting scored?"

Check your endpoint returns:
```json
{
  "rescore_triggered": true
}
```

If false or missing:
1. Verify `_ucnrr_base_url()` is configured
2. Check you're calling UCN/RR `/api/rescore`
3. Ensure you're updating and saving the RR values

## Complete Documentation

See [CRITICAL_DATA_FLOW_ARCHITECTURE.md](docs/CRITICAL_DATA_FLOW_ARCHITECTURE.md) for:
- Complete code paths and line numbers
- Detailed testing procedures
- Environment configuration
- Monitoring and validation
- Future extensibility patterns

## TL;DR

**Three Rules:**
1. **ALL data → Head Coach → Core → UCN/RR → Core (updated) → UI**
2. **Never bypass Head Coach orchestration**
3. **Always verify `rescore_triggered: true` in responses**

Break these rules and the system appears broken to users.
Follow these rules and everything works beautifully.

---

**Created:** 2025-10-06
**Last Validated:** 2025-10-06
**Status:** ✅ Production Critical
