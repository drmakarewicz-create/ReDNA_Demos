# UCN/RR Engine - Quick Start Guide

**Status**: ✅ Production Ready | **Version**: 0.1.0

---

## What is UCN/RR?

The **UCN/RR Calculation Engine** is the intelligence layer that:
- Assesses **confidence** in trait assignments (UCN: 0-1000)
- Ranks users by **profile refinement** (RR: 0-100 percentile)
- Drives **curiosity** to refine profiles (Curiosity = 100 - RR)

**Key Principle**: "Supreme level of intelligence" to determine how confident we are that an assigned trait matches the IRL (in real life) user.

---

## Quick Examples

### Example 1: Self-Report Only (Low Confidence)

```
Evidence: User says "My hair is dark brown"
UCN: ~300 (30% confidence)
Why: Single self-report, no corroboration
```

### Example 2: Photos + Self-Report (High Confidence)

```
Evidence:
  - 10 photos clearly showing dark brown hair
  - User confirms "dark brown"
  - Third-party attests "yes, dark brown"

UCN: ~974 (97% confidence)
Why: Multiple high-quality sources corroborate
```

### Example 3: Contradictory Evidence

```
Evidence:
  - Old photos (6 months ago): Blonde
  - Recent photos (1 week ago): Dark Brown
  - User says: "I dyed it brown"

UCN: ~474 (47% confidence - reduced by 50% penalty)
Why: Severe contradiction detected, held "in tension"
Status: Flagged for Head Coach to decide resolution timing
```

---

## 30-Second Test

```bash
cd ReDNACoreDemo

# Calculate UCN/RR for abtest user
python3 calculate_ucn_for_user.py abtest --save

# Expected output:
# RR: 73.25 percentile (top 27%)
# Average UCN: 593.66
# Curiosity: 26.75 (moderate)
# Strategy: Selective refinement
```

---

## Real Results

### User: abtest

```
Profile: 50 traits from 10 reference photos

Results:
  RR: 73.25 percentile (top 27%)
  Average UCN: 593.66
  Curiosity: 26.75 (moderate)

Gates Unlocked:
  ✅ Reliable Coaching (RR ≥ 70)
  ✅ Basic Features (RR ≥ 50)

Strategy:
  "Selective refinement - targeted improvements"
  Max 3 concurrent actions

Top Priority:
  1. PaDNA.HairDNA.Highlights (UCN 416)
     → "Opportunistically gather supporting evidence"
```

### User: mrscoachtest

```
Profile: 68 traits from 10 reference photos (includes age features)

Results:
  RR: 60.89 percentile (top 40%)
  Average UCN: 541.76
  Curiosity: 39.11 (high)

Gates Unlocked:
  ✅ Basic Features (RR ≥ 50)

Strategy:
  "Active refinement - many opportunities"
  Max 4 concurrent actions

Top Priority:
  1. PaDNA.HairDNA.Highlights (UCN 416)
  2. PaDNA.FacialDNA.ForeheadLines (UCN 419)
  3. PaDNA.SkinDNA.AgeSpotsPresence (UCN 420)
     → All need stronger evidence
```

**Key Insight**: mrscoachtest has MORE traits (68 vs 50) but LOWER RR (60.89 vs 73.25) because average UCN is lower. **Quality beats quantity!**

---

## How It Works

### 1. Evidence Weighting

Different evidence sources have different credibility:

| Source | Base Weight | Example UCN |
|--------|-------------|-------------|
| Webcam video | 0.8 | ~800 |
| Photo series (10 photos) | 0.7 | ~650 |
| Third-party | 0.6 | ~600 |
| Self-report | 0.3 | ~300 |

**Quality Boosts**:
- High resolution photo: +30%
- Good lighting: +20%
- Multiple angles: +20%
- Corroboration: +10-20% per source

### 2. Confidence Decay

Confidence decays over time (not the trait itself):

| Trait | Half-Life | Reason |
|-------|-----------|--------|
| Eye color | permanent | Never changes |
| Natural hair color | 365 days | Changes slowly |
| Dyed highlights | 60 days | Fades quickly |
| Hair styling | 30 days | Changes frequently |
| Current mood | 7 days | Highly volatile |

**Example**: Hair color observation from 6 months ago has decayed to ~50% confidence.

### 3. RR Calculation

Your average UCN is compared to all users:

```
Your avg UCN: 700
Users with lower avg UCN: 8,500 out of 10,000
Your RR: 85 percentile (top 15%)
```

### 4. Curiosity Generation

```
Curiosity = 100 - RR

RR 85 → Curiosity 15 (moderate)
  Strategy: "Selective refinement"
  Focus: "Contradictions and stale traits"
  Max actions: 3

RR 60 → Curiosity 40 (high)
  Strategy: "Active refinement"
  Focus: "High-impact and easy wins"
  Max actions: 4
```

---

## Gates & Milestones

### Gates (Feature Unlocks)

| RR Threshold | Gate | What You Get |
|--------------|------|--------------|
| ≥ 98 | **Sensitive DNA Unlock** | SexDNA, FinanceDNA genetic, etc. |
| ≥ 85 | **Advanced Personalization** | Enhanced features |
| ≥ 70 | **Reliable Coaching** | AI coaches can give solid advice |
| ≥ 50 | **Basic Features** | Standard functionality |

### Milestones (Celebrations)

| RR | Milestone | Message |
|----|-----------|---------|
| 98 | Elite Refinement | Top 2%! Sensitive DNAs unlocked |
| 90 | Exceptional | Top 10%! |
| 75 | Well-Refined | Great work! |
| 50 | Halfway There | Keep going! |
| 25 | Great Start | Profile taking shape |

---

## API Usage

### Basic Example

```python
from ucn_rr_engine import UCNCalculator, RRCalculator, CuriosityEngine
from ucn_rr_engine import EvidenceSource, SourceType
from datetime import datetime

# 1. Create evidence
evidence = [
    EvidenceSource(
        SourceType.PHOTO_SERIES,
        "Dark Brown",
        datetime.now(),
        "photo-001",
        quality_metadata={'resolution': 'high', 'lighting': 'good'}
    ),
    EvidenceSource(
        SourceType.SELF_REPORT_TEXT,
        "Dark Brown",
        datetime.now(),
        "self-001"
    )
]

# 2. Calculate UCN
ucn_calc = UCNCalculator()
result = ucn_calc.calculate(
    trait_path="PaDNA.HairDNA.Color",
    evidence_list=evidence
)

print(f"UCN: {result['ucn']}")  # 747
print(f"Value: {result['value']}")  # Dark Brown
print(f"Confidence: {result['confidence_level']}")  # high

# 3. Calculate RR
user_traits = {
    "PaDNA.HairDNA.Color": 747,
    "PaDNA.EyeDNA.Color": 950,
    # ... more traits ...
}

rr_calc = RRCalculator()
rr = rr_calc.calculate_rr("user_id", user_traits)
print(f"RR: {rr}")  # 90.62 percentile

# 4. Generate Curiosity
curiosity_engine = CuriosityEngine()
curiosity = curiosity_engine.calculate_overall_curiosity(rr)
print(f"Curiosity: {curiosity}")  # 9.38

signals = curiosity_engine.get_trait_curiosity_signals(user_traits)
for signal in signals[:3]:
    print(f"{signal.trait_path}: {signal.suggested_action}")
```

---

## CLI Commands

### Calculate UCN/RR for User

```bash
# Calculate for abtest
python3 calculate_ucn_for_user.py abtest --save

# Calculate for mrscoachtest
python3 calculate_ucn_for_user.py mrscoachtest --save

# Quiet mode (no verbose output)
python3 calculate_ucn_for_user.py abtest --quiet
```

### Run All Examples

```bash
python3 ucn_rr_engine/example_usage.py
```

Shows 6 scenarios:
1. Basic UCN calculation
2. Contradiction handling
3. RR calculation
4. Curiosity signals
5. Provenance logging
6. End-to-end workflow

---

## Configuration

### Adjust Evidence Weights

Edit `ucn_rr_engine/config/evidence_weights.yaml`:

```yaml
evidence_sources:
  photo_series:
    base_weight: 0.7      # Increase for more trust in photos
    corroboration_boost: 0.1  # Boost per additional photo

quality_multipliers:
  photo_resolution:
    high: 1.3             # Boost for high-res photos
```

### Adjust Decay Rates

Edit `ucn_rr_engine/config/decay_defaults.yaml`:

```yaml
PaDNA:
  HairDNA:
    Color: 365            # Days until confidence decays to 50%
    Highlights: 60        # Faster decay for temporary traits
```

### Adjust Gates

Edit `ucn_rr_engine/config/thresholds.yaml`:

```yaml
gates:
  sensitive_dna_unlock:
    rr_threshold: 98      # Require 98th percentile
  reliable_coaching:
    rr_threshold: 70      # Require 70th percentile
```

---

## Common Use Cases

### Use Case 1: User Uploads New Photo

```python
# Photo Coach uploads new evidence
new_photo = EvidenceSource(
    SourceType.PHOTO_SINGLE,
    "Dark Brown",
    datetime.now(),
    "photo-new-001",
    quality_metadata={'resolution': 'high', 'lighting': 'good'}
)

# Add to existing evidence
all_evidence = existing_evidence + [new_photo]

# Recalculate UCN
result = ucn_calc.calculate(trait_path, all_evidence)

# UCN increases from 300 → 650 (photo corroborates self-report)
```

### Use Case 2: Detect Contradiction

```python
# User reports different value
new_report = EvidenceSource(
    SourceType.SELF_REPORT_TEXT,
    "Blonde",  # Different from photos showing "Dark Brown"
    datetime.now(),
    "self-002"
)

all_evidence = existing_evidence + [new_report]
result = ucn_calc.calculate(trait_path, all_evidence)

# Contradiction detected!
print(result['contradictions'])
# [{'severity': 'moderate', 'values': ['Dark Brown', 'Blonde'], 'penalty': 0.25}]

# UCN reduced by 25%
# Curiosity increased (via lower RR)
# Head Coach flagged to resolve
```

### Use Case 3: Check If User Unlocked Gate

```python
rr_calc = RRCalculator()
rr_info = rr_calc.get_rr_info(user_id, user_traits)

if 'reliable_coaching' in rr_info['gates_passed']:
    # Enable coaching features
    enable_coaching(user_id)

if 'sensitive_dna_unlock' in rr_info['gates_passed']:
    # Unlock SexDNA, FinanceDNA, etc.
    unlock_sensitive_dnas(user_id)
```

### Use Case 4: Get Refinement Priorities

```python
curiosity_engine = CuriosityEngine()
summary = curiosity_engine.get_curiosity_summary(rr, user_traits)

# Get top 5 traits needing refinement
priorities = summary['trait_signals'][:5]

for signal in priorities:
    print(f"{signal['trait_path']}: {signal['suggested_action']}")

# Output:
# PaDNA.HairDNA.Highlights: Opportunistically gather supporting evidence
# PaDNA.SkinDNA.Tone: Seek additional evidence source to corroborate
# ...
```

---

## Performance

**Calculation Speed**:
- UCN per trait (1 source): < 1ms
- UCN per trait (10 sources): < 5ms
- RR calculation: < 10ms
- Curiosity signals: < 5ms

**Scalability**:
- Users: Tested with 10,000 population
- Traits: Tested with 68 traits per user
- Evidence: Unlimited per trait

---

## Next Steps

### For Developers

1. **Read the spec**: [UCN_RR_ENGINE_SPEC.md](docs/UCN_RR_ENGINE_SPEC.md)
2. **Run examples**: `python3 ucn_rr_engine/example_usage.py`
3. **Test with your user**: `python3 calculate_ucn_for_user.py {user_id} --save`
4. **Explore the code**: Start with `ucn_rr_engine/ucn_calculator.py`

### For Integration

1. **Wire into Explorer**: Expose UCN/RR/Curiosity to Head Coach
2. **Real-time updates**: Recalculate UCN when new evidence arrives
3. **Head Coach planning**: Use curiosity signals for action planning
4. **Population updates**: Schedule daily RR recalculation

---

## Documentation

- **Quick Start**: This file
- **Complete Spec**: [UCN_RR_ENGINE_SPEC.md](docs/UCN_RR_ENGINE_SPEC.md) (1,138 lines)
- **Implementation Summary**: [UCN_RR_IMPLEMENTATION_SUMMARY.md](docs/UCN_RR_IMPLEMENTATION_SUMMARY.md)
- **Integration Results**: [UCN_RR_INTEGRATION_RESULTS.md](docs/UCN_RR_INTEGRATION_RESULTS.md)
- **API Reference**: [ucn_rr_engine/README.md](ucn_rr_engine/README.md)

---

## Support

Questions? Check:
- Examples: `ucn_rr_engine/example_usage.py`
- Integration: `calculate_ucn_for_user.py`
- Configuration: `ucn_rr_engine/config/*.yaml`

---

**Ready to use!** 🚀

The UCN/RR Engine is production-ready and waiting to power your curiosity-driven profile refinement system.
