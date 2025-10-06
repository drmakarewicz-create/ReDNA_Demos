# UCN/RR Calculation Engine - Architectural Specification

## Overview

The UCN/RR Calculation Engine is the intelligence layer within ReDNA Core that assesses confidence in trait assignments and drives the system's curiosity to refine user profiles. It requires "supreme level of intelligence" to weigh evidence from multiple sources and assign confidence scores that reflect how accurately we believe a trait matches the IRL (in real life) user.

**Key Principles:**
- Confidence decays over time, not the trait itself
- More recent data is generally more trustworthy (with learned exceptions)
- Wide inference/speculation is encouraged, weighted by confidence
- All evidence attempts are logged (successes AND failures)
- Contradictions are held "in tension" until Head Coach decides resolution timing
- System-facing only (users see RR, not UCN/Curiosity)

## Core Metrics

### UCN (User Confidence Number)
- **Range:** 0-1000 per trait
- **Purpose:** Internal confidence score for how accurately a trait matches IRL reality
- **Visibility:** System-facing only
- **Calculation:** Complex AI-driven assessment of evidence quality, quantity, recency, and corroboration

### RR (Refinement Rank)
- **Range:** 0-100 percentile
- **Purpose:** User-facing metric showing profile completeness/refinement vs all living users
- **Calculation:** Percentile rank of user's average UCN across all traits vs population distribution
- **Visibility:** User-facing

### Curiosity
- **Formula:** `Curiosity = 100 - RR`
- **Purpose:** System's motivation to refine/validate traits
- **Properties:**
  - Larger number = more motivation to refine
  - Normalizes across different DNA types
  - System-facing only
- **Visibility:** System-facing only

## Architecture

### Module Location
**ReDNACoreDemo/ucn_rr_engine/**
- Located in Core (NOT in Explorer or as separate service)
- Tightly integrated with evidence loading and inference system
- Provides signals to Head Coach via Explorer

### Module Structure

```
ReDNACoreDemo/
├── ucn_rr_engine/
│   ├── __init__.py
│   ├── ucn_calculator.py          # Core UCN calculation logic
│   ├── rr_calculator.py           # RR percentile calculation
│   ├── curiosity.py               # Curiosity derivation
│   ├── evidence_weighting.py     # Evidence source credibility & weighting
│   ├── decay_engine.py           # Adaptive decay rate system
│   ├── contradiction_handler.py  # Contradiction detection & handling
│   ├── provenance.py             # Provenance tracking & logging
│   └── config/
│       ├── evidence_weights.yaml  # Evidence source base weights
│       ├── decay_defaults.yaml    # Per-DNA decay half-lives
│       └── thresholds.yaml        # UCN thresholds for various gates
```

## Evidence Weighting System

### Evidence Source Types

Evidence sources are weighted based on credibility, recency, and corroboration:

| Source Type | Base Weight | Volatility | Corroboration Boost | Decay Rate |
|-------------|-------------|------------|---------------------|------------|
| **Self-report (text)** | 0.3 | High | +0.2 with 2+ corroborations | Fast |
| **Self-report (structured form)** | 0.4 | High | +0.2 with 2+ corroborations | Fast |
| **Photo (single)** | 0.5 | Low (PaDNA) / High (StyleDNA) | +0.15 per additional photo | Slow (PaDNA) / Fast (StyleDNA) |
| **Photo series (3+)** | 0.7 | Low (PaDNA) / Med (StyleDNA) | +0.1 per additional photo | Slow (PaDNA) / Medium (StyleDNA) |
| **Third-party attestation** | 0.6 | Medium | +0.2 with photo corroboration | Medium |
| **Live webcam video** | 0.8 | Very Low (PaDNA) | +0.15 with other sources | Very Slow (PaDNA) |
| **Behavioral observation** | 0.5 | Medium | +0.2 with consistent patterns | Medium |
| **Device sensor (passive)** | 0.7 | Low | +0.15 with other sensors | Slow |
| **Inference (single rule)** | 0.3 | N/A | +0.1 per additional rule | Inherits from source |
| **Inference (multiple rules)** | 0.5 | N/A | +0.15 when corroborated | Inherits from source |
| **AI analysis (LLM)** | 0.6 | N/A | +0.2 with human validation | Medium |
| **Failed attempt** | -0.1 | N/A | Context for User traits | N/A |

### UCN Calculation Formula

```python
UCN = clamp(
    sum(evidence_weight * recency_factor * corroboration_factor * source_credibility)
    * (1 - contradiction_penalty)
    * quality_multiplier,
    0, 1000
)
```

**Components:**

1. **evidence_weight:** Base weight from table above
2. **recency_factor:** `e^(-age_in_days / decay_half_life)`
3. **corroboration_factor:** `1 + (corroboration_boost * num_corroborating_sources)`
4. **source_credibility:** 0.0-1.5 multiplier based on source history (learns over time)
5. **contradiction_penalty:** 0.0-0.5 reduction when contradictory evidence exists
6. **quality_multiplier:** 0.5-2.0 based on evidence quality (photo resolution, form completeness, etc.)

### Example Calculations

**Example 1: Hair Color = "Red"**

Evidence:
- Self-report (text): "My hair is red" → weight 0.3, 1 day old
- No corroboration, no photos

```
UCN = 0.3 * 1.0 * 1.0 * 1.0 * 1.0 * 1.0 = 0.3
Scaled to 0-1000: UCN = 300 (30% confidence)
```

**Example 2: Hair Color = "Red" (with corroboration)**

Evidence:
- Self-report (text): "My hair is red" → weight 0.3, 1 day old
- Photo series (5 photos): clearly show red hair → weight 0.7 + (2 * 0.1) = 0.9, 2 days old
- Third-party: Friend attests "Yes, red hair" → weight 0.6, 3 days old
- Corroboration boost: 3 sources = +0.4

```
UCN = (0.3 + 0.9 + 0.6) * 1.0 * 1.4 * 1.0 * 1.0 * 1.0 = 2.52
Clamped and scaled: UCN = 1000 (extremely high confidence)
```

**Example 3: Opinion (PsyDNA, volatile)**

Evidence:
- Self-report: "I love jazz music" → weight 0.3, 180 days old
- Decay half-life: 90 days for opinions
- recency_factor = e^(-180/90) = e^(-2) ≈ 0.135

```
UCN = 0.3 * 0.135 * 1.0 * 1.0 * 1.0 * 1.0 = 0.0405
Scaled: UCN = 41 (very low confidence due to age)
```

## Adaptive Decay System

### Principle: "Confidence Decays, Not the Trait"

Decay rates are NOT fixed. The AI learns optimal decay rates per DNA type and per data point based on:
- Observed volatility (how often the trait changes)
- Stability patterns (traits that remain consistent across multiple observations)
- Metadata (user's age, life stage, etc.)
- Exception patterns (traits that buck general trends)

### Default Decay Half-Lives (Starting Points)

```yaml
# decay_defaults.yaml
PaDNA:
  HairDNA:
    Color: 365 days          # Hair color changes slowly (if natural)
    ColorDyed: 45 days       # Dyed color changes more frequently
    Length: 90 days          # Hair length changes moderately
    Texture: 1825 days       # Texture rarely changes (5 years)
  EyeDNA:
    Color: permanent         # Eye color doesn't change
    ColorIntensity: 1825 days  # Perceived intensity stable
  SkinDNA:
    Tone: 730 days           # Skin tone relatively stable
    Freckles: 365 days       # Freckles change with sun exposure
  FacialDNA:
    FaceShape: permanent     # Bone structure doesn't change
    CrowsFeet: 180 days      # Aging indicators change gradually
    SkinMaturity: 365 days   # Age-related features evolve

PsyDNA:
  Opinions:
    PoliticalViews: 365 days    # Can change but generally stable
    MusicPreference: 180 days   # More fluid
    FoodPreference: 90 days     # Changes frequently
  Personality:
    BigFive: 1825 days          # Personality traits very stable
    Values: 730 days            # Core values moderately stable
  MentalState:
    Mood: 7 days                # Mood highly volatile
    Stress: 30 days             # Stress moderately volatile

StyleDNA:
  ClothingStyle: 90 days        # Fashion preferences change seasonally
  ColorPreference: 180 days     # Color preferences moderately stable
  AccessoryPreference: 60 days  # Accessories change frequently

SoDNA:
  Relationships: 180 days       # Relationships change but not daily
  SocialCircle: 90 days         # Social circles evolve regularly

HealthDNA:
  Weight: 30 days               # Weight can fluctuate
  Fitness: 60 days              # Fitness changes gradually
  Allergies: permanent          # Allergies rarely resolve

SkillsDNA:
  TechnicalSkills: 365 days     # Skills degrade without practice
  Languages: 730 days           # Language proficiency stable with use
  Hobbies: 180 days             # Active hobbies change

HistoryDNA:
  Birthplace: permanent         # Historical facts don't change
  Education: permanent          # Completed education immutable
  CareerHistory: permanent      # Past jobs don't change
```

### Adaptive Learning

The decay engine monitors trait stability over time and adjusts decay rates:

```python
# If a trait has 5+ observations over 2+ years with no changes:
adjusted_decay_half_life = default_half_life * 2.0  # Slower decay

# If a trait changes 3+ times in 6 months:
adjusted_decay_half_life = default_half_life * 0.5  # Faster decay

# Exception pattern: Trait that usually changes frequently but has been stable:
# Monitor for 90 days after last change, then slow decay rate
```

### Metadata Overrides

Certain metadata triggers decay rate adjustments:

```python
# User age > 60 → FacialDNA aging indicators decay faster (more rapid aging)
# User in college → Opinions decay faster (formative period)
# User married → RelationshipDNA decays slower (increased stability)
# User has chronic condition → HealthDNA decays faster (more volatile)
```

## Provenance Tracking System

### Tiered Storage Architecture

**Hot Tier (Last 90 Days):**
- Full raw evidence stored
- All metadata preserved
- Fast query access
- Used for active decision-making

**Warm Tier (90 days - 2 years):**
- Aggregated summaries
- Key metadata preserved
- Original evidence compressed or archived
- Query latency acceptable

**Cold Tier (2+ years):**
- High-level summaries only
- Critical events preserved
- Original evidence archived to S3/cold storage
- Query latency high but acceptable

### Provenance Log Structure

```json
{
  "trait_path": "PaDNA.HairDNA.Color",
  "timestamp": "2025-10-04T15:23:45Z",
  "attempt_id": "uuid-12345",
  "attempt_type": "photo_upload",
  "attempt_status": "success" | "failure" | "partial",
  "source_type": "photo",
  "source_id": "photo-uuid-67890",
  "evidence_quality": 0.85,
  "extracted_value": "Dark Brown",
  "confidence_assigned": 0.75,
  "ucn_before": 320,
  "ucn_after": 680,
  "corroboration_sources": ["self-report-uuid-111", "photo-uuid-222"],
  "contradiction_sources": [],
  "decay_half_life_applied": 365,
  "failure_reason": null,
  "user_behavior_indicators": {
    "upload_attempt_count": 1,
    "upload_success_rate": 1.0,
    "photo_quality": "high"
  }
}
```

### Failed Attempt Logging

Failed attempts reveal valuable information:

```json
{
  "trait_path": "PaDNA.HairDNA.Color",
  "timestamp": "2025-10-04T15:20:12Z",
  "attempt_id": "uuid-54321",
  "attempt_type": "photo_upload",
  "attempt_status": "failure",
  "failure_reason": "file_too_large",
  "user_behavior_indicators": {
    "upload_attempt_count": 3,
    "upload_success_rate": 0.0,
    "technical_ability": "low"  # Inferred from repeated failures
  },
  "head_coach_notes": "User struggling with photo uploads. May need guidance or system improvement."
}
```

## Contradiction Handling

### Detection Logic

Contradictions are detected when:
1. Two evidence sources assign different values to the same trait
2. The source weights are both > 0.3 (not trivial)
3. The time delta between sources is < 2 * decay_half_life

### Contradiction Response

**DO NOT force immediate resolution.** Instead:

1. **Lower UCN:**
   ```python
   ucn_with_contradiction = ucn_base * (1 - contradiction_penalty)
   # where contradiction_penalty = 0.2 to 0.5 depending on severity
   ```

2. **Raise Curiosity:**
   ```python
   # Since Curiosity = 100 - RR, lowering UCN lowers RR, which raises Curiosity
   ```

3. **Hold in Tension:**
   ```python
   # Store both contradictory values in trait container:
   {
     "trait_path": "PaDNA.HairDNA.Color",
     "value": "Dark Brown",  # Most recent or highest-weight source
     "ucn": 450,              # Reduced due to contradiction
     "contradictions": [
       {
         "value": "Blonde",
         "source": "self-report-uuid-111",
         "weight": 0.3,
         "timestamp": "2025-09-01T10:00:00Z"
       }
     ],
     "resolution_strategy": "await_head_coach_decision"
   }
   ```

4. **Flag for Head Coach:**
   - Add to Head Coach's curiosity queue
   - Provide context from provenance log
   - Let Head Coach decide WHEN to resolve (not forced timing)

### Contradiction Severity Levels

| Severity | Criteria | UCN Penalty | Action |
|----------|----------|-------------|--------|
| **Trivial** | One source weight < 0.3 | 0% | Ignore weaker source |
| **Minor** | Sources differ slightly, both < 0.5 weight | 10% | Lower UCN, monitor |
| **Moderate** | Sources differ clearly, one > 0.5 weight | 20-30% | Lower UCN, flag for Head Coach |
| **Severe** | Sources strongly contradict, both > 0.5 weight | 40-50% | Significantly lower UCN, priority flag for Head Coach |

## RR Percentile Calculation

### Population Distribution

RR is calculated by comparing a user's average UCN across all traits to the population distribution of all living users.

```python
def calculate_rr(user_id: str) -> float:
    """Calculate Refinement Rank (RR) percentile for user."""

    # 1. Calculate user's average UCN across all traits
    user_traits = load_user_traits(user_id)
    user_avg_ucn = sum(trait.ucn for trait in user_traits) / len(user_traits)

    # 2. Load population UCN distribution (cached, updated daily)
    population_ucns = load_population_distribution()

    # 3. Calculate percentile rank
    users_below = sum(1 for ucn in population_ucns if ucn < user_avg_ucn)
    rr_percentile = (users_below / len(population_ucns)) * 100

    return round(rr_percentile, 2)
```

### Population Distribution Caching

- Recalculated daily at 3 AM UTC
- Cached in Redis for fast lookup
- Includes all users with at least 10 traits
- Excludes deceased users (unless 3mo+ dormant period passed)

### RR Thresholds & Gates

```yaml
# thresholds.yaml
gates:
  sensitive_dna_unlock: 98  # RR >= 98 to unlock SexDNA, etc.
  advanced_features: 85     # RR >= 85 for advanced personalization
  coach_recommendations: 70 # RR >= 70 for reliable coaching

celebrations:
  milestone_50: "You're halfway there!"
  milestone_75: "Your profile is well-refined!"
  milestone_90: "Exceptional refinement!"
  milestone_98: "Elite refinement - sensitive DNAs unlocked!"
```

## Integration Points

### 1. Core → UCN/RR Engine

```python
# After loading evidence and running inference:
from ucn_rr_engine import UCNCalculator, RRCalculator

ucn_calc = UCNCalculator()
rr_calc = RRCalculator()

# Calculate UCN for all traits
for trait_path, trait_data in user_traits.items():
    evidence = load_evidence(user_id, trait_path)
    ucn = ucn_calc.calculate(trait_path, evidence)
    trait_data['ucn'] = ucn

# Calculate overall RR
rr = rr_calc.calculate_rr(user_id)
```

### 2. UCN/RR Engine → Head Coach (via Explorer)

```python
# Explorer exposes UCN/RR/Curiosity signals to Head Coach
curiosity_signals = {
    'overall_curiosity': 100 - rr,
    'high_curiosity_traits': [
        {'path': 'PaDNA.EyeDNA.Color', 'ucn': 250, 'curiosity': 75},
        {'path': 'PsyDNA.Values.Politics', 'ucn': 180, 'curiosity': 82},
    ],
    'contradictions': [
        {'path': 'PaDNA.HairDNA.Color', 'severity': 'moderate', 'ucn': 420}
    ],
    'stale_traits': [
        {'path': 'HealthDNA.Weight', 'ucn': 300, 'days_old': 180}
    ]
}

# Head Coach uses these signals for planning
head_coach.process_curiosity_signals(curiosity_signals)
```

### 3. External Apps → UCN/RR Engine (Confidence Feedback)

```python
# External apps (Photo Coach, UCN Rescore, etc.) feed confidence updates
from ucn_rr_engine import update_evidence

# Photo Coach uploads new photo:
update_evidence(
    user_id='abtest',
    trait_path='PaDNA.HairDNA.Color',
    source_type='photo',
    source_id='photo-uuid-99999',
    extracted_value='Dark Brown',
    evidence_quality=0.9,
    timestamp='2025-10-04T16:00:00Z'
)

# UCN recalculated automatically
```

### 4. Provenance → Head Coach (Decision Context)

```python
# When Head Coach needs context for planning:
provenance = get_provenance_log(
    user_id='abtest',
    trait_path='PaDNA.HairDNA.Color',
    lookback_days=90
)

# Returns full history of evidence attempts, failures, contradictions
# Head Coach uses this to decide next action (e.g., ask for photo, ignore contradiction, etc.)
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create module structure in ReDNACoreDemo/ucn_rr_engine/
- [ ] Implement evidence weighting system (evidence_weighting.py)
- [ ] Implement UCN calculator (ucn_calculator.py)
- [ ] Create default evidence weights config (evidence_weights.yaml)
- [ ] Write unit tests for UCN calculation

### Phase 2: Decay & Provenance (Week 2)
- [ ] Implement decay engine (decay_engine.py)
- [ ] Create decay defaults config (decay_defaults.yaml)
- [ ] Implement provenance logging (provenance.py)
- [ ] Set up tiered storage (hot/warm/cold)
- [ ] Write unit tests for decay and provenance

### Phase 3: RR & Curiosity (Week 3)
- [ ] Implement RR calculator (rr_calculator.py)
- [ ] Implement population distribution caching
- [ ] Implement Curiosity derivation (curiosity.py)
- [ ] Create thresholds config (thresholds.yaml)
- [ ] Write unit tests for RR and Curiosity

### Phase 4: Contradiction Handling (Week 4)
- [ ] Implement contradiction detection (contradiction_handler.py)
- [ ] Implement "hold in tension" logic
- [ ] Implement severity scoring
- [ ] Wire Head Coach flagging system
- [ ] Write unit tests for contradiction handling

### Phase 5: Integration (Week 5)
- [ ] Integrate UCN/RR engine with Core evidence loading
- [ ] Wire provenance logging to all evidence attempts
- [ ] Expose UCN/RR/Curiosity signals to Explorer
- [ ] Test end-to-end with real user data
- [ ] Performance optimization

### Phase 6: Learning & Refinement (Week 6+)
- [ ] Implement adaptive decay learning
- [ ] Implement source credibility learning
- [ ] Train initial models on existing user data
- [ ] Monitor and tune thresholds
- [ ] Document AI prompts for UCN assessment

## Success Criteria

1. **UCN Calculation Accuracy:**
   - Hair color from self-report: UCN ~300
   - Hair color from 5+ photos: UCN ~700-900
   - Hair color from photos + third-party: UCN ~900-1000

2. **Decay System:**
   - PaDNA traits decay slowly (1+ year half-life)
   - PsyDNA opinions decay faster (90-180 day half-life)
   - Adaptive learning adjusts rates within 3 months

3. **RR Calculation:**
   - User with 50 traits, avg UCN 600 → RR ~60-70
   - User with 100 traits, avg UCN 800 → RR ~85-95
   - Population distribution updates daily

4. **Provenance:**
   - 100% of evidence attempts logged (success + failure)
   - Failed attempts reveal user behavior patterns
   - Tiered storage keeps hot tier < 90 days

5. **Contradiction Handling:**
   - Contradictions detected within 1 second
   - UCN reduced appropriately (20-50% depending on severity)
   - Head Coach receives prioritized flags

## Open Questions for User

1. **Population Distribution:** Should RR be calculated against:
   - All users globally?
   - Users in same demographic cohort (age, location, etc.)?
   - Users who have opted into comparison?

2. **Sensitive DNA Gates:** Should we have different RR thresholds for different sensitive DNAs?
   - SexDNA: RR >= 98?
   - FinanceDNA: RR >= 95?
   - HealthDNA (genetic): RR >= 97?

3. **Provenance Storage Costs:** What's the acceptable storage budget per user?
   - 1 MB/month (minimal, summaries only)?
   - 10 MB/month (moderate, compressed evidence)?
   - 100 MB/month (extensive, full raw evidence)?

4. **AI Model for UCN Assessment:** Should this be:
   - Rule-based system (fast, deterministic, limited intelligence)?
   - LLM-based (GPT-4/Claude, slow, expensive, supreme intelligence)?
   - Hybrid (rules + LLM for complex cases)?

5. **Curiosity Budget (Dynamic):** How should Head Coach balance:
   - High-impact, low-UCN traits (big wins)?
   - Low-impact, low-UCN traits (easy wins)?
   - Contradictions (resolve uncertainty)?
   - Stale traits (refresh old data)?
