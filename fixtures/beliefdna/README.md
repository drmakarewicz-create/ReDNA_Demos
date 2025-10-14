# BeliefDNA Bundle System

Reuses the ChatDNA bundle schema/ingestion flow for BeliefDNA Coach persona bundles.

## Overview

The BeliefDNA bundle system allows you to:
1. **Define philosophical personas** with belief/value/cognitive trait bundles
2. **Ingest bundles** using the existing `ingest_style_bundle.py` script
3. **Render belief-based responses** via BeliefDNA Coach `/render` endpoint
4. **Evaluate stance consistency** using the evaluation harness
5. **Provide feedback** via `/feedback` endpoint with RR delta updates

## Directory Structure

```
fixtures/beliefdna/
├── personas/                  # Persona bundle files
│   ├── utilitarian.bundle.json
│   ├── virtue_ethics.bundle.json
│   └── deontological.bundle.json
├── prompts/                   # Evaluation prompts
│   └── stance_prompts.txt
└── README.md                  # This file

eval/beliefdna/
├── harness.py                 # Evaluation harness
└── results.md                 # Generated benchmark results
```

## Persona Bundles

### Structure

Each persona bundle follows the ChatDNA schema with BeliefDNA-specific paths:

```json
{
  "user_id": "persona_utilitarian",
  "profile": {
    "label": "Utilitarian Ethicist",
    "source": "Philosophical analysis of utilitarian thinkers",
    "note": "Prioritizes outcomes, greatest good for greatest number"
  },
  "paths": {
    "BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA": {
      "resolved_value": 85,
      "ucn": 900,
      "rr": 90,
      "curiosity": 10,
      "reasons": ["Strong emphasis on reducing suffering"],
      "provenance": {...}
    },
    "CogDNA.CognitiveStyleDNA.AnalyticalVsIntuitiveDNA": {
      "resolved_value": 85,
      "ucn": 880,
      "rr": 88,
      "curiosity": 12,
      "reasons": ["Highly analytical - weighs costs/benefits"],
      "provenance": {...}
    },
    "MotivationDNA.CoreValueDNA.AltruismDNA": {
      "resolved_value": 95,
      "ucn": 920,
      "rr": 92,
      "curiosity": 8,
      "reasons": ["Impartial concern for welfare of all"],
      "provenance": {...}
    }
  },
  "corpus_samples": [...]
}
```

### Available Personas

1. **Utilitarian** (`persona_utilitarian`)
   - High: CareFairness (90 RR), Altruism (92 RR), Analytical (88 RR)
   - Low: Authority (82 RR), Sanctity (85 RR), Loyalty (78 RR)
   - Philosophy: Consequentialism, greatest good for greatest number

2. **Virtue Ethics** (`persona_virtue_ethics`)
   - High: PersonalGrowth (90 RR), CommunityBelonging (85 RR), Conscientiousness (85 RR)
   - Moderate: All moral foundations balanced (65-75 RR)
   - Philosophy: Character-focused, eudaimonia, practical wisdom

3. **Deontological** (`persona_deontological`)
   - High: MoralIntegrity (95 RR), Conscientiousness (95 RR), CareFairness (92 RR)
   - High: AnalyticalVsIntuitive (90 RR), NeedForClosure (82 RR)
   - Philosophy: Duty-based, categorical imperative, rights and obligations

## Usage

### 1. Ingest Persona Bundles

```bash
# Dry run validation
python3 scripts/ingest_style_bundle.py fixtures/beliefdna/personas/utilitarian.bundle.json --dry-run

# Actual ingestion
python3 scripts/ingest_style_bundle.py fixtures/beliefdna/personas/utilitarian.bundle.json
python3 scripts/ingest_style_bundle.py fixtures/beliefdna/personas/virtue_ethics.bundle.json
python3 scripts/ingest_style_bundle.py fixtures/beliefdna/personas/deontological.bundle.json
```

**Output**:
```
📦 Loading bundle: Utilitarian Ethicist
   User ID: persona_utilitarian
   Source: Philosophical analysis of utilitarian thinkers
   Containers: 11
✅ Schema validation passed

📊 Summary:
   Total containers: 11
   Mean UCN: 801.8
   Mean RR: 80.2

   Top 5 high-confidence traits:
     • Altruism: 95 (UCN: 920, RR: 92.0)
     • CareFairness: 85 (UCN: 900, RR: 90.0)
     • AnalyticalVsIntuitive: 85 (UCN: 880, RR: 88.0)

✅ Ingested to: data/users/persona_utilitarian/resolved.json
```

### 2. Render Belief Responses

```bash
curl -X POST "http://127.0.0.1:8000/api/coach/beliefdna_coach/render" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "persona_utilitarian",
    "prompt": "Is lying ever morally acceptable?",
    "intent": "moral"
  }'
```

**Response**:
```json
{
  "output": "You'd likely approach this from a care/fairness perspective...",
  "reason_map": [
    {
      "trait": "BeliefValueDNA.MoralFoundationDNA.CareFairnessDNA",
      "rr": 90,
      "weight": 0.90,
      "influence": "Strong influence from your belief system (RR: 90)"
    }
  ],
  "similarity": {"overall": 0.74},
  "relevant_containers": [...],
  "rr_summary": {"BeliefValueDNA": 90, "CogDNA": 88}
}
```

### 3. Submit Feedback

```bash
curl -X POST "http://127.0.0.1:8000/api/coach/beliefdna_coach/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "persona_utilitarian",
    "prompt": "Is lying ever morally acceptable?",
    "output": "Yes, if it prevents greater harm",
    "user_rating": 5,
    "notes": "Very accurate"
  }'
```

**Rating Scale**:
- 1 star: -8 RR delta (very inaccurate)
- 2 stars: -4 RR delta
- 3 stars: 0 RR delta (neutral)
- 4 stars: +4 RR delta
- 5 stars: +8 RR delta (very accurate)

### 4. Run Evaluation Harness

```bash
# Evaluate all personas with 3 prompts
python3 eval/beliefdna/harness.py --limit 3

# Evaluate single persona
python3 eval/beliefdna/harness.py --persona persona_utilitarian --limit 10

# Full benchmark (57 prompts across 3 personas)
python3 eval/beliefdna/harness.py
```

**Output**: Generates `eval/beliefdna/results.md` with:
- Leaderboard table (ranked by mean similarity)
- Detailed metrics per persona
- Sample responses
- Success rates

## Evaluation Prompts

The `stance_prompts.txt` file contains 57 philosophical questions across categories:

- **Moral Foundations** (Care/Harm, Fairness, Liberty, Authority, Loyalty, Sanctity)
- **Ethical Frameworks** (Deontology vs Consequentialism, Virtue Ethics)
- **Meta-Ethics** (Moral realism, subjectivism, epistemic status)
- **Applied Ethics** (Trolley problems, animal rights, environment, technology)
- **Political Philosophy** (Democracy, rights, redistribution)
- **Existential Questions** (Meaning, free will, responsibility)

## Schema Validation

All bundles are validated against `fixtures/chatdna/schema/chatdna_style_bundle.schema.json`:

**Required fields**:
- `user_id`: Must match pattern `^persona_[a-z_]+$`
- `profile`: Label, source, optional note
- `paths`: Container paths with resolved_value, ucn, rr, curiosity, reasons, provenance

**Optional fields**:
- `version`: Trait version (e.g., ".v1")
- `status`: prototype | stable | deprecated
- `ai_upgradable`: Whether AI can refine via feedback
- `corpus_samples`: Text samples with embeddings for similarity

## Integration with BeliefDNA Coach

The ingested bundles populate the user's `resolved.json` with BeliefValueDNA, CogDNA, MotivationDNA, PsyDNA, and EmDNA traits. The BeliefDNA Coach service:

1. **Reads traits** from `resolved.json`
2. **Builds reason_map** showing which traits influenced the response
3. **Identifies relevant_containers** with similarity scores
4. **Calculates rr_summary** across namespaces
5. **Applies feedback deltas** to trait RR values based on user ratings

## CI/CD Integration

### Bundle Validation

Add to CI pipeline:

```yaml
- name: Validate BeliefDNA Bundles
  run: |
    for bundle in fixtures/beliefdna/personas/*.bundle.json; do
      python3 scripts/ingest_style_bundle.py "$bundle" --dry-run || exit 1
    done
```

### Mini Stance Benchmark

Add to CI pipeline:

```yaml
- name: Run BeliefDNA Stance Benchmark
  run: |
    python3 eval/beliefdna/harness.py --limit 5
    cat eval/beliefdna/results.md
```

## Future Enhancements

1. **LLM Integration**: Replace placeholder responses with actual GPT-4/Claude reasoning based on trait profiles
2. **Embedding-Based Similarity**: Use corpus_samples embeddings to calculate response similarity
3. **Stance Divergence Metrics**: Measure how much personas differ on controversial questions
4. **Temporal Consistency**: Track whether responses remain consistent over time
5. **Multi-Turn Dialogues**: Test consistency across follow-up questions
6. **Contradiction Detection**: Flag internal contradictions in belief systems

## Related Files

- [ADDING_NEW_COACH_PROTOCOL.md](../../docs/ADDING_NEW_COACH_PROTOCOL.md) - Protocol for adding coaches
- [BeliefDNA Coach Implementation Summary](../../ReDNACoreDemo/coaches/beliefdna_coach/IMPLEMENTATION_SUMMARY.md)
- [ChatDNA Bundle Schema](../chatdna/schema/chatdna_style_bundle.schema.json)
- [Bundle Ingestion Script](../../scripts/ingest_style_bundle.py)

---

**Status**: ✅ Complete
- Schema reuse: Working
- Ingestion: 3 personas successfully ingested
- Rendering: Endpoint functional (placeholder responses)
- Feedback: RR delta system implemented
- Evaluation: Harness complete with markdown reports
