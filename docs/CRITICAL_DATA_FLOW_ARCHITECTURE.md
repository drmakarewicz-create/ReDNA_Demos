# CRITICAL: ReDNA Data Flow Architecture

## 🔴 SACRED PRINCIPLE

**ALL data from ANY source MUST flow through Head Coach orchestration as if it was given directly to the Head Coach.**

This is the foundational architecture principle that ensures:
- Consistent data validation
- Proper RR/UCN scoring
- Holistic profile building
- System integrity

## Universal Data Flow Path

```
ANY DATA SOURCE → Head Coach Orchestration → Core Storage → UCN/RR Scoring → Core Update → UI Display
```

### Step-by-Step Flow

1. **Data Ingestion** (Any Source)
   - Photo Coach extracts physical traits
   - Relationship Coach gathers interaction data
   - PaDNA Coach processes appearance info
   - Direct user chat messages
   - Onboarding responses
   - Future data sources (wearables, social media, etc.)

2. **Head Coach Orchestration** (`head_coach.shape_photo_import()` or equivalent)
   - Validates data structure
   - Performs AI inference
   - Shapes raw data into structured observations
   - Routes to appropriate storage

3. **Core Storage** (`/ui/photo/import`, `/hc/ingest`, etc.)
   - Stores traits in `resolved.json`
   - Updates evidence and observations
   - Maintains provenance tracking

4. **UCN/RR Scoring** (`POST /api/rescore`)
   - Calculates RR (Refinement Rating) scores
   - Computes curiosity values
   - Returns scored data to Core

5. **Core Update**
   - Updates `resolved.json` with RR scores
   - Stores curiosity values
   - Persists to disk

6. **UI Display**
   - Reads from `/ui/unabridged`
   - Displays traits with RR scores
   - Shows curiosity-driven nudges

## Critical Code Paths

### Photo Coach Flow

**File:** `ReDNACoreDemo/core/api.py`

```python
@app.post("/ui/photo/import")
def import_photo_json(payload: Dict[str, Any] = Body(...)) -> Any:
    # Lines 4245-4249: HEAD COACH shapes the data
    head_coach_result = head_coach.shape_photo_import(
        imported_traits=imported_for_inference,
        user_id=user_id_raw,
        image_quality=0.9
    )

    # Lines 4202-4223: UCN/RR rescores and updates
    response = requests.post(
        f"{ucnrr_base}/api/rescore",
        json={"user_id": user_id_raw, "traits": traits_payload},
        timeout=10,
    )
    if response.ok:
        ucnrr_result = response.json()
        rr_by_trait = ucnrr_result.get("rr_by_trait", {})
        curiosity_by_trait = ucnrr_result.get("curiosity_by_trait", {})

        # Update resolved.json with RR values
        for trait_id, rr_value in rr_by_trait.items():
            if trait_id in resolved:
                resolved[trait_id]["rr"] = rr_value

        # Save updated state
        write_user_state(user_id_raw, resolved, evidence, observations)
```

### Holistic Review (Rescore All Traits)

**File:** `ReDNACoreDemo/core/api.py`

```python
@app.post("/ui/holistic/review")
def holistic_review(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    # Lines 2298-2324: Load all traits and build payload
    resolved, evidence, obs = read_user_state(user_id)
    traits = []
    for trait_path, trait_data in resolved.items():
        traits.append({
            "id": trait_path,
            "value": trait_data.get("resolved_value"),
            "rr": trait_data.get("rr", trait_data.get("ucn", 500.0)),
        })

    # Lines 2338-2379: Call UCN/RR rescore and update
    response = requests.post(
        f"{ucnrr_base}/api/rescore",
        json={"user_id": user_id, "traits": traits},
        timeout=30,
    )

    if response.ok:
        rescore_result = response.json()
        rr_by_trait = rescore_result.get("rr_by_trait", {})
        curiosity_by_trait = rescore_result.get("curiosity_by_trait", {})

        # Update all traits with new RR scores
        for trait_path in resolved:
            if trait_path in rr_by_trait:
                resolved[trait_path]["rr"] = rr_by_trait[trait_path]
            if trait_path in curiosity_by_trait:
                resolved[trait_path]["curiosity"] = curiosity_by_trait[trait_path]

        # Persist updates
        write_user_state(user_id, resolved, evidence, obs)
```

### UCN/RR Forward Flow (Push Mode)

**File:** `UCN_RR_Demo/ucnrr_app.py`

```python
# Lines 556-569: UCN/RR pushes scored data to Core
def _post_core_ingest(user_id: str, observations: Dict[str, Any], trace_id: Optional[str] = None):
    resp = requests.post(
        f"{CORE_BASE}/ingest_from_ucnrr",
        json={"user_id": user_id, "observations": observations},
        timeout=30,
    )
    return {"ok": resp.ok, "status_code": resp.status_code}

# Lines 812-817: After pushing to Core, trigger recompute
recompute_resp = requests.post(
    f"{CORE_BASE}/recompute/{user_id}",
    json={},
    timeout=15,
)
```

## Environment Configuration

### Required Environment Variables

**Core Service:**
```bash
# UCN/RR connection (checked in order)
UCNRR_BASE_URL=http://127.0.0.1:8011
# OR
UCNRR_BASE=http://127.0.0.1:8011
# OR
UCNRR_URL=http://127.0.0.1:8011
```

**UCN/RR Service:**
```bash
# Core connection
CORE_BASE=http://127.0.0.1:8015
# OR
CORE_URL=http://127.0.0.1:8015
```

### Verify Configuration

```bash
# Check Core health and UCN/RR status
curl http://127.0.0.1:8015/health

# Expected response:
{
  "status": "healthy",
  "service": "core",
  "features": {
    "ucnrr_enabled": true,  # ← Must be true
    "curiosity_enabled": true
  }
}

# Check UCN/RR health
curl http://127.0.0.1:8011/api/health

# Expected response:
{
  "status": "healthy",
  "service": "ucnrr"
}
```

## Testing the Flow

### 1. Test Photo Import with RR Scoring

```bash
# Import a trait via Photo Coach
curl -X POST http://127.0.0.1:8015/ui/photo/import \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "data": {"PaDNA.EyeDNA.Color": "Blue"},
    "source": "test"
  }'

# Expected response includes:
{
  "ok": true,
  "imported": 1,
  "rescore_triggered": true,  # ← RR scoring happened
  "traits": [...]
}

# Verify RR score was saved
curl "http://127.0.0.1:8015/ui/unabridged?user_id=test_user"

# Should see:
{
  "traits": [
    {
      "trait_id": "PaDNA.EyeDNA.Color",
      "value": "Blue",
      "ucn": 80.0,
      "rr": 80.0,           # ← RR score present
      "curiosity": 0.782    # ← Curiosity calculated
    }
  ]
}
```

### 2. Test Holistic Review (Rescore Legacy Data)

```bash
# Trigger holistic review to rescore all traits
curl -X POST http://127.0.0.1:8015/ui/holistic/review \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}'

# Expected response:
{
  "ok": true,
  "user_id": "test_user",
  "traits_updated": 10,    # ← Number of traits rescored
  "global_curiosity": 0.6984,
  "rescore_result": {
    "rr_by_trait": {...},
    "curiosity_by_trait": {...}
  }
}
```

### 3. Test Direct UCN/RR Rescore

```bash
# Call UCN/RR directly
curl -X POST http://127.0.0.1:8011/api/rescore \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "traits": [
      {"id": "PaDNA.EyeDNA.Color", "value": "Blue", "rr": 80}
    ]
  }'

# Expected response:
{
  "ok": true,
  "user_id": "test_user",
  "rr_by_trait": {
    "PaDNA.EyeDNA.Color": 80.0
  },
  "curiosity_by_trait": {
    "PaDNA.EyeDNA.Color": 0.782
  }
}
```

## Common Issues and Solutions

### Issue: RR Scores Are Null

**Symptoms:**
- Traits exist but `rr: null` in unabridged data
- UI shows "0.0" for RR scores

**Root Cause:**
- Legacy data from before RR implementation
- UCN/RR not configured (check `UCNRR_BASE_URL`)
- Network error between Core and UCN/RR

**Solution:**
1. Verify UCN/RR is running: `curl http://127.0.0.1:8011/api/health`
2. Check Core config: `curl http://127.0.0.1:8015/health` (ucnrr_enabled must be true)
3. Trigger holistic review via Settings UI or API
4. For new data, ensure photo import shows `"rescore_triggered": true`

### Issue: User Has No Traits

**Symptoms:**
- Holistic review returns `"error": "no_traits"`
- Unabridged shows empty traits array

**Root Cause:**
- User was created but never had data ingested
- No photos uploaded
- No conversations with Head Coach

**Solution:**
1. Upload photos via Photo Coach
2. Start conversation with Head Coach
3. Import data via onboarding or bulk import
4. Once data exists, holistic review will work

### Issue: Photo Data Bypasses Head Coach

**THIS SHOULD NEVER HAPPEN**

If you find photo data going directly to Core without Head Coach orchestration:

1. **STOP** - This breaks the architecture
2. Check that `/ui/photo/import` calls `head_coach.shape_photo_import()` (line 4245)
3. Verify UCN/RR validation happens (line 4258)
4. Ensure RR scores are updated after rescore (lines 4214-4220)
5. Document the bug and fix immediately

## Future Data Sources

When adding new data sources (wearables, social media, etc.):

### ✅ CORRECT Pattern:
```python
@app.post("/new_source/ingest")
def ingest_new_source(payload: Dict[str, Any]):
    # 1. Extract raw data
    raw_data = payload.get("data")

    # 2. HEAD COACH ORCHESTRATION (mandatory!)
    hc_result = head_coach.shape_new_source_import(
        raw_data=raw_data,
        user_id=user_id,
        metadata=metadata
    )

    # 3. Store in Core
    write_user_state(user_id, resolved, evidence, obs)

    # 4. Trigger UCN/RR rescore
    ucnrr_base = _ucnrr_base_url()
    if ucnrr_base:
        response = requests.post(
            f"{ucnrr_base}/api/rescore",
            json={"user_id": user_id, "traits": traits_payload}
        )
        # Update with RR scores
        # Save again
```

### ❌ INCORRECT Pattern (DO NOT DO THIS):
```python
@app.post("/new_source/ingest")
def ingest_new_source(payload: Dict[str, Any]):
    # ❌ WRONG: Bypasses Head Coach
    raw_data = payload.get("data")
    resolved[trait_id] = raw_data
    write_user_state(user_id, resolved, evidence, obs)
```

## Monitoring and Validation

### Key Metrics to Track

1. **Rescore Success Rate**
   - Should be >99% for healthy system
   - Track via `rescore_triggered: true` in responses

2. **RR Coverage**
   - % of traits with non-null RR scores
   - Query: `SELECT COUNT(*) WHERE rr IS NOT NULL / COUNT(*)`

3. **Head Coach Processing**
   - All ingestion endpoints should log HC processing
   - Monitor for bypassed routes

### Health Checks

```bash
# Daily validation script
#!/bin/bash

# 1. Core + UCN/RR connectivity
core_health=$(curl -s http://127.0.0.1:8015/health | jq -r '.features.ucnrr_enabled')
if [ "$core_health" != "true" ]; then
  echo "❌ UCN/RR not enabled in Core"
  exit 1
fi

# 2. Sample user RR coverage
rr_coverage=$(curl -s "http://127.0.0.1:8015/ui/unabridged?user_id=TEST" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); traits=d.get('traits',[]); \
  with_rr=[t for t in traits if t.get('rr') is not None]; \
  print(len(with_rr)/len(traits) if traits else 0)")

if (( $(echo "$rr_coverage < 0.9" | bc -l) )); then
  echo "⚠️  RR coverage below 90%: $rr_coverage"
fi

echo "✅ System healthy - RR coverage: $rr_coverage"
```

## Related Documentation

- [Core Benchmarks Roadmap v2.1](Core_Benchmarks_Roadmap_v2.1.md) - RSC and holistic review benchmarks
- [AI Intelligence Integration Framework](AI_Intelligence_Integration_Framework.md) - AI override architecture
- [Decision Diff Panel Specification](Decision_Diff_Panel_Specification.md) - UI for AI decision transparency

## Changelog

- **2025-10-06**: Initial documentation of critical data flow architecture
  - Documented Photo Coach → HC → Core → UCN/RR flow
  - Added holistic review rescore path
  - Included testing procedures and troubleshooting
  - Defined patterns for future data sources
