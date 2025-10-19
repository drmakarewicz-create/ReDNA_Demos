# RR System - Quick Reference

**Last Updated**: October 6, 2025
**Status**: ✅ Operational

## One-Minute Overview

**What is RR?**
- RR = Refinement Rating (0-100 percentile)
- Shows how refined a user's trait is compared to other users
- Example: RR=95 means "more refined than 95% of users"

**Why RR?**
- Drives AI curiosity (low RR = high curiosity = AI asks questions)
- Gamification (badges, progress tracking)
- Feature access (unlock features at certain RR levels)

**Current Status:**
- ✅ 79 traits with valid RR (0-100)
- ✅ 12 population distributions
- ✅ Multi-level hierarchy working
- ✅ Privacy protection enabled

## Quick Commands

### Check User RR
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos/ReDNACoreDemo

# Check specific user
python3 -c "
from core.storage import read_user_state
resolved, _, _ = read_user_state('bstest')
for trait_path, entry in list(resolved.items())[:10]:
    rr = entry.get('rr')
    ucn = entry.get('ucn')
    print(f'{trait_path}: RR={rr}, UCN={ucn}')
"
```

### Run Integration Test
```bash
python3 tests/test_rr_integration.py
```

### Calculate User Summary
```bash
python3 -m core.rr_aggregation bstest
```

### Rebuild Distributions
```bash
python3 -m core.rr_distribution_builder
```

### Run Migration
```bash
# Analyze first
python3 tools/migrate_rr_data.py --analyze-only

# Dry run
python3 tools/migrate_rr_data.py --dry-run

# Full migration
python3 tools/migrate_rr_data.py
```

## Key Concepts

### Three-Level Hierarchy

```
User: "bstest"
├── Overall RR: 87.67 (global refinement)
├── Container: PaDNA
│   ├── RR: 87.67 (weighted average)
│   └── Traits:
│       ├── HairColor: RR 95.88 (more refined than 95.88% of users)
│       ├── HairLength: RR 83.89
│       ├── HairTexture: RR 87.14
│       └── HairVolume: RR 89.12
```

### RR Formula

```
Per-Trait RR = (users_with_lower_UCN / total_users_with_trait) × 100

Curiosity = 100 - RR

Container RR = Σ(RR_trait × weight) / Σ(weight)
```

### Weight Formula

```
weight = α × (population_size/1000) + (1-α) × (ucn/1000)

α = 0.5 (default, balances population quality and data quality)
```

## Common Tasks

### Add New User
1. Create user in system
2. Add traits through photo coach or head coach
3. Run holistic review
4. RR automatically calculated (if ≥5 users have same trait)

### Update RR After New Data
```bash
# Option 1: Run holistic review (updates one user)
curl -X POST "http://localhost:8015/ui/holistic/review" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bstest"}'

# Option 2: Rebuild distributions (updates all users)
curl -X POST "http://localhost:8015/rr/rebuild_distributions?force=true"
```

### Check RR Status
```bash
# Simple check
python3 tools/migrate_rr_data_simple.py

# Detailed analysis
python3 tools/migrate_rr_data.py --analyze-only
```

### Backup Data
```bash
# Automatic backup before migration
python3 tools/migrate_rr_data.py

# Manual backup
cp -r data/users data/backups/manual_$(date +%Y%m%d_%H%M%S)
```

### Restore Data
```bash
# Find backups
ls -lt data/backups/

# Restore
cp -r data/backups/rr_migration_<timestamp>/users/* data/users/
```

## Troubleshooting

### RR shows null
**Cause**: Trait has <5 users
**Solution**: Normal - need more users with that trait

### RR shows >100
**Cause**: Old data not migrated
**Solution**: `python3 tools/migrate_rr_data.py`

### RR not updating
**Cause**: Distributions not rebuilt
**Solution**: `curl -X POST "http://localhost:8015/rr/rebuild_distributions?force=true"`

### Privacy warning
**Cause**: K-anonymity violated (small population)
**Solution**: Acceptable for demo - add more users for production

## File Locations

```
ReDNACoreDemo/
├── core/
│   ├── rr_histogram.py           # Histogram storage
│   ├── rr_per_trait.py            # Per-trait calculator
│   ├── rr_distribution_builder.py # Distribution builder
│   ├── rr_aggregation.py          # Container/overall RR
│   ├── holistic.py                # Uses new RR (line 83)
│   └── api.py                     # RR endpoints (line 7190)
├── data/
│   ├── users/<user_id>/resolved.json  # RR values stored here
│   ├── population_distributions/      # 12 distributions
│   │   ├── manifest.json              # Tracks distributions
│   │   └── *.json                     # One file per trait
│   └── backups/rr_migration_*/        # Migration backups
└── docs/
    ├── RR_QUICK_REFERENCE.md          # ← You are here
    ├── RR_SYSTEM_INDEX.md             # Master index
    ├── RR_COMPLETION_SUMMARY.md       # Implementation summary
    ├── RR_ARCHITECTURE_MULTILEVEL.md  # System design
    ├── RR_IMPLEMENTATION_REFINEMENTS.md # Technical details
    └── RR_MIGRATION_GUIDE.md          # Migration procedures
```

## API Endpoints

```bash
# Per-trait RR
GET /rr/trait?user_id=bstest&trait_path=PaDNA.HairDNA.Color
# Returns: { "rr": 95.88, "curiosity": 4.12, "method": "histogram_percentile", ... }

# Container RR
GET /rr/container?user_id=bstest&container=PaDNA
# Returns: { "rr": 87.67, "curiosity": 12.33, "trait_count": 4, ... }

# Overall RR
GET /rr/overall?user_id=bstest
# Returns: { "overall": { "rr": 87.67, "curiosity": 12.33, ... }, "containers": [...] }

# Rebuild distributions
POST /rr/rebuild_distributions?force=true
# Returns: { "ok": true, "distributions_built": 12, "total_users": 69, ... }
```

## Python API

### Calculate Per-Trait RR
```python
from pathlib import Path
from core.rr_per_trait import PerTraitRRCalculator

calculator = PerTraitRRCalculator(
    distribution_dir=Path("data/population_distributions"),
    k_min=50
)

metadata = calculator.calculate_rr_metadata(ucn=950.0, trait_path="PaDNA.HairDNA.Color")
print(f"RR: {metadata['rr']}")  # 95.88
print(f"Curiosity: {metadata['curiosity']}")  # 4.12
```

### Calculate Container RR
```python
from pathlib import Path
from core.rr_aggregation import ContainerRRAggregator

aggregator = ContainerRRAggregator(
    distribution_dir=Path("data/population_distributions"),
    k_min=50,
    alpha=0.5
)

result = aggregator.calculate_container_rr("bstest", "PaDNA")
print(f"Container RR: {result['rr']}")  # 87.67
```

### Calculate Overall RR
```python
from pathlib import Path
from core.rr_aggregation import calculate_user_rr_summary

summary = calculate_user_rr_summary(
    user_id="bstest",
    distribution_dir=Path("data/population_distributions"),
    k_min=50,
    alpha=0.5
)

print(f"Overall RR: {summary['overall']['rr']}")  # 87.67
```

## Decision Tree

### When to use what?

**Need to check single trait RR?**
→ Use `GET /rr/trait` or `PerTraitRRCalculator`

**Need to check container RR (e.g., PaDNA)?**
→ Use `GET /rr/container` or `ContainerRRAggregator.calculate_container_rr()`

**Need to check overall user RR?**
→ Use `GET /rr/overall` or `calculate_user_rr_summary()`

**Need to update RR for one user?**
→ Run holistic review for that user

**Need to update RR for all users?**
→ Rebuild distributions with `POST /rr/rebuild_distributions?force=true`

**Need to fix invalid RR values?**
→ Run migration: `python3 tools/migrate_rr_data.py`

**Need to add new users to system?**
→ Just add them - distributions rebuild automatically on next holistic review

## Integration with Other Systems

### Holistic Review
Holistic review now automatically uses the new RR calculator:
```python
# In core/holistic.py (line 83)
rr_metadata = rr_calculator.calculate_rr_metadata(new_ucn, path)
new_rr = rr_metadata["rr"]
```

### Head Coach
Head Coach displays RR in header:
```typescript
// In web/src/app/page-client.tsx
<div className="text-xs opacity-75">
  RR {snapshot.overall_rr?.toFixed(1) ?? '0.0'}
</div>
```

### Photo Coach
Photo Coach submits traits → Head Coach → Core → UCN/RR calculation:
```
Photo → Trait → Head Coach → Core → RR Calculator → resolved.json
```

## Monitoring

### Check System Health
```bash
# Integration test
python3 tests/test_rr_integration.py

# Check distribution count
ls data/population_distributions/*.json | grep -v manifest | wc -l

# Check user count
python3 -c "from core.storage import list_users; print(len(list_users()))"

# Check valid RR count
python3 tools/migrate_rr_data_simple.py
```

### Performance Metrics
- Distribution building: ~5-10s for 12 traits, 69 users
- RR calculation: <1ms per trait (O(log b))
- Storage: ~1KB per distribution file

### Privacy Compliance
```bash
# Check k-anonymity violations
python3 -c "
from pathlib import Path
import json
dist_dir = Path('data/population_distributions')
violations = 0
for f in dist_dir.glob('*.json'):
    if f.name == 'manifest.json':
        continue
    data = json.loads(f.read_text())
    if any(c < 5 for c in data.get('bin_counts', [])):
        violations += 1
print(f'K-anonymity violations: {violations}/{len(list(dist_dir.glob(\"*.json\")))-1}')
"
```

## Next Steps

### Immediate
- [x] Test integration (DONE - test passing)
- [ ] Test frontend display
- [ ] Add more users to system

### Short Term
- [ ] Implement curiosity-driven behaviors
- [ ] Add RR to DNA panel displays
- [ ] Create user dashboards

### Long Term
- [ ] Gamification (badges, progress bars)
- [ ] Feature gating (unlock at RR thresholds)
- [ ] User motivation ("You're in top 10%!")

## Cheat Sheet

| Task | Command |
|------|---------|
| Check user RR | `python3 -m core.rr_aggregation <user_id>` |
| Run integration test | `python3 tests/test_rr_integration.py` |
| Rebuild distributions | `POST /rr/rebuild_distributions` |
| Run migration | `python3 tools/migrate_rr_data.py` |
| Check migration status | `python3 tools/migrate_rr_data_simple.py` |
| Backup data | `cp -r data/users data/backups/manual_$(date +%Y%m%d)` |
| Restore data | `cp -r data/backups/<timestamp>/users/* data/users/` |

## Support

For detailed information, see:
- [RR_SYSTEM_INDEX.md](RR_SYSTEM_INDEX.md) - Master index
- [RR_COMPLETION_SUMMARY.md](RR_COMPLETION_SUMMARY.md) - Implementation summary
- [RR_MIGRATION_GUIDE.md](RR_MIGRATION_GUIDE.md) - Migration procedures

---

**Status**: ✅ System operational and tested
**Last Integration Test**: October 6, 2025 - PASSED
**Migration Status**: 79/431 traits with valid RR (18.3%)
