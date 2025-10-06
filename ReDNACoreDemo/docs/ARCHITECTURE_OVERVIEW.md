# UCN/RR System Architecture Overview

**Visual guide to how the UCN/RR Calculation Engine works**

---

## System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER UPLOADS EVIDENCE                    │
│  (photos, self-reports, third-party attestations, sensors, etc.) │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EVIDENCE WEIGHTING SYSTEM                     │
│  • Base weights (0.3-0.8 by source type)                        │
│  • Quality multipliers (resolution, lighting, etc.)             │
│  • Corroboration boosts (+0.1 to +0.2 per source)              │
│  • Recency factor (exponential decay)                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTRADICTION DETECTION                       │
│  • Compare evidence sources                                      │
│  • Calculate severity (trivial/minor/moderate/severe)           │
│  • Apply UCN penalty (0% to 50%)                                │
│  • Hold "in tension" (don't force resolution)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      UCN CALCULATION                             │
│  Formula:                                                        │
│  UCN = clamp(                                                    │
│    sum(weight * recency * corroboration * credibility)          │
│    * (1 - contradiction_penalty)                                │
│    * quality_multiplier,                                        │
│    0, 1000                                                       │
│  )                                                               │
│                                                                  │
│  Result: 0-1000 confidence score per trait                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RR CALCULATION                              │
│  1. Calculate average UCN across all user traits                │
│  2. Compare to population distribution (all users)              │
│  3. Calculate percentile rank                                   │
│                                                                  │
│  Result: 0-100 percentile (RR)                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CURIOSITY DERIVATION                           │
│  Formula: Curiosity = 100 - RR                                  │
│                                                                  │
│  Result: 0-100 motivation score (higher = more curious)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CURIOSITY SIGNALS                              │
│  • Per-trait priorities (critical/high/medium/low)              │
│  • Suggested actions (request photos, corroborate, etc.)        │
│  • Strategy (aggressive/active/selective/maintenance)           │
│  • Budget allocation (max concurrent actions)                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     HEAD COACH PLANNING                          │
│  • Consumes curiosity signals                                    │
│  • Prioritizes refinement actions                               │
│  • Balances user well-being with system improvement            │
│  • Decides when to resolve contradictions                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Evidence Flow Example

### Scenario: User Says "My hair is dark brown"

```
Step 1: Self-Report
  Source: "My hair is dark brown"
  Type: SELF_REPORT_TEXT
  Base Weight: 0.3
  ↓
  UCN: ~300 (30% confidence)
  Status: Low confidence - needs corroboration


Step 2: User Uploads Photos
  Source: 10 photos showing dark brown hair
  Type: PHOTO_SERIES
  Base Weight: 0.7
  Quality: High resolution (1.3x), Good lighting (1.2x), Multiple angles (1.2x)
  ↓
  Combined Weight: 0.7 × 1.87 = 1.31
  UCN: ~649 (65% confidence)
  Status: High confidence


Step 3: Friend Confirms
  Source: Third-party attestation
  Type: THIRD_PARTY_ATTESTATION
  Base Weight: 0.6
  Corroboration: Now 3 sources agree
  ↓
  Self-report: 0.3 + corroboration boost (0.2) = 0.5
  Photos: 1.31 (already strong)
  Third-party: 0.6 + corroboration boost (0.2) = 0.8
  Total Weight: 0.5 + 1.31 + 0.8 = 2.61
  ↓
  UCN: ~974 (97% confidence)
  Status: Very high confidence - multiple corroborating sources
```

---

## RR Calculation Example

### User Profile

```
User: abtest
Traits: 50

Individual UCN scores:
  PaDNA.HairDNA.Color: 649
  PaDNA.EyeDNA.Color: 650
  PaDNA.FacialDNA.FaceShape: 650
  PaDNA.SkinDNA.Tone: 649
  ... 46 more traits ...

Average UCN: 593.66
```

### Population Comparison

```
Population: 10,000 users
Distribution of average UCNs:
  [200, 250, 280, 320, ..., 593.66 (USER), ..., 850, 920, 980]
       ↑                        ↑                           ↑
    Bottom                   abtest                       Top

Users with lower avg UCN than abtest: 7,325
Percentile: 7,325 / 10,000 = 73.25%

RR: 73.25 (top 27%)
```

### Curiosity Calculation

```
RR: 73.25
Curiosity: 100 - 73.25 = 26.75

Level: Moderate
Strategy: "Selective refinement - targeted improvements"
Focus: "Contradictions and stale traits"
Max Concurrent Actions: 3
```

---

## Contradiction Handling Flow

### Scenario: Hair Color Changed

```
Evidence Timeline:
  6 months ago: 5 photos showing "Blonde" (UCN 650)
  1 week ago: 5 photos showing "Dark Brown" (UCN 650)
  Today: User says "I dyed it brown"

Step 1: Contradiction Detection
  ✓ Two different values ("Blonde" vs "Dark Brown")
  ✓ Both sources have weight > 0.3 (both significant)
  ✓ Time delta < 2 × decay half-life (still relevant)
  ↓
  Contradiction Detected: SEVERE
  (Both sources have weight > 0.5)


Step 2: Severity Assessment
  Source A: Photos (Blonde) - Weight 0.65 (decayed from 0.7)
  Source B: Photos (Dark Brown) - Weight 0.7
  ↓
  Both > 0.5 → Severity: SEVERE
  Penalty: 50%


Step 3: UCN Adjustment
  Without contradiction:
    Total weight: 0.65 + 0.7 = 1.35
    UCN: ~700

  With contradiction:
    UCN: 700 × (1 - 0.5) = 350

  Final: UCN 350 (reduced by 50%)


Step 4: Hold in Tension
  Status: "in_tension"
  Consensus Value: "Dark Brown" (most recent)
  Contradictions: [
    {
      severity: "severe",
      values: ["Blonde", "Dark Brown"],
      penalty: 0.5
    }
  ]
  Flagged for Head Coach: CRITICAL priority


Step 5: Head Coach Decision
  Options:
  1. Ask user to confirm current color
  2. Request recent photo/webcam
  3. Wait for natural evidence (user uploads more photos)
  4. Accept that hair was dyed (legitimate change)

  Decision: Mark as legitimate change, no action needed
  (User confirmed "I dyed it brown")
```

---

## Decay Over Time

### Example: Hair Color Confidence Decay

```
Observation: "Dark Brown" hair color
Initial UCN: 650 (from photo series)
Decay Half-Life: 365 days (natural hair color)

Timeline:
  Day 0 (today):
    Recency Factor: 1.0
    UCN: 650 × 1.0 = 650 ✓

  Day 180 (6 months):
    Recency Factor: e^(-180/365) = 0.62
    UCN: 650 × 0.62 = 403 ↓

  Day 365 (1 year):
    Recency Factor: e^(-365/365) = 0.37
    UCN: 650 × 0.37 = 241 ↓↓

  Day 730 (2 years):
    Recency Factor: e^(-730/365) = 0.14
    UCN: 650 × 0.14 = 91 ↓↓↓

Recommendation: Request fresh evidence after 6-12 months
```

### Comparison: Different Decay Rates

```
Trait: Eye Color (permanent)
  Half-Life: ∞
  Day 365: UCN 650 → 650 (no decay)
  Day 730: UCN 650 → 650 (no decay)

Trait: Natural Hair Color
  Half-Life: 365 days
  Day 365: UCN 650 → 241 (37% of original)
  Day 730: UCN 650 → 91 (14% of original)

Trait: Dyed Highlights
  Half-Life: 60 days
  Day 60: UCN 650 → 325 (50% of original)
  Day 120: UCN 650 → 163 (25% of original)
  Day 365: UCN 650 → 7 (1% of original)

Trait: Current Mood
  Half-Life: 7 days
  Day 7: UCN 650 → 325 (50% of original)
  Day 14: UCN 650 → 163 (25% of original)
  Day 30: UCN 650 → 16 (2.5% of original)
```

---

## Gates & Milestones

### Feature Unlocking Flow

```
User's RR Journey:

RR 25: ┌─────────────────────────┐
       │  ✓ Milestone: Great Start!
       │  Features: Basic profile
       └─────────────────────────┘

RR 50: ┌─────────────────────────┐
       │  ✓ Milestone: Halfway There!
       │  ✓ Gate: Basic Features
       │  Features: Standard functionality
       └─────────────────────────┘

RR 70: ┌─────────────────────────┐
       │  ✓ Gate: Reliable Coaching
       │  Features: AI coaches enabled
       │           Personalized advice
       └─────────────────────────┘

RR 75: ┌─────────────────────────┐
       │  ✓ Milestone: Well-Refined!
       └─────────────────────────┘

RR 85: ┌─────────────────────────┐
       │  ✓ Gate: Advanced Personalization
       │  Features: Enhanced recommendations
       │           Predictive insights
       └─────────────────────────┘

RR 90: ┌─────────────────────────┐
       │  ✓ Milestone: Exceptional!
       └─────────────────────────┘

RR 98: ┌─────────────────────────┐
       │  ✓ Milestone: Elite Refinement!
       │  ✓ Gate: Sensitive DNA Unlock
       │  Features: SexDNA
       │           FinanceDNA (genetic)
       │           Advanced analytics
       └─────────────────────────┘
```

---

## Component Dependencies

```
┌─────────────────────────────────────────────────────────┐
│                   Configuration Files                    │
│  • evidence_weights.yaml                                │
│  • decay_defaults.yaml                                  │
│  • thresholds.yaml                                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│                    Core Components                       │
│                                                          │
│  DecayEngine ──────┐                                    │
│                    │                                     │
│  EvidenceWeighting ├──► UCNCalculator ──┐              │
│                    │                     │              │
│  ContradictionHandler ─┘                 │              │
│                                          │              │
│  ProvenanceLogger ───────────────────────┤              │
│                                          │              │
│                                          ▼              │
│                                   RRCalculator          │
│                                          │              │
│                                          ▼              │
│                                   CuriosityEngine       │
│                                          │              │
└──────────────────────────────────────────┼──────────────┘
                                           │
                                           ▼
                              ┌────────────────────────┐
                              │     Explorer API       │
                              │  (Future Integration)  │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │     Head Coach         │
                              │  (Future Integration)  │
                              └────────────────────────┘
```

---

## Data Flow

```
┌──────────────────────┐
│  observations.json   │
│  (Raw observations)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  calculate_ucn_for_user.py           │
│  1. Load observations                │
│  2. Convert to EvidenceSource        │
│  3. Calculate UCN for each trait     │
│  4. Calculate RR                     │
│  5. Generate Curiosity signals       │
└──────────┬───────────────────────────┘
           │
           ├─────────────────────────────┐
           │                             │
           ▼                             ▼
┌──────────────────────┐    ┌──────────────────────┐
│  ucn_report.json     │    │  provenance/hot/     │
│  (UCN/RR summary)    │    │  (Audit trail)       │
│  • RR: 73.25         │    │  • All attempts      │
│  • Avg UCN: 593.66   │    │  • Success/failure   │
│  • Curiosity: 26.75  │    │  • User behavior     │
│  • Per-trait UCNs    │    │  • Evidence quality  │
│  • Top priorities    │    │  • Timestamps        │
└──────────────────────┘    └──────────────────────┘
```

---

## Integration Points

### Current State

```
User Data                UCN/RR Engine           Output
─────────────────────────────────────────────────────────
observations.json   →    calculate_ucn_for_user.py
                    →    UCNCalculator              → ucn_report.json
                    →    RRCalculator               → provenance logs
                    →    CuriosityEngine            → console output
```

### Future State (Phase 2)

```
User Data                Core                    Explorer              Head Coach
────────────────────────────────────────────────────────────────────────────────
observations.json   →    Evidence Loading    →   UCN/RR Signals   →   Planning
photos             →    UCNCalculator        →   RR: 73.25        →   Actions
third-party        →    RRCalculator         →   Curiosity: 26.75 →   Priorities
sensors            →    ProvenanceLogger     →   Top Priorities   →   Execution
                   →                         →   Contradictions   →   Resolution
                                                                  →   Feedback
                                                                      Loop ↺
```

---

## Performance Characteristics

```
Operation                    Time        Scalability
────────────────────────────────────────────────────
UCN per trait (1 source)     < 1ms       ✓ Unlimited traits
UCN per trait (10 sources)   < 5ms       ✓ Unlimited evidence
RR calculation               < 10ms      ✓ 10,000+ users
Curiosity signals            < 5ms       ✓ 100+ traits
Provenance logging           < 1ms       ✓ Tiered storage
Full user calculation        < 100ms     ✓ 68+ traits tested
```

---

## Key Principles

### 1. Confidence Decays, Not Traits

```
Wrong:  Trait value changes over time
        "Dark Brown" → "Light Brown" → "Brown"

Right:  Confidence in trait value decays over time
        "Dark Brown" (UCN 650 → 400 → 200)
        Value stays "Dark Brown" until new evidence
```

### 2. Quality Over Quantity

```
User A: 50 traits, avg UCN 593  →  RR 73.25
User B: 68 traits, avg UCN 541  →  RR 60.89

User A has FEWER traits but HIGHER RR
Quality (avg UCN) matters more than quantity
```

### 3. Hold Contradictions in Tension

```
Don't:  Force immediate resolution
        Pick one value, discard the other

Do:     Lower UCN, raise Curiosity
        Hold both values
        Flag for Head Coach
        Let Head Coach decide WHEN to resolve
```

### 4. User Well-Being First

```
System needs: Resolve contradiction, get fresh evidence
User state:   Busy, stressed, not engaged

Head Coach:   Wait for natural opportunity
              Don't spam user with requests
              Balance system improvement with user experience
```

---

## Summary

The UCN/RR Calculation Engine provides:

✅ **Confidence Assessment** (UCN 0-1000)
✅ **Profile Ranking** (RR 0-100 percentile)
✅ **Curiosity Signals** (Curiosity = 100 - RR)
✅ **Evidence Weighting** (12 source types, quality multipliers)
✅ **Adaptive Decay** (permanent to 7 days, learns over time)
✅ **Contradiction Handling** (detect, penalize, hold in tension)
✅ **Complete Provenance** (all attempts tracked)

**Result**: A production-ready intelligence layer that drives curiosity-based profile refinement while respecting user well-being.
