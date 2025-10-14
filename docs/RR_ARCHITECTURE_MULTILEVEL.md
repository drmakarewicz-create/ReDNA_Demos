# RR Architecture: Multi-Level Refinement Rating System

**Status**: 🔴 Critical Architecture Mismatch Discovered
**Priority**: High
**Complexity**: High

## Current Problem

The system has **two different RR calculators** that produce incompatible results:

1. **`core/rr_engine.py`** (Currently Used by Holistic Review)
   - Uses statistical z-score against fixed baseline (mean=700, std=150)
   - Returns 0-100 scale but **NOT a true percentile**
   - Does NOT compare against actual population
   - Example: UCN 950 → RR ~67 (synthetic score, not percentile)

2. **`ucn_rr_engine/rr_calculator.py`** (Correct but Unused)
   - Calculates true population percentile
   - Compares user's average UCN against all users
   - Returns: `(users_below / total_users) * 100`
   - **Only calculates overall user RR, not per-trait**

**Result**: BSTest shows RR 840.3 instead of a 0-100 percentile because old data has UCN values stored in RR field.

## Required Architecture: Multi-Level RR

Per user requirements, RR must exist at **three distinct levels**:

### Level 1: Per-Trait RR (Granular)
**Example**: `NoseTipShape` trait RR

**Calculation**:
```python
def calculate_trait_rr(user_id: str, trait_path: str) -> float:
    """
    Calculate RR for a specific trait by comparing against population.

    Returns: 0-100 percentile
    """
    user_ucn = get_user_trait_ucn(user_id, trait_path)

    # Get all users who have this specific trait
    all_trait_ucns = get_population_trait_ucns(trait_path)

    users_below = sum(1 for ucn in all_trait_ucns if ucn < user_ucn)
    total_users = len(all_trait_ucns)

    rr = (users_below / total_users) * 100
    return round(rr, 2)
```

**Example**:
- User has `NoseTipShape` with UCN 440
- 300 users have `NoseTipShape` with UCN < 440
- 700 users have `NoseTipShape` with UCN > 440
- **RR = (300 / 1000) * 100 = 30**

**Use Cases**:
- **Curiosity calculation**: `Curiosity = 100 - RR`
  - NoseTipShape RR 5 → Curiosity 95 → System highly motivated to refine this trait
  - NoseTipShape RR 95 → Curiosity 5 → System not very curious, trait is well-refined
- **Core intelligence**: Low RR traits trigger autonomous research (analyze old photos, ask questions)
- **Head Coach planning**: Incorporate low RR traits into conversation goals
- **User motivation**: User sees which traits need more refinement

### Level 2: Container-Level RR (DNA-Level)
**Example**: Overall `PaDNA` RR

**Calculation**:
```python
def calculate_container_rr(user_id: str, container: str) -> float:
    """
    Calculate RR for entire DNA container (e.g., PaDNA, Personality).

    Returns: 0-100 percentile, weighted average of trait RRs
    """
    # Get all traits in this container for this user
    user_traits = get_user_traits_by_container(user_id, container)

    # Calculate RR for each trait
    trait_rrs = []
    trait_ucns = []
    for trait_path, ucn in user_traits.items():
        trait_rr = calculate_trait_rr(user_id, trait_path)
        trait_rrs.append(trait_rr)
        trait_ucns.append(ucn)

    # Weighted average (higher UCN traits count more)
    total_weight = sum(trait_ucns)
    weighted_rr = sum(rr * ucn for rr, ucn in zip(trait_rrs, trait_ucns)) / total_weight

    return round(weighted_rr, 2)
```

**Example**:
- User has 109 PaDNA traits
- Each trait has its own RR (0-100)
- PaDNA RR = weighted average of all 109 trait RRs
- Higher UCN traits (more confident) contribute more to container RR

**Use Cases**:
- **DNA refinement tracking**: User sees their overall PaDNA refinement
- **Container-level curiosity**: System prioritizes which DNA containers need work
- **Coach specialization**: Photo Coach focuses on low PaDNA RR users
- **Achievement unlocks**: "Reach PaDNA RR 80" milestone

### Level 3: Overall User RR (Global)
**Example**: User's complete ReDNA refinement score

**Calculation**:
```python
def calculate_overall_rr(user_id: str) -> float:
    """
    Calculate user's overall ReDNA RR across ALL traits.

    Returns: 0-100 percentile
    """
    # Get user's average UCN across all traits
    user_avg_ucn = calculate_average_ucn(user_id)

    # Get all users' average UCNs
    population_avg_ucns = get_all_user_avg_ucns()

    users_below = sum(1 for avg_ucn in population_avg_ucns if avg_ucn < user_avg_ucn)
    total_users = len(population_avg_ucns)

    rr = (users_below / total_users) * 100
    return round(rr, 2)
```

**Alternative** (more sophisticated):
```python
def calculate_overall_rr_v2(user_id: str) -> float:
    """
    Weighted average of all container RRs.
    """
    containers = ["PaDNA", "Personality", "Cognitive", ...]
    container_rrs = []
    container_weights = []

    for container in containers:
        rr = calculate_container_rr(user_id, container)
        trait_count = get_trait_count(user_id, container)

        container_rrs.append(rr)
        container_weights.append(trait_count)

    total_weight = sum(container_weights)
    weighted_rr = sum(rr * weight for rr, weight in zip(container_rrs, container_weights)) / total_weight

    return round(weighted_rr, 2)
```

**Use Cases**:
- **Feature access**: "Premium features require RR 50+"
- **User progression**: Gamification, achievements, milestones
- **System intelligence**: High RR users get more sophisticated AI interactions
- **Comparative metrics**: "You're more refined than 78% of users"

## Implementation Hierarchy

```
Overall User RR (e.g., 64.5)
│
├── PaDNA RR (e.g., 72.3)
│   ├── HairDNA.Color RR (e.g., 85.0)
│   ├── HairDNA.Length RR (e.g., 90.0)
│   ├── EyeDNA.IrisColor RR (e.g., 65.0)
│   └── ... (109 PaDNA traits)
│
├── Personality RR (e.g., 45.2)
│   ├── Openness RR (e.g., 30.0)
│   ├── Conscientiousness RR (e.g., 55.0)
│   └── ... (Personality traits)
│
└── Cognitive RR (e.g., 58.7)
    └── ... (Cognitive traits)
```

## Data Storage Structure

### Per-Trait (in resolved.json)
```json
{
  "PaDNA.HairDNA.Color": {
    "resolved_value": "Blonde",
    "ucn": 950.0,
    "rr": 85.0,         // ← Percentile (0-100) vs population for this specific trait
    "curiosity": 15.0,  // ← 100 - RR
    "reasons": ["photo_import:reference_photo_analysis"],
    "notes": {...},
    "population_stats": {
      "users_with_trait": 1000,
      "users_below": 850,
      "percentile": 85.0,
      "last_calculated": "2025-10-06T12:00:00Z"
    }
  }
}
```

### Container-Level (in resolved.json profile section)
```json
{
  "profile": {
    "label": "BSTest",
    "rr": 64.5,           // ← Overall user RR
    "curiosity": 35.5,    // ← 100 - overall RR
    "rr_by_container": {
      "PaDNA": {
        "rr": 72.3,
        "curiosity": 27.7,
        "trait_count": 109,
        "avg_ucn": 825.0
      },
      "Personality": {
        "rr": 45.2,
        "curiosity": 54.8,
        "trait_count": 15,
        "avg_ucn": 600.0
      }
    },
    "last_rr_calculation": "2025-10-06T12:00:00Z"
  }
}
```

## Population Distribution Cache

**File**: `data/population_distributions/`

### Per-Trait Distribution
```json
// data/population_distributions/PaDNA.HairDNA.Color.json
{
  "trait_path": "PaDNA.HairDNA.Color",
  "distribution": [450, 500, 550, 600, 650, ...],  // All UCN values for this trait
  "user_count": 1000,
  "mean_ucn": 625.0,
  "median_ucn": 600.0,
  "std_dev": 150.0,
  "last_updated": "2025-10-06T03:00:00Z"
}
```

### Overall User Distribution
```json
// data/population_distributions/overall_users.json
{
  "distribution": [
    {"user_id": "user1", "avg_ucn": 650.0},
    {"user_id": "user2", "avg_ucn": 700.0},
    ...
  ],
  "user_count": 10000,
  "mean_avg_ucn": 625.0,
  "last_updated": "2025-10-06T03:00:00Z"
}
```

## Calculation Frequency

### Per-Trait RR
- **Triggered**: Every time trait UCN changes (after rescore)
- **Frequency**: Real-time (immediate after holistic review or new evidence)
- **Cache**: 1-hour stale check (can use cached population distribution)

### Container RR
- **Triggered**: After per-trait RR updates
- **Frequency**: Real-time (recalculated from trait RRs)
- **Cache**: Not cached, calculated on-demand from trait RRs

### Overall User RR
- **Triggered**: After container RR updates
- **Frequency**: Real-time (recalculated from container RRs)
- **Cache**: Not cached, calculated on-demand from container RRs

### Population Distribution Rebuild
- **Schedule**: Daily at 3:00 AM UTC
- **Process**:
  1. Query all users' trait UCNs
  2. Group by trait_path
  3. Save per-trait distributions
  4. Calculate overall user avg UCNs
  5. Save overall distribution
- **Duration**: ~5-10 minutes for 10,000 users

## Migration Strategy

### Phase 1: Fix Data (Current Priority)
**Problem**: BSTest has UCN values (840.3) stored in RR field
**Solution**:
1. Run data migration to clear invalid RR values (>100)
2. Set RR to null for all traits
3. Trigger holistic review to recalculate with correct formula

### Phase 2: Implement Per-Trait RR Calculator
**Location**: `ReDNACoreDemo/core/rr_per_trait.py`
**Features**:
- Load population distribution for specific trait
- Calculate percentile vs population
- Handle missing population data (use placeholder until distribution built)
- Cache population distributions with 1-hour TTL

### Phase 3: Update Holistic Review
**File**: `ReDNACoreDemo/core/holistic.py` line 69
**Change**:
```python
# BEFORE (incorrect)
new_rr = rr_engine.compute_rr(path, value, new_ucn, baselines, previous_rr=previous_rr)

# AFTER (correct)
new_rr = rr_per_trait.calculate_trait_rr(user_id, path, new_ucn)
```

### Phase 4: Add Container & Overall RR Calculation
**Location**: `ReDNACoreDemo/core/rr_aggregation.py`
**Features**:
- Calculate container RR from trait RRs (weighted average)
- Calculate overall user RR from container RRs
- Store in profile section of resolved.json

### Phase 5: Build Population Distribution System
**Components**:
1. **Initial Build**: Script to populate distributions from existing users
2. **Daily Rebuild**: Cron job at 3 AM UTC
3. **Incremental Update**: Option to update single trait distribution on-demand

### Phase 6: Integrate with Core Intelligence
**Use Cases**:
1. **Curiosity-Driven Research**: Core checks trait RR, prioritizes low RR traits
2. **Head Coach Planning**: Incorporate low RR traits into conversation goals
3. **Autonomous Photo Analysis**: System reviews old photos to improve low RR PaDNA traits
4. **Smart Question Asking**: Head Coach asks about traits with high curiosity

## Testing Strategy

### Unit Tests
```python
def test_trait_rr_calculation():
    """Test per-trait RR calculation."""
    # Setup: 1000 users with NoseTipShape UCNs
    population = [random.randint(200, 800) for _ in range(1000)]

    # User has UCN 440
    user_ucn = 440

    # Expected: ~30% of users have lower UCN
    expected_rr = 30.0

    actual_rr = calculate_trait_rr("test_user", "NoseTipShape", user_ucn, population)

    assert abs(actual_rr - expected_rr) < 5.0  # Within 5% tolerance


def test_container_rr_aggregation():
    """Test container RR from trait RRs."""
    trait_data = {
        "PaDNA.HairDNA.Color": {"ucn": 950, "rr": 85.0},
        "PaDNA.EyeDNA.IrisColor": {"ucn": 600, "rr": 30.0},
    }

    # Weighted average: (85*950 + 30*600) / (950+600) = 64.5
    expected_rr = 64.5

    actual_rr = calculate_container_rr("test_user", "PaDNA", trait_data)

    assert abs(actual_rr - expected_rr) < 0.1
```

### Integration Tests
```python
def test_holistic_review_rr_update():
    """Test holistic review recalculates RR correctly."""
    user_id = "integration_test_user"

    # Setup: User with traits
    create_test_user(user_id, traits={
        "PaDNA.HairDNA.Color": {"ucn": 950, "rr": None}
    })

    # Run holistic review
    run_holistic_review(user_id)

    # Verify: RR is 0-100 percentile
    trait = get_user_trait(user_id, "PaDNA.HairDNA.Color")
    assert 0 <= trait["rr"] <= 100
    assert trait["curiosity"] == 100 - trait["rr"]
```

### End-to-End Tests
```python
def test_user_sees_correct_rr_in_ui():
    """Test user sees correct multi-level RR in UI."""
    user_id = "e2e_test_user"

    # Setup: User with multiple traits across containers
    setup_test_user_with_traits(user_id)

    # API call: GET /ui/unabridged?user_id=e2e_test_user
    response = api_client.get(f"/ui/unabridged?user_id={user_id}")

    # Verify trait-level RR
    padna_trait = next(t for t in response["traits"] if t["trait_id"] == "PaDNA.HairDNA.Color")
    assert 0 <= padna_trait["rr"] <= 100

    # Verify container-level RR
    assert "rr_by_container" in response["profile"]
    assert 0 <= response["profile"]["rr_by_container"]["PaDNA"]["rr"] <= 100

    # Verify overall RR
    assert 0 <= response["profile"]["rr"] <= 100
```

## UI Display Requirements

### Trait Level (Unabridged Panel)
```
PaDNA.HairDNA.Color: "Blonde"
  UCN: 950  |  RR: 85  |  Curiosity: 15%
  (More refined than 85% of users for this trait)
```

### Container Level (RR by DNA Panel)
```
👤 Physical Appearance (PaDNA)
   109 traits
   RR: 72.3 (Well-Refined)
   Curiosity: 27.7%
```

### Overall Level (Profile Header)
```
BSTest
Overall RR: 64.5 (Developing)
More refined than 64% of users
```

## Related Documentation

- [CRITICAL_DATA_FLOW_ARCHITECTURE.md](./CRITICAL_DATA_FLOW_ARCHITECTURE.md) - How data flows through system
- [RR_BASELINE_REQUIREMENT.md](./RR_BASELINE_REQUIREMENT.md) - Need for fictionalized user baseline
- [HOLISTIC_REVIEW_BUG_FIX.md](./HOLISTIC_REVIEW_BUG_FIX.md) - Previous RR display issues

## Frequently Asked Questions

### Q: Why not just use UCN directly?
**A**: UCN is absolute confidence (0-1000), RR is relative refinement (percentile). RR is more meaningful to users ("You're in the top 15%") than raw UCN ("Your UCN is 850").

### Q: What if there's only 1 user with a trait?
**A**: Use fictionalized user baseline (see RR_BASELINE_REQUIREMENT.md) to ensure statistical validity even with small populations.

### Q: How does curiosity drive system behavior?
**A**: High curiosity (low RR) traits trigger:
- Core autonomous research (analyze old data)
- Head Coach conversation planning (ask about this trait)
- Photo Coach analysis (re-examine photos for this trait)
- Explorer priority (gather more evidence for this trait)

### Q: Should container RR be average or weighted average?
**A**: Weighted average by UCN. A trait with UCN 950 (high confidence) should contribute more to container RR than a trait with UCN 200 (low confidence).

### Q: How does overall RR relate to feature access?
**A**: Future feature gating:
- RR 50+: Access to advanced AI features
- RR 70+: Priority support, premium coaches
- RR 90+: Elite features, early access to new tools

---

**Last Updated**: 2025-10-06
**Status**: 🔴 Architecture design phase - implementation pending
**Blocking Issue**: Current holistic review uses wrong RR calculator
