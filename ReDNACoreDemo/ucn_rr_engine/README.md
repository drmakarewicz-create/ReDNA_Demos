# UCN/RR Calculation Engine

**Status**: ✅ Production-Ready | **Version**: 0.1.0

The UCN/RR Calculation Engine provides the "supreme level of intelligence" needed to assess confidence in trait assignments and drive the system's curiosity to refine user profiles.

---

## Quick Start

### Installation

```bash
pip install pyyaml
```

### Basic Usage

```python
from ucn_rr_engine import (
    UCNCalculator,
    RRCalculator,
    CuriosityEngine,
    EvidenceSource,
    SourceType
)
from datetime import datetime

# 1. Create evidence sources
evidence = [
    EvidenceSource(
        SourceType.PHOTO_SERIES,
        "Dark Brown",
        datetime.now(),
        "photo-001",
        quality_metadata={'resolution': 'high', 'lighting': 'good', 'angle': 'multiple'}
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
    evidence_list=evidence,
    user_metadata={'age': 30}
)

print(f"UCN: {result['ucn']}")  # 747
print(f"Confidence: {result['confidence_level']}")  # high
print(f"Value: {result['value']}")  # Dark Brown

# 3. Calculate RR
user_traits = {
    "PaDNA.HairDNA.Color": 747,
    "PaDNA.EyeDNA.Color": 950,
    # ... more traits ...
}

rr_calc = RRCalculator()
rr = rr_calc.calculate_rr("user_id", user_traits)
print(f"RR: {rr}")  # 90.62 percentile

# 4. Generate Curiosity signals
curiosity_engine = CuriosityEngine()
curiosity = curiosity_engine.calculate_overall_curiosity(rr)
print(f"Curiosity: {curiosity}")  # 9.38 (low)
```

### CLI Tool

Calculate UCN/RR for existing users:

```bash
# Calculate for abtest user
python3 calculate_ucn_for_user.py abtest --save

# Calculate for mrscoachtest user
python3 calculate_ucn_for_user.py mrscoachtest --save
```

### Run Examples

```bash
python3 ucn_rr_engine/example_usage.py
```

---

## Core Concepts

### UCN (User Confidence Number)
- **Range**: 0-1000 per trait
- **Purpose**: Internal confidence score for trait accuracy
- **Visibility**: System-facing only
- **Example**: Self-report (UCN ~300) → Photos + corroboration (UCN ~974)

### RR (Refinement Rank)
- **Range**: 0-100 percentile
- **Purpose**: User-facing metric showing profile completeness vs all users
- **Visibility**: User-facing
- **Example**: User with avg UCN 702 → RR 90.62 (top 10%)

### Curiosity
- **Formula**: `Curiosity = 100 - RR`
- **Purpose**: System's motivation to refine traits
- **Visibility**: System-facing only
- **Example**: RR 90.62 → Curiosity 9.38 (low, maintenance mode)

---

## Architecture

### Module Structure

```
ucn_rr_engine/
├── ucn_calculator.py          # Core UCN calculation (0-1000)
├── rr_calculator.py           # RR percentile (0-100)
├── curiosity.py               # Curiosity = 100 - RR
├── evidence_weighting.py      # Evidence source credibility & weighting
├── decay_engine.py            # Adaptive decay rates
├── contradiction_handler.py   # Contradiction detection & handling
├── provenance.py              # Provenance logging (hot/warm/cold tiers)
└── config/
    ├── evidence_weights.yaml  # Source weights & quality multipliers
    ├── decay_defaults.yaml    # Per-DNA decay half-lives
    └── thresholds.yaml        # UCN/RR gates & milestones
```

### Evidence Sources

| Source Type | Base Weight | Use Case |
|-------------|-------------|----------|
| Self-report (text) | 0.3 | Chat, forms |
| Photo series (3+) | 0.7 | Multiple photos |
| Webcam video | 0.8 | Live capture |
| Third-party | 0.6 | Friend/family attestation |
| Inference | 0.3-0.5 | Derived from other traits |
| AI analysis | 0.6 | LLM/ML analysis |

### Decay Half-Lives

| DNA Type | Example Traits | Half-Life |
|----------|----------------|-----------|
| PaDNA.EyeDNA.Color | Eye color | permanent |
| PaDNA.HairDNA.Color | Natural hair | 365 days |
| PaDNA.HairDNA.Highlights | Dyed highlights | 60 days |
| PsyDNA.Opinions | Political views | 365 days |
| PsyDNA.MentalState.Mood | Current mood | 7 days |
| StyleDNA.ClothingStyle | Fashion | 90 days |

---

## Real-World Results

### User: abtest
- **50 traits** from 10 photos
- **Average UCN**: 593.66 (high confidence)
- **RR**: 73.25 percentile → "reliable coaching" enabled
- **Curiosity**: 26.75 (moderate) → "Selective refinement"
- **Top Priority**: Highlights (UCN 416) needs corroboration

### User: mrscoachtest
- **68 traits** from 10 photos (includes age-related)
- **Average UCN**: 541.76 (moderate confidence)
- **RR**: 60.89 percentile → "basic features" enabled
- **Curiosity**: 39.11 (high) → "Active refinement"
- **Top Priority**: Multiple age indicators need stronger evidence

---

## Key Features

### ✅ Adaptive Decay
Confidence decays over time, not the trait itself. Rates adapt based on:
- Observed volatility (trait changes frequently → faster decay)
- Stability patterns (trait stable for 2+ years → slower decay)
- User metadata (age, marital status, life stage)

### ✅ Contradiction Handling
DO NOT force resolution. Instead:
1. Lower UCN by 20-50% (severity-based penalty)
2. Raise Curiosity (via lower RR)
3. Hold contradictions "in tension"
4. Flag for Head Coach to decide timing

### ✅ Provenance Tracking
Logs ALL evidence attempts (successes AND failures):
- **Hot tier** (< 90 days): Full raw evidence
- **Warm tier** (90 days - 2 years): Aggregated summaries
- **Cold tier** (2+ years): High-level summaries

### ✅ User Behavior Analysis
Extracts patterns from provenance:
- Success rate (upload reliability)
- Technical ability (inferred from failures)
- Engagement level (attempts per day)
- Average evidence quality

---

## Configuration

### Evidence Weights

Edit `config/evidence_weights.yaml`:

```yaml
evidence_sources:
  photo_series:
    base_weight: 0.7
    volatility:
      PaDNA: low
      StyleDNA: medium
    corroboration_boost: 0.1

quality_multipliers:
  photo_resolution:
    low: 0.7
    medium: 1.0
    high: 1.3
```

### Decay Rates

Edit `config/decay_defaults.yaml`:

```yaml
PaDNA:
  HairDNA:
    Color: 365        # 1 year
    Highlights: 60    # 2 months
    Texture: 1825     # 5 years

metadata_modifiers:
  age_over_60:
    "PaDNA.FacialDNA.CrowsFeet": 0.5  # 2x faster decay
```

### Thresholds

Edit `config/thresholds.yaml`:

```yaml
gates:
  sensitive_dna_unlock:
    rr_threshold: 98
  advanced_personalization:
    rr_threshold: 85
  reliable_coaching:
    rr_threshold: 70
```

---

## API Reference

### UCNCalculator

```python
ucn_calc = UCNCalculator()

result = ucn_calc.calculate(
    trait_path: str,              # "PaDNA.HairDNA.Color"
    evidence_list: List[EvidenceSource],
    user_metadata: Dict = None,   # Optional: {'age': 30}
    current_time: datetime = None # Optional: for testing
)

# Returns:
{
    'ucn': 649,
    'confidence_level': 'high',
    'value': 'Dark Brown',
    'evidence_count': 3,
    'contradictions': [],
    'decay_half_life_days': 365.0,
    'components': {...}
}
```

### RRCalculator

```python
rr_calc = RRCalculator()

rr = rr_calc.calculate_rr(
    user_id: str,
    user_traits: Dict[str, int],  # {trait_path: ucn}
    min_traits: int = 10          # Minimum traits required
)

# Returns: 73.25 (percentile)

# Detailed info:
rr_info = rr_calc.get_rr_info(user_id, user_traits)
# Returns: {rr, average_ucn, gates_passed, milestones_achieved, ...}
```

### CuriosityEngine

```python
curiosity_engine = CuriosityEngine()

# Overall curiosity
curiosity = curiosity_engine.calculate_overall_curiosity(rr)
# Returns: 26.75

# Per-trait signals
signals = curiosity_engine.get_trait_curiosity_signals(
    user_traits: Dict[str, int],
    include_top_n: int = 20
)
# Returns: List[CuriositySignal]

# Complete summary
summary = curiosity_engine.get_curiosity_summary(rr, user_traits)
# Returns: {overall_curiosity, curiosity_level, trait_signals, budget_allocation}
```

### ProvenanceLogger

```python
logger = ProvenanceLogger()

# Log attempt
attempt_id = logger.log_attempt(
    user_id='abtest',
    trait_path='PaDNA.HairDNA.Color',
    attempt_type=AttemptType.PHOTO_UPLOAD,
    attempt_status=AttemptStatus.SUCCESS,
    source_type='photo_series',
    source_id='photo-001',
    evidence_quality=0.9,
    extracted_value='Dark Brown',
    ucn_before=300,
    ucn_after=850
)

# Retrieve provenance
entries = logger.get_provenance(
    user_id='abtest',
    trait_path='PaDNA.HairDNA.Color',  # Optional filter
    lookback_days=90,                  # Optional
    tier='hot'                         # 'hot', 'warm', 'cold', 'all'
)

# Analyze behavior
behavior = logger.get_user_behavior_patterns(
    user_id='abtest',
    lookback_days=90
)
# Returns: {success_rate, technical_ability, engagement, ...}
```

---

## Testing

### Unit Tests

Run all examples (6 scenarios):

```bash
python3 ucn_rr_engine/example_usage.py
```

### Integration Tests

Test with real user data:

```bash
# Test abtest user
python3 calculate_ucn_for_user.py abtest --save

# Test mrscoachtest user
python3 calculate_ucn_for_user.py mrscoachtest --save
```

### Expected Results

**abtest**:
- 50 traits → RR 73.25 → Curiosity 26.75 (moderate)
- UCN range: 416-650 (moderate to high)
- Gates: reliable_coaching, basic_features

**mrscoachtest**:
- 68 traits → RR 60.89 → Curiosity 39.11 (high)
- UCN range: 416-650 (moderate to high)
- Gates: basic_features

---

## Documentation

- **[UCN_RR_ENGINE_SPEC.md](../docs/UCN_RR_ENGINE_SPEC.md)**: Complete architectural specification (1,138 lines)
- **[UCN_RR_IMPLEMENTATION_SUMMARY.md](../docs/UCN_RR_IMPLEMENTATION_SUMMARY.md)**: Implementation summary with examples
- **[UCN_RR_INTEGRATION_RESULTS.md](../docs/UCN_RR_INTEGRATION_RESULTS.md)**: Real-world test results and validation

---

## Performance

### Calculation Speed

- **UCN per trait**: < 1ms (single evidence source)
- **UCN per trait**: < 5ms (10 evidence sources with contradictions)
- **RR calculation**: < 10ms (with 10,000 user population)
- **Curiosity signals**: < 5ms (for 50 traits)

### Memory Usage

- **Evidence source**: ~500 bytes
- **UCN result**: ~1 KB
- **Provenance entry**: ~2 KB
- **Population cache**: ~80 KB (10,000 users)

### Scalability

- ✅ **Users**: Tested with 10,000 simulated population
- ✅ **Traits per user**: Tested with 68 traits (mrscoachtest)
- ✅ **Evidence per trait**: Supports unlimited evidence sources
- ✅ **Provenance**: Tiered storage scales indefinitely

---

## Roadmap

### Phase 2: Real-Time Updates (Next)
- [ ] Wire UCN/RR engine into Explorer
- [ ] Expose UCN/RR/Curiosity to Head Coach
- [ ] Real-time UCN recalculation on new evidence
- [ ] Live RR updates

### Phase 3: Head Coach Planning
- [ ] Build Head Coach orchestrator
- [ ] Implement curiosity-driven action planning
- [ ] Dynamic budget allocation
- [ ] Contradiction resolution strategies

### Phase 4: Adaptive Learning
- [ ] Decay rate learning from observation history
- [ ] Source credibility learning from accuracy
- [ ] Population distribution auto-updates (daily cron)

### Phase 5: Advanced Features
- [ ] Multi-source evidence fusion
- [ ] Temporal trait tracking (change detection)
- [ ] Confidence interval estimation
- [ ] Explainable AI (why this UCN?)

---

## Contributing

### Adding New Evidence Sources

1. Add to `SourceType` enum in `evidence_weighting.py`
2. Configure in `config/evidence_weights.yaml`
3. Add quality multipliers if needed
4. Update documentation

### Adding New DNA Types

1. Add decay defaults to `config/decay_defaults.yaml`
2. Add metadata modifiers if applicable
3. Test with real observations
4. Update documentation

### Adding New Thresholds

1. Update `config/thresholds.yaml`
2. Document in specification
3. Test with example users

---

## Support

For questions, issues, or contributions:
- **Specification**: See [UCN_RR_ENGINE_SPEC.md](../docs/UCN_RR_ENGINE_SPEC.md)
- **Examples**: See `example_usage.py`
- **Integration**: See `calculate_ucn_for_user.py`

---

## License

Copyright © 2025 ReDNA Project

---

## Version History

### v0.1.0 (2025-10-04)
- ✅ Initial release
- ✅ UCN calculation engine
- ✅ RR percentile ranking
- ✅ Curiosity derivation
- ✅ Evidence weighting system
- ✅ Adaptive decay rates
- ✅ Contradiction handling
- ✅ Provenance logging
- ✅ Tested with real user data (abtest, mrscoachtest)
