# RR Migration Guide

Complete guide for migrating from legacy RR (z-score) to new RR (population percentile).

## Overview

This migration updates the RR calculation from a statistical z-score approach to a true population percentile system with:
- **Per-Trait RR**: Percentile rank vs all users with same trait (0-100)
- **Container RR**: Coverage-weighted average across DNA container
- **Overall User RR**: Global refinement score across all containers

## Prerequisites

1. **Backup**: All user data will be backed up automatically
2. **Time**: Migration takes ~5-10 minutes for 100 users
3. **Access**: Need write access to data directory

## Migration Steps

### Step 1: Analyze Current State

First, understand the scope of the migration:

```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo
python tools/migrate_rr_data.py --analyze-only
```

This outputs:
- Total users with traits
- Count of invalid RR values (>100, null, negative)
- Sample of affected users

**Example output:**
```json
{
  "total_users": 150,
  "users_with_traits": 145,
  "invalid_rr_patterns": {
    "rr_null": 523,
    "rr_greater_than_100": 1247,
    "rr_negative": 0
  }
}
```

### Step 2: Run Migration (Dry Run)

Test the migration without making changes:

```bash
python tools/migrate_rr_data.py --dry-run
```

This shows:
- What would be backed up
- What distributions would be built
- How many traits would be migrated

### Step 3: Run Full Migration

Execute the complete migration:

```bash
python tools/migrate_rr_data.py \
  --data-dir data \
  --distribution-dir data/population_distributions \
  --k-min 50
```

**What happens:**
1. ✅ Creates backup at `data/backups/rr_migration_<timestamp>/`
2. ✅ Builds population distributions (one per trait)
3. ✅ Recalculates RR for all users
4. ✅ Updates `resolved.json` files with correct RR/curiosity
5. ✅ Adds migration provenance

**Expected output:**
```
[1/5] Analyzing current state...
  - Total users: 150
  - Users with traits: 145
  - Invalid RR (null): 523
  - Invalid RR (>100): 1247

[2/5] Creating backup...
  - Backup created at: data/backups/rr_migration_20250106_143022/
  - Backed up 150 users

[3/5] Rebuilding population distributions...
  - Built 87 trait distributions

[4/5] Migrating user RR data...
  [1/150] BSTest: 109 traits migrated
  [2/150] abtest: 51 traits migrated
  ...

[5/5] Migration complete!
SUMMARY:
  - Users scanned: 150
  - Users with invalid RR: 145
  - Traits migrated: 1770
  - Traits unchanged: 0
  - Errors: 0

Backup saved to: data/backups/rr_migration_20250106_143022/
```

### Step 4: Verify Migration

Check a few users to ensure RR values are now 0-100:

```bash
# Check specific user
python -m core.rr_aggregation BSTest

# Expected output
{
  "overall": {
    "rr": 64.5,
    "curiosity": 35.5,
    "container_count": 1,
    "trait_count": 109
  },
  "containers": [
    {
      "container": "PaDNA",
      "rr": 64.5,
      "curiosity": 35.5,
      "trait_count": 109,
      "coverage": 87.3,
      "traits": [...]
    }
  ]
}
```

### Step 5: Test API Endpoints

Verify new RR endpoints work:

```bash
# Start Core API
cd ReDNACoreDemo
.venv/bin/python -m uvicorn core.api:app --port 8015

# Test trait-level RR
curl "http://localhost:8015/rr/trait?user_id=BSTest&trait_path=PaDNA.HairDNA.Color"

# Test container-level RR
curl "http://localhost:8015/rr/container?user_id=BSTest&container=PaDNA"

# Test overall RR
curl "http://localhost:8015/rr/overall?user_id=BSTest"
```

## Post-Migration

### Update Frontend

The frontend should already display RR correctly after migration. Verify:

1. Open Head Coach for a migrated user
2. Check header shows RR in 0-100 range (not 800+)
3. Open DNA panel, verify individual traits show RR 0-100
4. Run holistic review, verify RR updates correctly

### Periodic Maintenance

**Weekly:** Rebuild distributions to include new users
```bash
curl -X POST "http://localhost:8015/rr/rebuild_distributions"
```

**Monthly:** Full migration for any legacy data
```bash
python tools/migrate_rr_data.py --k-min 50
```

## Rollback

If issues occur, restore from backup:

```bash
# Find latest backup
ls -lt data/backups/

# Restore
cp -r data/backups/rr_migration_20250106_143022/users/* data/users/
```

## Troubleshooting

### Issue: "No distribution found for trait"

**Cause:** Trait has < 5 users (k-anonymity threshold)

**Solution:** System will use fictional prior (Gaussian blend). RR will show `method: "small_n_blend"` in metadata.

### Issue: "RR still showing >100"

**Cause:** User not included in migration

**Solutions:**
1. Check if user exists: `ls data/users/`
2. Re-run migration: `python tools/migrate_rr_data.py`
3. Check migration log for errors

### Issue: "Container RR is null"

**Cause:** Container has no traits with valid RR

**Solution:**
1. Check if traits exist: `cat data/users/<user_id>/resolved.json | jq '.resolved | keys'`
2. Verify trait UCNs are present
3. Run holistic review to backfill UCNs

### Issue: "Migration takes too long"

**Cause:** Large user base (>500 users)

**Solutions:**
1. Use `--dry-run` first to estimate time
2. Consider running overnight
3. Migration is idempotent - safe to re-run

## Testing Checklist

After migration, verify:

- [ ] All users have RR values 0-100
- [ ] Curiosity = 100 - RR for all traits
- [ ] Container RR aggregates correctly
- [ ] Overall RR calculates across containers
- [ ] Holistic review updates RR properly
- [ ] Frontend displays RR correctly
- [ ] API endpoints return valid data
- [ ] Backup was created successfully

## File Changes

Migration updates these files per user:

**`data/users/<user_id>/resolved.json`:**
```json
{
  "resolved": {
    "PaDNA.HairDNA.Color": {
      "value": "Blonde",
      "ucn": 440.0,
      "rr": 45.3,              // ← Changed from 840.3 to 45.3
      "curiosity": 54.7,        // ← Updated to 100 - RR
      "provenance": {
        "rr_migrated": "2025-01-06T14:30:22Z",
        "rr_method": "histogram_percentile",
        "rr_population_size": 150,
        "rr_blending_lambda": null  // No blending (n >= 50)
      }
    }
  }
}
```

**New files created:**

- `data/population_distributions/PaDNA_HairDNA_Color.json` (histogram)
- `data/population_distributions/manifest.json` (tracking)
- `data/backups/rr_migration_<timestamp>/` (backup)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ RR Calculation Architecture (Post-Migration)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Per-Trait RR (0-100 percentile)                           │
│  ├─ rr_per_trait.py: PerTraitRRCalculator                  │
│  ├─ rr_histogram.py: TraitDistributionHistogram            │
│  └─ Uses: Population distributions with k-anonymity        │
│                                                             │
│  Container RR (coverage-weighted avg)                      │
│  ├─ rr_aggregation.py: ContainerRRAggregator               │
│  └─ Weights: α×pop_size + (1-α)×ucn                        │
│                                                             │
│  Overall User RR (global score)                            │
│  └─ Weighted average across containers                     │
│                                                             │
│  Data Flow:                                                │
│  1. Photo Coach → UCN                                      │
│  2. Holistic Review → Per-Trait RR (via histogram)         │
│  3. API Aggregation → Container RR + Overall RR            │
│  4. Frontend Display → User sees 0-100 percentile          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

After successful migration:

1. **Monitor RR accuracy** - Are percentiles reasonable?
2. **Adjust k_min** - If too many traits lack distributions, lower k_min
3. **Tune alpha** - Adjust coverage weighting (default 0.5)
4. **Add curiosity-driven behaviors** - Low RR → autonomous research
5. **Build UI features** - Show container RR, overall RR in panels

## References

- [RR_ARCHITECTURE_MULTILEVEL.md](RR_ARCHITECTURE_MULTILEVEL.md) - Core design
- [RR_IMPLEMENTATION_REFINEMENTS.md](RR_IMPLEMENTATION_REFINEMENTS.md) - Implementation details
- [RR_SYSTEM_INDEX.md](RR_SYSTEM_INDEX.md) - Master index

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review migration logs in terminal
3. Inspect backup files to understand changes
4. Consult RR documentation in `docs/`
