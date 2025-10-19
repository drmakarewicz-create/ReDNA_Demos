# Alt-LLM Benchmark Backlog

**Version**: 1.0
**Last Updated**: 2025-10-16
**Maintained By**: Claude (via automated failure analysis)

---

## Purpose & Scope

This document maintains a **durable, versioned backlog** of test cases that we believe would improve with a more capable LLM (e.g., GPT-4o-mini, Claude 3.5 Sonnet) compared to the local Ollama llama3.1:8b model.

### What "Alt-LLM" Means
- **Primary LLM**: Ollama llama3.1:8b (local, free, privacy-preserving)
- **Alt-LLM**: External commercial models (OpenAI, Anthropic) used for **benchmarking only**
- **Use Case**: Validate that system architecture is sound; identify LLM capability gaps

### Scope
- This backlog is **append-only** — cases are added from failure analysis but never removed
- Each case is a **minimal, single-utterance** test with clear expected traits
- All tests run through the **normal Core ingestion pipeline** (snapshot.traits only)
- Results are compared at **snapshot level** (UI-visible traits), not internal evidence

### Maintenance Rules
1. Add new cases after each baseline run or production failure analysis
2. Always log: date, model used, cost estimate, P/R scores
3. Never commit API keys or secrets to this file
4. Update `score_last_local` and `score_last_alt` when running batch tests

---

## Benchmark Cases

| ID | Category | User Message | Expected Trait IDs | Expected Values | Notes | Risk | Score (Local) | Score (Alt) | Last Run | Model | Cost (USD) |
|----|----------|--------------|-------------------|-----------------|-------|------|---------------|-------------|----------|-------|------------|
| **direct_fact_001** | direct_fact | "I am 6 feet tall" | PaDNA.BodyDNA.Height | 6 feet | Simple height statement | low | ❌ 0/1 | - | - | - | - |
| **direct_fact_004** | direct_fact | "I'm 30 years old" | BasicDNA.Age | 30 | Age with number | low | ❌ 0/1 | - | - | - | - |
| **direct_fact_005** | direct_fact | "I'm a woman" | BasicDNA.Gender | female | Gender identity | low | ❌ 0/1 | - | - | - | - |
| **direct_fact_006** | direct_fact | "I live in San Francisco" | BasicDNA.Location.City | San Francisco | City location | low | ❌ 0/1 | - | - | - | - |
| **direct_fact_007** | direct_fact | "I work as a software engineer" | BasicDNA.Occupation | software engineer | Job title | low | ❌ 0/1 | - | - | - | - |
| **direct_fact_008** | direct_fact | "I'm married" | BasicDNA.RelationshipStatus | married | Relationship status | low | ✅ 1/1 | - | - | - | - |
| **direct_fact_002** | direct_fact | "I have blue eyes" | PaDNA.EyeDNA.IrisColor | blue | Eye color | low | ✅ 1/1 | - | - | - | - |
| **direct_fact_003** | direct_fact | "My hair is brown" | PaDNA.HairDNA.Color.Natural | brown | Hair color | low | ✅ 1/1 | - | - | - | - |
| **edge_case_001** | edge_case | "I'm 183 centimeters tall" | PaDNA.BodyDNA.Height | 183cm | Metric unit conversion | med | ❌ 0/1 | - | - | - | - |
| **edge_case_002** | edge_case | "I'm in my early 30s" | BasicDNA.Age | 30-34 | Age range vs exact | med | ✅ 1/1 | - | - | - | - |
| **edge_case_003** | edge_case | "I don't eat meat" | BehaviorDNA.Health.Diet | vegetarian | Implicit dietary restriction | med | ✅ 1/1 | - | - | - | - |
| **edge_case_004** | edge_case | "I'm usually up by 5:30 AM and in bed by 9 PM" | BehaviorDNA.Sleep.Chronotype, BehaviorDNA.Sleep.Duration | morning, 8.5hrs | Multi-trait from schedule | med | ⚠️ 1/2 | - | - | - | - |
| **behavior_001** | behavior | "I go hiking every weekend" | BehaviorDNA.Exercise.Outdoor, BehaviorDNA.Exercise.Frequency | hiking, weekly | Exercise behavior pair | low | ✅ 2/2 | - | - | - | - |
| **behavior_002** | behavior | "I'm a morning person" | BehaviorDNA.Sleep.Chronotype | morning | Chronotype self-report | low | ✅ 1/1 | - | - | - | - |
| **behavior_003** | behavior | "I usually stay in and read on weekends" | BehaviorDNA.Leisure.Indoor, PreferenceDNA.Social.GroupSize | true, small | Indoor + social inference | med | ❌ 0/2 | - | - | - | - |
| **behavior_004** | behavior | "I start work at 6 AM and finish by 2 PM" | BehaviorDNA.Schedule.WorkHours, BehaviorDNA.Sleep.Chronotype | 6AM-2PM, morning | Work schedule → chronotype | med | ❌ 0/2 (FP) | - | - | - | - |
| **behavior_005** | behavior | "I meal prep every Sunday for the week" | BehaviorDNA.Organization.Level, BehaviorDNA.Health.Diet | high, planned | Organization + diet | med | ❌ 0/2 | - | - | - | - |
| **behavior_006** | behavior | "I always reply to texts within an hour" | BehaviorDNA.Communication.ResponseStyle | prompt | Communication behavior | med | ❌ 0/1 | - | - | - | - |
| **behavior_007** | behavior | "I drink three cups of coffee every morning" | BehaviorDNA.Health.CaffeineIntake, BehaviorDNA.Routine.Morning | high, coffee | Caffeine + morning routine | med | ❌ 0/2 | - | - | - | - |
| **behavior_008** | behavior | "I learn best by doing hands-on projects" | BehaviorDNA.Learning.Style | kinesthetic | Learning preference | med | ❌ 0/1 | - | - | - | - |
| **indirect_001** | indirect_signal | "I take cold showers every morning" | BehaviorDNA.Wellness.ColdTherapy | daily | Wellness behavior | med | ❌ 0/1 | - | - | - | - |
| **indirect_002** | indirect_signal | "I work from home most days" | BehaviorDNA.Work.Location | remote | Work location inference | low | ✅ 1/1 | - | - | - | - |
| **indirect_003** | indirect_signal | "Ugh, it's raining again, I was hoping to go for a run" | BehaviorDNA.Exercise.Outdoor, BehaviorDNA.Exercise.Type | outdoor, running | Indirect exercise preference | high | ❌ 0/2 | - | - | - | - |
| **indirect_004** | indirect_signal | "Looking forward to a quiet weekend with no plans" | BehaviorDNA.Social.Style, PreferenceDNA.Social.GroupSize | introvert, solitary | Social style from context | high | ❌ 0/2 | - | - | - | - |
| **ambiguous_002** | ambiguous | "I'm pretty tall" | PaDNA.BodyDNA.Height | tall | Vague descriptor | med | ❌ 0/1 | - | - | - | - |
| **ambiguous_003** | ambiguous | "I'm in decent shape" | BehaviorDNA.Fitness.Level | moderate | Vague fitness level | med | ❌ 0/1 | - | - | - | - |
| **ambiguous_004** | ambiguous | "I'm an introvert but I like going to parties sometimes" | BehaviorDNA.Social.Style | ambivert | Conflicting signals | med | ❌ 0/1 | - | - | - | - |
| **preference_001** | preference | "I love pizza" | PreferenceDNA.Food.Pizza | true | Food preference | low | ✅ 1/1 | - | - | - | - |
| **preference_004** | preference | "I prefer backpacking over luxury hotels" | PreferenceDNA.Travel.Style | budget_adventure | Travel style contrast | med | ❌ 0/1 | - | - | - | - |
| **multi_trait_001** | multi_trait | "I'm a 30-year-old woman with brown hair and green eyes" | BasicDNA.Age, BasicDNA.Gender, PaDNA.HairDNA.Color.Natural, PaDNA.EyeDNA.IrisColor | 30, female, brown, green | 4 traits in one statement | low | ✅ 4/4 | - | - | - | - |
| **multi_trait_002** | multi_trait | "I have blue eyes, blonde hair, and I love hiking and pizza" | PaDNA.EyeDNA.IrisColor, PaDNA.HairDNA.Color.Natural, BehaviorDNA.Exercise.Outdoor, PreferenceDNA.Food.Pizza | blue, blonde, hiking, pizza | Physical + behavioral mix | low | ✅ 4/4 | - | - | - | - |
| **conversational_001** | conversational | "How are you doing today?" | (none) | - | Phatic greeting - NO extraction | high | ❌ 0/0 (FP) | - | - | - | - |
| **conversational_004** | conversational | "Got it, thanks!" | (none) | - | Acknowledgment - NO extraction | high | ❌ 0/0 (FP) | - | - | - | - |
| **correction_001** | correction | "Actually, I have brown eyes, not blue" | PaDNA.EyeDNA.IrisColor | brown | Correction/override signal | med | ✅ 1/1 | - | - | - | - |

### Score Legend
- **✅ N/M**: N correct extractions out of M expected
- **❌ 0/M**: Failed to extract any of M expected traits
- **⚠️ N/M**: Partial extraction (some traits missing)
- **(FP)**: False positive - extracted traits when none expected

---

## Change Log

### 2025-10-16 — Initial Backlog Creation (v1.0)
- **Author**: Claude
- **Source**: Iteration 0-2 baseline report (extraction_baseline.md)
- **Total Cases**: 34
- **Breakdown**:
  - Direct facts: 8 cases (5 failing on local)
  - Edge cases: 4 cases (2 failing, 1 partial)
  - Behaviors: 8 cases (6 failing)
  - Indirect signals: 4 cases (2 failing)
  - Ambiguous: 3 cases (3 failing)
  - Preferences: 2 cases (1 failing)
  - Multi-trait: 2 cases (2 passing - validates system works!)
  - Conversational: 2 cases (2 FP on local)
  - Corrections: 1 case (1 passing)
- **Local LLM Results**: P=89.47%, R=23.94% (Iteration 2)
- **Key Findings**:
  - System architecture is sound (multi-trait cases pass perfectly)
  - Local LLM struggles with: demographics, behavioral inference, vague descriptors
  - False positives on conversational/phatic inputs (Work.Location hallucination)

---

## Usage

### Running a Batch Test

```bash
source .venv/bin/activate
export OPENAI_API_KEY=***   # or ANTHROPIC_API_KEY

# Dry run (no LLM calls)
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 20 \
  --max_cost_usd 1.00 \
  --dry_run

# Actual run (will toggle UCNRR temporarily)
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 20 \
  --max_cost_usd 1.00
```

### Adding a New Case

1. Identify failure from baseline report or production logs
2. Create minimal test case (single utterance, clear expected traits)
3. Add row to table above with:
   - Unique ID (category_NNN)
   - Category, user message, expected trait IDs
   - Risk level (low/med/high for FP potential)
   - Initial score from local LLM
4. Add to `tests/llm_benchmarks/backlog_seed.json` for batch runner
5. Document in Change Log with date, source, and summary

---

## Cost Estimates (Batch Runner Rate Table)

| Provider | Model | Input ($/1M tokens) | Output ($/1M tokens) | Avg cost/case |
|----------|-------|---------------------|----------------------|---------------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | ~$0.002 |
| OpenAI | gpt-4o | $5.00 | $15.00 | ~$0.05 |
| Anthropic | claude-3-5-sonnet-20241022 | $3.00 | $15.00 | ~$0.04 |
| Anthropic | claude-3-5-haiku-20241022 | $1.00 | $5.00 | ~$0.015 |

**Note**: Estimates based on ~200 input tokens + ~100 output tokens per case (HC prompt + extraction response).

---

*End of Alt-LLM Benchmark Backlog v1.0*
