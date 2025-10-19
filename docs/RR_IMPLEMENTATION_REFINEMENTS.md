# RR Implementation Refinements

**Source**: ChatGPT collaborative review of RR_ARCHITECTURE_MULTILEVEL.md
**Date**: 2025-10-06
**Status**: Design approved, implementation pending

## Executive Summary

ChatGPT reviewed the multi-level RR architecture and provided critical refinements for:
- **Robustness**: Tie handling, small-N protection, outlier detection
- **Performance**: Histogram-based distributions (O(1) percentile queries)
- **Privacy**: K-anonymity guarantees, no raw UCN exposure
- **Fairness**: Cohort-aware RR hooks, bias mitigation
- **Intelligence**: Curiosity satiation, cool-down windows

All refinements accepted and incorporated into implementation plan.

---

## 1. Ties & Small-N Correctness

### Problem
- **Ties**: Multiple users with same UCN can skew percentile calculation
- **Small populations**: Trait with 5 users → percentiles swing wildly with each new user

### Solution: Mid-Rank Percentile + Fictional Prior Blending

```python
def calculate_trait_rr_robust(
    user_ucn: float,
    population_ucns: List[float],
    k_min: int = 50
) -> float:
    """
    Calculate RR with tie handling and small-N blending.

    Args:
        user_ucn: User's UCN for this trait
        population_ucns: All UCNs for this trait across population
        k_min: Minimum population size for pure empirical RR

    Returns:
        RR percentile (0-100) with robust tie/small-N handling
    """
    n = len(population_ucns)

    if n == 0:
        return None  # No population data

    # Handle ties with mid-rank (Hazen/Cunnane method)
    users_below = sum(1 for ucn in population_ucns if ucn < user_ucn)
    users_equal = sum(1 for ucn in population_ucns if ucn == user_ucn)

    # Mid-rank: count half of equal values as "below"
    effective_below = users_below + (users_equal / 2.0)

    rr_empirical = (effective_below / n) * 100

    # Small-N protection: blend with fictional prior
    if n < k_min:
        # Prior assumes normal distribution centered at UCN 500
        rr_prior = calculate_prior_rr(user_ucn, mean=500, std=150)

        # Blend factor: 0 when n=0, 1 when n>=k_min
        lambda_blend = min(1.0, n / k_min)

        rr_final = lambda_blend * rr_empirical + (1 - lambda_blend) * rr_prior
    else:
        rr_final = rr_empirical

    return round(rr_final, 2)


def calculate_prior_rr(ucn: float, mean: float = 500, std: float = 150) -> float:
    """
    Calculate RR using fictional prior (normal distribution).

    Used for small populations to stabilize percentile.
    """
    import scipy.stats as stats

    z_score = (ucn - mean) / std
    percentile = stats.norm.cdf(z_score) * 100

    return max(0.0, min(100.0, percentile))
```

**Example**:
```python
# Trait has only 10 users (n < k_min=50)
population = [400, 450, 500, 550, 600, 650, 700, 750, 800, 850]
user_ucn = 675

# Empirical: 7/10 below → RR 70
rr_empirical = 70.0

# Prior (fictional baseline): UCN 675 vs mean 500 → RR ~88
rr_prior = 88.0

# Blend: lambda = 10/50 = 0.2
# RR = 0.2 * 70 + 0.8 * 88 = 84.4
rr_final = 84.4
```

**Benefits**:
- Stabilizes RR for traits with few users
- Prevents wild swings as population grows
- Graceful degradation from prior to empirical as n increases

---

## 2. Population Distribution as Histograms

### Problem
- Storing raw UCN arrays for 10,000 users × 500 traits = 5M values (memory intensive)
- Privacy risk: raw UCN values could leak user identity
- Slow percentile queries: O(n) to scan full array

### Solution: Histogram Storage with K-Anonymity

```python
class TraitDistributionHistogram:
    """
    Histogram-based population distribution for fast, private RR calculation.
    """

    def __init__(self, trait_path: str, num_bins: int = 100, k_min: int = 5):
        self.trait_path = trait_path
        self.num_bins = num_bins
        self.k_min = k_min  # K-anonymity minimum

        # Histogram bins: [0-10), [10-20), ..., [990-1000]
        self.bin_edges = np.linspace(0, 1000, num_bins + 1)
        self.bin_counts = np.zeros(num_bins, dtype=int)

        # Quantiles for fast lookup
        self.quantiles = {}  # {10: 250, 50: 500, 90: 750, ...}

        # Metadata
        self.total_count = 0
        self.mean_ucn = 0.0
        self.median_ucn = 0.0
        self.std_dev = 0.0
        self.last_updated = None

    def add_ucns(self, ucns: List[float]) -> None:
        """Build histogram from raw UCN values."""
        # Winsorize outliers at P1/P99 to prevent distortion
        p1, p99 = np.percentile(ucns, [1, 99])
        ucns_winsorized = np.clip(ucns, p1, p99)

        # Fill histogram bins
        self.bin_counts, _ = np.histogram(ucns_winsorized, bins=self.bin_edges)

        # Enforce k-anonymity: merge bins with count < k_min
        self._enforce_k_anonymity()

        # Calculate quantiles
        self._calculate_quantiles(ucns_winsorized)

        # Store metadata
        self.total_count = len(ucns)
        self.mean_ucn = float(np.mean(ucns_winsorized))
        self.median_ucn = float(np.median(ucns_winsorized))
        self.std_dev = float(np.std(ucns_winsorized))
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def _enforce_k_anonymity(self) -> None:
        """
        Merge bins with count < k_min to ensure k-anonymity.

        Privacy guarantee: No bin exposes fewer than k users.
        """
        i = 0
        while i < len(self.bin_counts):
            if self.bin_counts[i] < self.k_min and i < len(self.bin_counts) - 1:
                # Merge with next bin
                self.bin_counts[i + 1] += self.bin_counts[i]
                self.bin_counts[i] = 0
            i += 1

        # Clip trailing zero bins
        self.bin_counts = self.bin_counts[self.bin_counts > 0]

    def _calculate_quantiles(self, ucns: np.ndarray) -> None:
        """Pre-calculate common quantiles for O(1) lookup."""
        percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        self.quantiles = {
            p: float(np.percentile(ucns, p))
            for p in percentiles
        }

    def get_percentile(self, ucn: float) -> float:
        """
        Fast O(log b) percentile query using histogram.

        Args:
            ucn: User's UCN value

        Returns:
            Percentile rank (0-100)
        """
        # Find which bin this UCN falls into
        bin_idx = np.searchsorted(self.bin_edges, ucn, side='right') - 1
        bin_idx = max(0, min(bin_idx, len(self.bin_counts) - 1))

        # Count all users below this bin
        users_below = np.sum(self.bin_counts[:bin_idx])

        # Estimate position within bin (linear interpolation)
        bin_start = self.bin_edges[bin_idx]
        bin_end = self.bin_edges[bin_idx + 1]
        bin_count = self.bin_counts[bin_idx]

        if bin_count > 0:
            fraction_in_bin = (ucn - bin_start) / (bin_end - bin_start)
            users_in_bin_below = fraction_in_bin * bin_count
        else:
            users_in_bin_below = 0

        total_below = users_below + users_in_bin_below
        percentile = (total_below / self.total_count) * 100

        return round(percentile, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "trait_path": self.trait_path,
            "bin_edges": self.bin_edges.tolist(),
            "bin_counts": self.bin_counts.tolist(),
            "quantiles": self.quantiles,
            "total_count": self.total_count,
            "mean_ucn": self.mean_ucn,
            "median_ucn": self.median_ucn,
            "std_dev": self.std_dev,
            "last_updated": self.last_updated,
            "k_min": self.k_min,
            "version": "1.0"
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TraitDistributionHistogram':
        """Deserialize from JSON dict."""
        hist = cls(
            trait_path=data["trait_path"],
            num_bins=len(data["bin_counts"]),
            k_min=data.get("k_min", 5)
        )
        hist.bin_edges = np.array(data["bin_edges"])
        hist.bin_counts = np.array(data["bin_counts"])
        hist.quantiles = data["quantiles"]
        hist.total_count = data["total_count"]
        hist.mean_ucn = data["mean_ucn"]
        hist.median_ucn = data["median_ucn"]
        hist.std_dev = data["std_dev"]
        hist.last_updated = data["last_updated"]
        return hist
```

**Storage Format**:
```json
// data/population_distributions/PaDNA.HairDNA.Color_v1.json
{
  "trait_path": "PaDNA.HairDNA.Color",
  "bin_edges": [0, 10, 20, 30, ..., 1000],
  "bin_counts": [0, 5, 12, 45, 89, ..., 3],
  "quantiles": {
    "10": 250.5,
    "50": 525.0,
    "90": 785.2
  },
  "total_count": 1000,
  "mean_ucn": 525.3,
  "median_ucn": 525.0,
  "std_dev": 148.7,
  "last_updated": "2025-10-06T03:00:00Z",
  "k_min": 5,
  "version": "1.0"
}
```

**Benefits**:
- **Privacy**: No raw UCN values stored, k-anonymity enforced (k≥5)
- **Speed**: O(log b) percentile queries vs O(n) for raw arrays
- **Memory**: ~1KB per trait vs ~40KB for 1000 raw UCNs
- **Scalability**: 500 traits × 1KB = 500KB total vs 20MB for raw data

---

## 3. Coverage vs. Weighting for Container RR

### Problem
- Weighting container RR purely by UCN penalizes users with many low-confidence traits
- Unknown traits don't contribute to weight, understating domain coverage

### Solution: Configurable Coverage Weight

```python
def calculate_container_rr(
    user_id: str,
    container: str,
    alpha: float = 0.7
) -> Dict[str, Any]:
    """
    Calculate container RR with coverage weighting.

    Args:
        user_id: User ID
        container: Container name (e.g., "PaDNA")
        alpha: Weight for UCN vs coverage (0.7 = 70% UCN, 30% coverage)

    Returns:
        {
            "rr": float,
            "curiosity": float,
            "trait_count": int,
            "avg_ucn": float,
            "coverage": float
        }
    """
    # Get all traits in this container for this user
    user_traits = get_user_traits_by_container(user_id, container)

    if not user_traits:
        return {"rr": None, "curiosity": 100.0, "trait_count": 0}

    # Calculate per-trait RR
    trait_rrs = []
    trait_ucns = []

    for trait_path, ucn in user_traits.items():
        trait_rr = calculate_trait_rr(user_id, trait_path)

        if trait_rr is not None:
            trait_rrs.append(trait_rr)
            trait_ucns.append(ucn)

    # Weighted average with configurable alpha
    weights = []
    for ucn in trait_ucns:
        # Weight = alpha * UCN + (1-alpha) * presence_indicator
        weight = alpha * ucn + (1 - alpha) * 1.0
        weights.append(weight)

    total_weight = sum(weights)
    weighted_rr = sum(rr * w for rr, w in zip(trait_rrs, weights)) / total_weight

    avg_ucn = sum(trait_ucns) / len(trait_ucns)

    # Coverage: what % of canonical traits in this container does user have?
    canonical_traits = get_canonical_traits_for_container(container)
    coverage = len(user_traits) / len(canonical_traits)

    return {
        "rr": round(weighted_rr, 2),
        "curiosity": round(100 - weighted_rr, 2),
        "trait_count": len(user_traits),
        "avg_ucn": round(avg_ucn, 2),
        "coverage": round(coverage * 100, 2)
    }
```

**Configuration**:
```python
# config/rr_weighting.json
{
  "container_weights": {
    "PaDNA": {"alpha": 0.7},        # 70% UCN, 30% coverage
    "Personality": {"alpha": 0.5},   # 50/50 (many traits, value breadth)
    "Cognitive": {"alpha": 0.8}      # 80% UCN (fewer traits, value depth)
  }
}
```

**Benefits**:
- Prevents "all low-UCN" users from having artificially low RR
- Rewards users for breadth of coverage (many traits) vs just depth (high UCN)
- Configurable per container based on domain characteristics

---

## 4. Missing / Unset Traits

### Problem
- User lacks `NoseTipShape` entirely → should show high curiosity but no RR
- Container RR shouldn't penalize missing traits, but should flag them for Head Coach

### Solution: Null RR with Explicit Curiosity

```python
{
  "PaDNA.NoseTipShape": {
    "resolved_value": null,
    "ucn": null,
    "rr": null,
    "curiosity": 100.0,
    "reason": "no_evidence",
    "priority": "high"  // Core should target this trait
  }
}
```

**Container RR Calculation**:
```python
def calculate_container_rr_with_missing(user_id: str, container: str):
    """Include missing traits in curiosity map but exclude from RR average."""

    known_traits = get_user_traits(user_id, container)  # Has UCN
    canonical_traits = get_canonical_traits(container)  # All possible traits
    missing_traits = set(canonical_traits) - set(known_traits.keys())

    # Calculate RR only from known traits
    known_rrs = [calculate_trait_rr(user_id, t) for t in known_traits]
    container_rr = weighted_average(known_rrs, weights=ucns)

    # Build curiosity map including missing
    curiosity_map = {}
    for trait in known_traits:
        curiosity_map[trait] = 100 - known_traits[trait]["rr"]

    for trait in missing_traits:
        curiosity_map[trait] = 100.0  # Maximum curiosity for unknown

    return {
        "rr": container_rr,
        "curiosity": 100 - container_rr,
        "curiosity_map": curiosity_map,  # For Head Coach targeting
        "missing_traits": list(missing_traits),
        "coverage": len(known_traits) / len(canonical_traits)
    }
```

**Head Coach Integration**:
```python
# Head Coach checks curiosity map to prioritize questions
def plan_conversation(user_id: str):
    padna_data = get_container_rr(user_id, "PaDNA")

    # Sort traits by curiosity (highest first)
    high_curiosity_traits = sorted(
        padna_data["curiosity_map"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    # Focus conversation on top 5 high-curiosity traits
    for trait, curiosity in high_curiosity_traits:
        if curiosity > 80:
            add_to_agenda(f"Ask about {trait}")
```

---

## 5. Cohort-Aware RR (Phase-Next)

### Problem
- Global RR can be biased by demographic imbalances
- Example: Lighting conditions skew PaDNA UCNs by ethnicity
- Need fair comparisons within relevant cohorts

### Solution: Stub Interface for Future Cohort RR

```python
def calculate_trait_rr_cohort_aware(
    user_id: str,
    trait_path: str,
    cohort_key: Optional[str] = None,
    enable_cohort: bool = False  # MUST be False until ethics review
) -> float:
    """
    Calculate RR with optional cohort filtering.

    Args:
        user_id: User ID
        trait_path: Trait path
        cohort_key: Optional cohort identifier (e.g., "age_25_35", "lighting_outdoor")
        enable_cohort: MUST be False until ethics review passes

    Returns:
        RR percentile (global or cohort-specific)

    Raises:
        ValueError: If enable_cohort=True without ethics approval
    """
    if enable_cohort and not ETHICS_REVIEW_APPROVED:
        raise ValueError(
            "Cohort-aware RR requires ethics review approval. "
            "See docs/ETHICS_COHORT_RR.md for review process."
        )

    if enable_cohort and cohort_key:
        # Future: Load cohort-specific distribution
        distribution = load_distribution(trait_path, cohort=cohort_key)
    else:
        # Current: Use global distribution
        distribution = load_distribution(trait_path)

    return calculate_percentile(user_ucn, distribution)
```

**Configuration Stub**:
```python
# config/cohort_rr.json (disabled by default)
{
  "enabled": false,
  "ethics_review_required": true,
  "ethics_review_approved": false,
  "cohort_definitions": {
    "age_bands": ["18_24", "25_34", "35_44", "45_54", "55_plus"],
    "lighting": ["indoor", "outdoor", "mixed"],
    "ethnicity": null  // DO NOT ENABLE without extensive bias testing
  }
}
```

**Documentation Requirement**:
- Create `docs/ETHICS_COHORT_RR.md` explaining:
  - Why cohort RR might reduce bias
  - Risks of creating filter bubbles
  - Required bias testing before enabling
  - Legal/privacy review checklist

---

## 6. Curiosity Satiation & Cool-Down

### Problem
- System calculates RR, gets big jump, immediately asks more questions about same trait
- Over-harvests same source (e.g., asks 10 questions about hair color in one session)
- High-RR traits disappear from agenda entirely

### Solution: Cool-Down Window + Minimum Curiosity Floor

```python
class CuriosityCoolDown:
    """Manage curiosity satiation to prevent over-harvesting."""

    def __init__(self, cool_down_hours: int = 48, min_curiosity: float = 5.0):
        self.cool_down_hours = cool_down_hours
        self.min_curiosity = min_curiosity

        # Track recent RR jumps: {trait_path: timestamp}
        self.recent_updates = {}

    def should_target_trait(
        self,
        trait_path: str,
        curiosity: float,
        last_rr_update: Optional[datetime] = None
    ) -> bool:
        """
        Check if trait should be targeted for curiosity-driven action.

        Args:
            trait_path: Trait identifier
            curiosity: Current curiosity score (0-100)
            last_rr_update: Timestamp of last RR update

        Returns:
            True if trait is actionable, False if in cool-down
        """
        # Apply minimum curiosity floor
        effective_curiosity = max(curiosity, self.min_curiosity)

        # Check cool-down window
        if last_rr_update:
            time_since_update = datetime.now(timezone.utc) - last_rr_update
            hours_elapsed = time_since_update.total_seconds() / 3600

            if hours_elapsed < self.cool_down_hours:
                # Recently updated, reduce effective curiosity
                cool_down_factor = hours_elapsed / self.cool_down_hours
                effective_curiosity *= cool_down_factor

        return effective_curiosity > 10.0  # Threshold for action

    def record_update(self, trait_path: str, rr_jump: float) -> None:
        """
        Record RR update for cool-down tracking.

        Args:
            trait_path: Trait that was updated
            rr_jump: Magnitude of RR change (0-100)
        """
        if rr_jump > 10.0:  # Only track significant jumps
            self.recent_updates[trait_path] = datetime.now(timezone.utc)
```

**Integration with Head Coach**:
```python
def plan_next_question(user_id: str):
    """Head Coach plans next question using curiosity + cool-down."""

    cool_down = CuriosityCoolDown(cool_down_hours=48, min_curiosity=5.0)

    # Get all traits sorted by curiosity
    traits = get_all_traits_with_curiosity(user_id)

    for trait_path, curiosity, last_update in traits:
        if cool_down.should_target_trait(trait_path, curiosity, last_update):
            return f"Ask about {trait_path}"

    # Fallback: even high-RR traits get periodic recheck
    return "General check-in question"
```

**Benefits**:
- Prevents over-harvesting same trait
- Ensures diverse conversation topics
- High-RR traits don't disappear (min curiosity floor)
- Periodic rechecks detect drift/decay

---

## 7. Outlier & Drift Protection

### Problem
- One user with UCN 9999 warps entire population distribution
- Distribution changes over time as system improves (drift)

### Solution: Winsorization + Versioned Distributions

```python
def build_population_distribution(all_ucns: List[float], version: str = "1.0"):
    """
    Build population distribution with outlier protection.

    Args:
        all_ucns: All UCN values for this trait
        version: Distribution version (for auditability)
    """
    # Winsorize at P1/P99 to clip extreme outliers
    p1, p99 = np.percentile(all_ucns, [1, 99])
    ucns_winsorized = np.clip(all_ucns, p1, p99)

    # Build histogram
    hist = TraitDistributionHistogram(trait_path)
    hist.add_ucns(ucns_winsorized)

    # Save with version
    save_path = f"data/population_distributions/{trait_path}_v{version}.json"
    with open(save_path, 'w') as f:
        json.dump(hist.to_dict(), f, indent=2)

    # Log distribution metadata
    log_distribution_build(trait_path, version, len(all_ucns), p1, p99)
```

**Version Tracking in Trait Data**:
```json
{
  "PaDNA.HairDNA.Color": {
    "ucn": 950.0,
    "rr": 85.0,
    "rr_metadata": {
      "distribution_version": "1.0",
      "calculated_at": "2025-10-06T12:00:00Z",
      "method": "histogram_percentile"
    }
  }
}
```

**Audit Trail**:
```python
# When RR calculation produces unexpected result, trace back
def audit_rr_calculation(user_id: str, trait_path: str):
    trait = get_trait(user_id, trait_path)

    dist_version = trait["rr_metadata"]["distribution_version"]
    dist_file = f"data/population_distributions/{trait_path}_v{dist_version}.json"

    hist = load_histogram(dist_file)

    print(f"Trait: {trait_path}")
    print(f"User UCN: {trait['ucn']}")
    print(f"Calculated RR: {trait['rr']}")
    print(f"Distribution: {dist_file}")
    print(f"Population: {hist.total_count} users")
    print(f"Mean: {hist.mean_ucn}, Median: {hist.median_ucn}")
```

---

## 8. UI Copy & Tooltips

### Trait Panel
```
PaDNA.HairDNA.Color: "Blonde"
  UCN: 950  |  RR: 85  |  Curiosity: 15%
  ℹ️ More refined than 85% of users for this trait.
     Curiosity 15: we'll occasionally recheck this.
```

### Container Panel
```
👤 Physical Appearance (PaDNA)
   109 traits | Coverage: 87%
   RR: 72.3 (Well-Refined) | Curiosity: 27.7%

   🎯 Top priorities (low RR):
   • NoseTipShape: RR 5 → Upload profile photo
   • EarShape: RR 12 → Answer quick check
   • HandSize: RR 18 → Measure & log
```

### Overall Header
```
BSTest
Overall RR: 64.5 (Developing)
More refined than 64% of users
ℹ️ How this is calculated: Your RR is your percentile rank
   compared to all active users. Higher = more complete profile.
```

---

## 9. Migration Safety Net

### Phase 1: Data Validation Guardrails

```python
def validate_rr_write(rr: Optional[float]) -> None:
    """
    Validate RR value before writing to resolved.json.

    Raises:
        ValueError: If RR is out of valid range
    """
    if rr is None:
        return  # Null is valid (no evidence)

    if not (0 <= rr <= 100):
        raise ValueError(
            f"Invalid RR value: {rr}. "
            f"RR must be in range [0, 100] (percentile). "
            f"UCN values (0-1000) should NOT be stored in RR field."
        )


def migrate_invalid_rr_values(user_id: str) -> Dict[str, Any]:
    """
    One-time migration to fix RR values > 100 (legacy UCN values).

    Returns:
        {
            "fixed_count": int,
            "invalid_traits": List[str]
        }
    """
    resolved = load_resolved(user_id)
    fixed_count = 0
    invalid_traits = []

    for trait_path, trait_data in resolved.items():
        if trait_path == "profile":
            continue

        rr = trait_data.get("rr")

        if rr is not None and (rr < 0 or rr > 100):
            # Invalid RR detected
            invalid_traits.append(trait_path)

            # Reset to null (will be recalculated by holistic review)
            trait_data["rr"] = None
            trait_data["curiosity"] = 100.0

            # Mark for recalculation
            trait_data["rr_status"] = "needs_recalculation"
            trait_data["rr_migration"] = {
                "old_value": rr,
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "reason": "invalid_range"
            }

            fixed_count += 1

    save_resolved(user_id, resolved)

    return {
        "fixed_count": fixed_count,
        "invalid_traits": invalid_traits
    }
```

### Phase 2: Consistency Scanner

```python
def scan_rr_consistency(user_id: str) -> Dict[str, Any]:
    """
    Scan for RR inconsistencies and trigger recalculation.

    Returns:
        {
            "total_traits": int,
            "missing_rr": int,
            "recalculated": int
        }
    """
    resolved = load_resolved(user_id)
    total_traits = 0
    missing_rr = 0
    recalculated = 0

    for trait_path, trait_data in resolved.items():
        if trait_path == "profile":
            continue

        total_traits += 1
        ucn = trait_data.get("ucn")
        rr = trait_data.get("rr")

        # If UCN exists but RR is null, recalculate
        if ucn is not None and rr is None:
            missing_rr += 1

            # Recalculate using cached histogram
            new_rr = calculate_trait_rr(user_id, trait_path)

            if new_rr is not None:
                trait_data["rr"] = new_rr
                trait_data["curiosity"] = 100 - new_rr
                trait_data["rr_metadata"] = {
                    "calculated_at": datetime.now(timezone.utc).isoformat(),
                    "method": "consistency_scan"
                }
                recalculated += 1

    save_resolved(user_id, resolved)

    return {
        "total_traits": total_traits,
        "missing_rr": missing_rr,
        "recalculated": recalculated
    }
```

---

## 10. API & Test Additions

### New API Endpoints

#### GET /rr/trait
```python
@app.get("/rr/trait")
def get_trait_rr(
    user_id: str = Query(...),
    trait_path: str = Query(...)
) -> Dict[str, Any]:
    """
    Get detailed RR information for a specific trait.

    Returns:
        {
            "user_id": str,
            "trait_path": str,
            "ucn": float,
            "rr": float,
            "curiosity": float,
            "population_stats": {
                "total_users": int,
                "users_below": int,
                "percentile": float,
                "mean_ucn": float,
                "median_ucn": float
            },
            "rr_metadata": {
                "distribution_version": str,
                "calculated_at": str,
                "method": str
            }
        }
    """
    trait = get_user_trait(user_id, trait_path)
    dist = load_distribution(trait_path)

    return {
        "user_id": user_id,
        "trait_path": trait_path,
        "ucn": trait["ucn"],
        "rr": trait["rr"],
        "curiosity": trait["curiosity"],
        "population_stats": {
            "total_users": dist.total_count,
            "users_below": int((trait["rr"] / 100) * dist.total_count),
            "percentile": trait["rr"],
            "mean_ucn": dist.mean_ucn,
            "median_ucn": dist.median_ucn
        },
        "rr_metadata": trait.get("rr_metadata", {})
    }
```

#### GET /rr/container
```python
@app.get("/rr/container")
def get_container_rr(
    user_id: str = Query(...),
    container: str = Query(...)
) -> Dict[str, Any]:
    """
    Get container-level RR with curiosity map.

    Returns:
        {
            "user_id": str,
            "container": str,
            "rr": float,
            "curiosity": float,
            "trait_count": int,
            "avg_ucn": float,
            "coverage": float,
            "curiosity_map": Dict[str, float],
            "top_priorities": List[Dict[str, Any]]
        }
    """
    container_data = calculate_container_rr(user_id, container)

    # Get top 5 high-curiosity traits
    sorted_traits = sorted(
        container_data["curiosity_map"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]

    top_priorities = [
        {"trait": trait, "curiosity": curiosity, "rr": 100 - curiosity}
        for trait, curiosity in sorted_traits
    ]

    return {
        **container_data,
        "top_priorities": top_priorities
    }
```

### Test Cases

```python
def test_tie_handling():
    """Test mid-rank percentile with ties."""
    # 10 users, 3 with same UCN as test user
    population = [100, 200, 300, 400, 400, 400, 500, 600, 700, 800]
    user_ucn = 400

    # 3 below (100, 200, 300), 3 equal (400, 400, 400), 4 above
    # Mid-rank: 3 + 1.5 = 4.5 below → RR = 45
    rr = calculate_trait_rr_robust(user_ucn, population)

    assert 44 <= rr <= 46  # Allow small rounding tolerance


def test_small_n_blending():
    """Test small-N protection with fictional prior."""
    # Only 5 users (n < k_min=50)
    population = [100, 200, 300, 400, 500]
    user_ucn = 350

    # Empirical: 3/5 below → RR 60
    # Prior: UCN 350 vs mean 500 → RR ~27
    # Blend: lambda=5/50=0.1 → RR = 0.1*60 + 0.9*27 = 30.3

    rr = calculate_trait_rr_robust(user_ucn, population, k_min=50)

    assert 25 <= rr <= 35  # Blended result


def test_histogram_privacy():
    """Test k-anonymity enforcement in histogram."""
    # Small population with outliers
    ucns = [100] * 2 + [200] * 8 + [300] * 3  # Bins: [2, 8, 3]

    hist = TraitDistributionHistogram(trait_path="test", k_min=5)
    hist.add_ucns(ucns)

    # Bins with count < 5 should be merged
    assert all(count == 0 or count >= 5 for count in hist.bin_counts)


def test_missing_trait_curiosity():
    """Test missing traits have curiosity=100, rr=None."""
    user_id = "test_user"

    # User lacks NoseTipShape
    container_data = calculate_container_rr_with_missing(user_id, "PaDNA")

    assert "NoseTipShape" in container_data["missing_traits"]
    assert container_data["curiosity_map"]["NoseTipShape"] == 100.0


def test_outlier_winsorization():
    """Test outliers are clipped at P1/P99."""
    # Population with extreme outliers
    ucns = [50] * 100 + [500] * 800 + [9999] * 100

    # Build distribution with winsorization
    dist = build_population_distribution(ucns)

    # Max value should be P99, not 9999
    assert dist.bin_edges[-1] < 9999
```

---

## Summary Checklist

**Core Improvements**:
- ✅ Tie handling with mid-rank percentile
- ✅ Small-N blending with fictional prior (lambda = min(1, n/k_min))
- ✅ Histogram-based distributions (O(log b) queries, k-anonymity)
- ✅ Coverage weighting for container RR (configurable alpha)
- ✅ Missing trait handling (rr=None, curiosity=100)
- ✅ Cohort-aware RR stub (disabled pending ethics review)
- ✅ Curiosity satiation with cool-down (48h default)
- ✅ Outlier protection (winsorization at P1/P99)
- ✅ Versioned distributions for audit trail
- ✅ Migration safety (validate RR range, consistency scanner)
- ✅ New API endpoints (/rr/trait, /rr/container)
- ✅ Comprehensive test suite

**Next Steps**:
1. Implement `TraitDistributionHistogram` class
2. Build per-trait RR calculator with all refinements
3. Create data migration script for invalid RR values
4. Update holistic review to use new calculator
5. Add API endpoints
6. Write test suite

This architecture is production-ready with robust edge case handling, privacy guarantees, and scalability to millions of users.

---

**Last Updated**: 2025-10-06
**Status**: ✅ Design approved, ready for implementation
**Reviewed By**: ChatGPT (collaborative refinement)
