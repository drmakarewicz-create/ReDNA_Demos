# RR (Refinement Rating) System - Master Index

**Purpose**: Central reference for all RR architecture, implementation, and operational documentation
**Status**: 🟢 Active - All future RR work must align with these specifications
**Last Updated**: 2025-10-06

---

## 📚 Document Hierarchy

### 1. Core Architecture (MUST READ)

#### [RR_ARCHITECTURE_MULTILEVEL.md](./RR_ARCHITECTURE_MULTILEVEL.md)
**Purpose**: Defines the three-level RR system architecture

**Key Concepts**:
- **Per-Trait RR**: Percentile rank for specific trait (e.g., NoseTipShape RR 30 = more refined than 30% of users for that trait)
- **Container RR**: Weighted average across DNA container (e.g., PaDNA RR = aggregate of all 109 PaDNA traits)
- **Overall User RR**: Global refinement score across all traits

**Formula** (Per-Trait RR):
```
RR = (users_with_trait_UCN_below / total_users_with_trait) × 100
```

**Curiosity Relationship**:
```
Curiosity = 100 - RR
```

**When to Reference**:
- Implementing any RR calculation logic
- Understanding RR use cases (feature access, gamification, AI motivation)
- Designing UI displays for RR scores

---

#### [RR_IMPLEMENTATION_REFINEMENTS.md](./RR_IMPLEMENTATION_REFINEMENTS.md)
**Purpose**: Production-ready implementation details with edge case handling

**Critical Refinements**:
1. **Tie Handling**: Mid-rank percentile calculation when multiple users have same UCN
2. **Small-N Protection**: Blend empirical percentile with fictional prior when population < 50 users
3. **Histogram Storage**: O(log b) percentile queries with k-anonymity privacy guarantees (k≥5)
4. **Coverage Weighting**: Configurable alpha for UCN vs breadth in container RR
5. **Outlier Protection**: Winsorize at P1/P99 to prevent extreme values warping distribution
6. **Curiosity Satiation**: 48-hour cool-down window after RR jumps to prevent over-harvesting
7. **Versioned Distributions**: Audit trail for population distribution changes over time

**Formula** (Small-N Blending):
```python
lambda_blend = min(1.0, n / k_min)  # k_min = 50
RR = lambda_blend × RR_empirical + (1 - lambda_blend) × RR_prior
```

**When to Reference**:
- Writing production RR calculation code
- Debugging unexpected RR values
- Privacy/security review
- Performance optimization

---

### 2. Related Systems

#### [RR_BASELINE_REQUIREMENT.md](./RR_BASELINE_REQUIREMENT.md)
**Purpose**: Need for fictionalized user baseline to ensure statistical validity

**Problem Addressed**: With only 1-2 real users, RR percentiles are meaningless

**Solution**: 50-100 synthetic baseline users with realistic trait distributions serve as comparison population

**Integration**: Feeds into small-N protection (when real population < 50, fictional users stabilize percentile)

**When to Reference**:
- Setting up new deployment with few users
- Understanding why RR values are stable even with small user base

---

#### [CRITICAL_DATA_FLOW_ARCHITECTURE.md](./CRITICAL_DATA_FLOW_ARCHITECTURE.md)
**Purpose**: Sacred principle - ALL data flows through Head Coach → Core → UCN/RR → Core (updated)

**RR Integration**:
- Every trait ingestion triggers UCN calculation
- UCN calculation triggers RR recalculation
- RR recalculation updates curiosity
- Curiosity updates trigger Core intelligence behaviors

**When to Reference**:
- Adding new data sources (photos, conversations, external APIs)
- Understanding why RR updates happen asynchronously
- Debugging data flow issues

---

### 3. Operational Documentation

#### Population Distribution Management

**Daily Rebuild** (Scheduled: 3:00 AM UTC):
```bash
# Rebuild all population distributions from current user data
python ReDNACoreDemo/tools/rebuild_population_distributions.py --all

# Rebuild specific trait
python ReDNACoreDemo/tools/rebuild_population_distributions.py --trait "PaDNA.HairDNA.Color"
```

**On-Demand Update**:
```bash
# Incremental update after holistic review
python ReDNACoreDemo/tools/update_population_distribution.py --user <user_id> --trait <trait_path>
```

**File Structure**:
```
data/population_distributions/
├── PaDNA.HairDNA.Color_v1.json      # Histogram with k-anonymity
├── PaDNA.EyeDNA.IrisColor_v1.json
├── Personality.Openness_v1.json
└── overall_users_v1.json             # For overall RR calculation
```

---

#### Data Migration (One-Time)

**Problem**: Legacy data has UCN values (0-1000) stored in RR field instead of percentiles (0-100)

**Solution**:
```bash
# Scan all users for invalid RR values
python ReDNACoreDemo/tools/migrate_rr_data.py --scan

# Fix invalid values (sets to null, triggers recalculation)
python ReDNACoreDemo/tools/migrate_rr_data.py --fix --user <user_id>

# Fix all users
python ReDNACoreDemo/tools/migrate_rr_data.py --fix-all
```

**Validation**:
```bash
# Verify all RR values are in valid range [0, 100]
python ReDNACoreDemo/tools/validate_rr_consistency.py --all
```

---

### 4. API Reference

#### GET /rr/trait
Get detailed RR information for specific trait.

**Endpoint**: `GET /rr/trait?user_id={user_id}&trait_path={trait_path}`

**Response**:
```json
{
  "user_id": "bstest",
  "trait_path": "PaDNA.HairDNA.Color",
  "ucn": 950.0,
  "rr": 85.0,
  "curiosity": 15.0,
  "population_stats": {
    "total_users": 1000,
    "users_below": 850,
    "percentile": 85.0,
    "mean_ucn": 625.0,
    "median_ucn": 600.0
  },
  "rr_metadata": {
    "distribution_version": "1.0",
    "calculated_at": "2025-10-06T12:00:00Z",
    "method": "histogram_percentile"
  }
}
```

---

#### GET /rr/container
Get container-level RR with curiosity map for targeting.

**Endpoint**: `GET /rr/container?user_id={user_id}&container={container}`

**Response**:
```json
{
  "user_id": "bstest",
  "container": "PaDNA",
  "rr": 72.3,
  "curiosity": 27.7,
  "trait_count": 109,
  "avg_ucn": 825.0,
  "coverage": 87.0,
  "curiosity_map": {
    "PaDNA.NoseTipShape": 95.0,
    "PaDNA.EarShape": 88.0,
    "PaDNA.HairDNA.Color": 15.0
  },
  "top_priorities": [
    {"trait": "PaDNA.NoseTipShape", "curiosity": 95.0, "rr": 5.0},
    {"trait": "PaDNA.EarShape", "curiosity": 88.0, "rr": 12.0},
    {"trait": "PaDNA.HandSize", "curiosity": 82.0, "rr": 18.0}
  ]
}
```

---

#### GET /rr/overall
Get user's overall ReDNA RR across all traits.

**Endpoint**: `GET /rr/overall?user_id={user_id}`

**Response**:
```json
{
  "user_id": "bstest",
  "overall_rr": 64.5,
  "overall_curiosity": 35.5,
  "total_traits": 150,
  "avg_ucn": 675.0,
  "rr_by_container": {
    "PaDNA": {"rr": 72.3, "curiosity": 27.7, "trait_count": 109},
    "Personality": {"rr": 45.2, "curiosity": 54.8, "trait_count": 15},
    "Cognitive": {"rr": 58.7, "curiosity": 41.3, "trait_count": 26}
  },
  "rank_label": "Developing",
  "percentile_description": "More refined than 64% of users"
}
```

---

### 5. Core Intelligence Integration

#### Curiosity-Driven Behaviors

**Low RR (High Curiosity) Triggers**:
- **RR < 20** (Curiosity > 80):
  - Core prioritizes autonomous research (analyze old photos, search public data)
  - Head Coach plans direct questions about this trait
  - Explorer flags trait for immediate evidence gathering

- **RR 20-50** (Curiosity 50-80):
  - Head Coach incorporates into conversation naturally
  - Photo Coach re-analyzes existing photos for this trait
  - System suggests user actions (upload photo, answer survey)

- **RR 50-80** (Curiosity 20-50):
  - Periodic rechecks for drift/decay
  - Low-priority questions when convenient

- **RR > 80** (Curiosity < 20):
  - Well-refined, minimal system attention
  - Cool-down prevents over-harvesting
  - Minimum curiosity floor (5-10) ensures periodic validation

**Head Coach Planning Example**:
```python
def plan_conversation(user_id: str):
    """Head Coach uses curiosity map to prioritize topics."""

    container_data = get_container_rr(user_id, "PaDNA")

    # Get top 5 high-curiosity traits
    priorities = container_data["top_priorities"]

    for trait_info in priorities[:3]:  # Focus on top 3
        trait = trait_info["trait"]
        curiosity = trait_info["curiosity"]

        if curiosity > 80:
            add_urgent_question(f"Ask directly about {trait}")
        elif curiosity > 50:
            add_casual_question(f"Work into conversation: {trait}")
```

---

### 6. UI Guidelines

#### Display Standards

**Per-Trait (Unabridged Panel)**:
```
PaDNA.HairDNA.Color: "Blonde"
  UCN: 950  |  RR: 85  |  Curiosity: 15%
  ℹ️ More refined than 85% of users for this trait.
     Curiosity 15: we'll occasionally recheck this.
```

**Container (RR by DNA Panel)**:
```
👤 Physical Appearance (PaDNA)
   109 traits | Coverage: 87%
   RR: 72.3 (Well-Refined) | Curiosity: 27.7%

   🎯 Top priorities (low RR):
   • NoseTipShape: RR 5 → Upload profile photo
   • EarShape: RR 12 → Answer quick check
   • HandSize: RR 18 → Measure & log
```

**Overall (Profile Header)**:
```
BSTest
Overall RR: 64.5 (Developing)
More refined than 64% of users
ℹ️ How this is calculated: Your RR is your percentile rank
   compared to all active users. Higher = more complete profile.
```

#### RR Band Labels

| RR Range | Label | Color | Description |
|----------|-------|-------|-------------|
| 98-100 | Elite | Purple | Top 2% - exceptional refinement |
| 90-97 | Exceptional | Violet | Top 10% - very well refined |
| 75-89 | Well-Refined | Blue | Top 25% - strong profile |
| 50-74 | Developing | Cyan | Top 50% - good progress |
| 25-49 | Emerging | Teal | Bottom 50% - early stage |
| 0-24 | Early | Slate | Bottom 25% - just starting |

---

### 7. Testing Requirements

All RR implementations MUST pass:

**Unit Tests**:
- ✅ Tie handling with mid-rank percentile
- ✅ Small-N blending (n < 50)
- ✅ Histogram k-anonymity (all bins k≥5)
- ✅ Missing trait handling (rr=None, curiosity=100)
- ✅ Outlier winsorization (P1/P99 clipping)
- ✅ Coverage weighting (configurable alpha)
- ✅ Cool-down window enforcement

**Integration Tests**:
- ✅ Holistic review recalculates RR correctly
- ✅ Population distribution rebuild
- ✅ API endpoints return correct format
- ✅ Container RR aggregation from trait RRs

**End-to-End Tests**:
- ✅ User sees correct RR in UI after holistic review
- ✅ Curiosity triggers Head Coach question
- ✅ RR migration fixes invalid values

---

### 8. Privacy & Ethics Requirements

**Privacy Guarantees**:
- ✅ Population distributions use histograms (no raw UCN exposure)
- ✅ K-anonymity enforced (k≥5 per bucket)
- ✅ Versioned distributions for audit trail
- ✅ RR metadata tracks calculation method

**Ethics Review Required For**:
- ❌ Cohort-aware RR (age, ethnicity, etc.) - DISABLED until review
- ❌ Predictive RR (forecasting future refinement)
- ❌ Comparative RR displays ("You vs Friend")

**Audit Trail**:
Every RR calculation must log:
- Distribution version used
- Calculation method (empirical vs blended)
- Timestamp
- Population size at time of calculation

---

### 9. Performance Targets

**Latency**:
- Per-trait RR calculation: < 10ms (histogram lookup O(log b))
- Container RR aggregation: < 50ms (100 traits)
- Overall RR calculation: < 100ms (all containers)
- Population distribution rebuild: < 5 minutes (10,000 users, 500 traits)

**Storage**:
- Per-trait histogram: ~1KB
- 500 traits × 1KB = 500KB total (vs 20MB for raw UCNs)

**Caching**:
- Population distributions: 1-hour TTL
- Trait RR: Real-time (no cache, recalculated on UCN change)
- Container/Overall RR: On-demand (calculated from trait RRs)

---

### 10. Future Enhancements (Phase-Next)

**Planned**:
- Cohort-aware RR (after ethics review)
- RR trend analysis (track user progress over time)
- Predictive RR (ML model forecasts future refinement)
- Social RR features (compare with friends, opt-in only)

**Under Consideration**:
- RR-based feature access (premium at RR 50+)
- Achievement system (badges for RR milestones)
- Gamification (leaderboards, challenges)
- RR decay (penalize inactive users)

---

## Quick Reference Card

**Core Formula**:
```
Per-Trait RR = (users_below / total_users) × 100
Curiosity = 100 - RR
```

**RR Levels**:
1. Trait-level (e.g., NoseTipShape RR 30)
2. Container-level (e.g., PaDNA RR 72.3)
3. Overall (e.g., User RR 64.5)

**Key Files**:
- `core/rr_per_trait.py` - Per-trait percentile calculator
- `core/rr_aggregation.py` - Container/overall aggregation
- `core/holistic.py` - Integration with holistic review
- `data/population_distributions/` - Histogram storage

**Migration Commands**:
```bash
# Fix invalid RR data
python ReDNACoreDemo/tools/migrate_rr_data.py --fix-all

# Rebuild distributions
python ReDNACoreDemo/tools/rebuild_population_distributions.py --all

# Validate consistency
python ReDNACoreDemo/tools/validate_rr_consistency.py --all
```

---

## Document Change Log

| Date | Document | Change | Author |
|------|----------|--------|--------|
| 2025-10-06 | RR_ARCHITECTURE_MULTILEVEL.md | Initial architecture design | Claude Code |
| 2025-10-06 | RR_IMPLEMENTATION_REFINEMENTS.md | ChatGPT collaborative review refinements | Claude Code + ChatGPT |
| 2025-10-06 | RR_SYSTEM_INDEX.md | Master index created | Claude Code |

---

## Compliance Checklist

Before implementing ANY RR-related code, verify:

- [ ] Have you read RR_ARCHITECTURE_MULTILEVEL.md?
- [ ] Have you read RR_IMPLEMENTATION_REFINEMENTS.md?
- [ ] Does your implementation handle ties (mid-rank)?
- [ ] Does your implementation protect small-N (fictional prior blending)?
- [ ] Does your implementation use histograms (not raw UCNs)?
- [ ] Does your implementation enforce k-anonymity (k≥5)?
- [ ] Does your implementation winsorize outliers (P1/P99)?
- [ ] Does your implementation version distributions?
- [ ] Does your implementation log audit trail?
- [ ] Have you written tests for edge cases?
- [ ] Have you updated this index if adding new RR features?

---

**This index is the authoritative source for all RR system documentation. All future RR work MUST align with these specifications.**

**Last Updated**: 2025-10-06
**Status**: 🟢 Active and Enforced
**Maintained By**: Core Development Team
