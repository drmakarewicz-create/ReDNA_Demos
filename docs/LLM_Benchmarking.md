# LLM Benchmarking Guide

**Version**: 1.0
**Last Updated**: 2025-10-16
**Purpose**: Document the Alt-LLM benchmark system for safely comparing local vs. external LLM extraction performance

---

## Overview

The ReDNA system uses **Ollama (llama3.1:8b)** for local, privacy-preserving extraction. However, we maintain a **benchmark backlog** of test cases that we believe would improve with more capable LLMs (GPT-4o-mini, Claude 3.5 Sonnet).

This system provides:
1. **Persistent backlog** ([AltLLM_Benchmark_Backlog.md](AltLLM_Benchmark_Backlog.md)) - Append-only list of test cases
2. **Batch runner** ([run_alt_llm_benchmark.py](../scripts/run_alt_llm_benchmark.py)) - Safe toggle to external LLM for benchmarking
3. **Cost controls** - Hard ceiling on spend, dry-run mode, automatic revert

---

## Quick Start

### Prerequisites

1. **API Key** (for external LLM):
   ```bash
   # For OpenAI
   export OPENAI_API_KEY=sk-...

   # For Anthropic
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **Core service running**:
   ```bash
   # Check Core health
   curl http://127.0.0.1:8001/health
   ```

### Running a Batch Test

```bash
# Activate Python environment
source .venv/bin/activate

# Dry run (no LLM calls, no cost)
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 20 \
  --max_cost_usd 1.00 \
  --dry_run

# Actual run (will make LLM calls)
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 20 \
  --max_cost_usd 1.00
```

### Command-Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--provider` | ✅ Yes | - | LLM provider (`openai` or `anthropic`) |
| `--model` | ✅ Yes | - | Model name (e.g., `gpt-4o-mini`) |
| `--limit` | No | 25 | Number of cases to run |
| `--max_cost_usd` | No | 2.00 | Hard cost ceiling (stop if exceeded) |
| `--dry_run` | No | False | Print plan without making LLM calls |

---

## How It Works

### 1. Configuration Storage
The runner stores your current UCNRR config (Ollama settings) before toggling:
```python
stored_config = {
    "UCNRR_LLM_PROVIDER": "ollama",
    "UCNRR_LLM_MODEL": "llama3.1:8b",
    # ... other vars
}
```

### 2. Temporary Toggle
Switches to external LLM **only for the batch run**:
```python
os.environ["UCNRR_LLM_PROVIDER"] = "openai"
os.environ["UCNRR_LLM_MODEL"] = "gpt-4o-mini"
# Batch test runs here
```

### 3. Automatic Revert
**Always reverts** to Ollama after completion (even on error):
```python
finally:
    revert_ucnrr_config(stored_config)
    print("✅ Reverted UCNRR to local Ollama configuration")
```

### 4. Safety Switches

**Cost Ceiling**:
- Stops immediately if `total_cost >= max_cost_usd`
- Estimates cost before each call using provider rate tables

**Error Handling**:
- Stops after 3 consecutive hard errors
- Reports partial results even on early stop

**Dry Run**:
- Use `--dry_run` to validate plan without spending

---

## Reading the Report

After a batch run, a dated report is saved to `docs/reports/altllm_batch_<timestamp>.md`.

### Key Sections

#### 1. Summary Metrics
Overall precision, recall, F1 across all cases:
```markdown
| Metric | Value | Target |
|--------|-------|--------|
| **Precision** | 95.24% | ≥ 95% |
| **Recall** | 78.57% | ≥ 85% |
| **F1 Score** | 86.09% | - |
```

#### 2. Category Breakdown
Performance by test category (direct_fact, behavior, etc.):
```markdown
| Category | Cases | Precision | Recall | F1 | TP | FP | FN |
|----------|-------|-----------|--------|----|----|----|----|
| direct_fact | 8 | 100.0% | 85.7% | 92.3% | 6 | 0 | 1 |
```

#### 3. Case-Level Results
Detailed pass/fail for each test case:
```markdown
### 1. ✅ direct_fact_001 (direct_fact)

**User Message**: "I am 6 feet tall"

- **Expected**: PaDNA.BodyDNA.Height
- **Extracted**: PaDNA.BodyDNA.Height
- **Correct (TP)**: PaDNA.BodyDNA.Height
- **Cost**: $0.0002
```

**Failure Example**:
```markdown
### 5. ❌ behavior_003 (behavior)

**User Message**: "I usually stay in and read on weekends"

- **Expected**: BehaviorDNA.Leisure.Indoor, PreferenceDNA.Social.GroupSize
- **Extracted**: BehaviorDNA.Leisure.Indoor
- **Correct (TP)**: BehaviorDNA.Leisure.Indoor
- **Missing (FN)**: PreferenceDNA.Social.GroupSize
- **Cost**: $0.0002
```

---

## Adding a New Benchmark Case

When you identify a failure from baseline tests or production logs:

### 1. Create Minimal Test Case
- **Single utterance** (no multi-turn context)
- **Clear expected traits** (canonical IDs only)
- **No confounders** (avoid mixing unrelated signals)

### 2. Add to Markdown Backlog
Edit [docs/AltLLM_Benchmark_Backlog.md](AltLLM_Benchmark_Backlog.md):

```markdown
| **new_case_id** | category | "User message" | ExpectedTrait1, ExpectedTrait2 | value1, value2 | Notes about edge case | med | ❌ 0/2 | - | - | - | - |
```

**Columns**:
- **ID**: Unique stable key (e.g., `behavior_009`)
- **Category**: `direct_fact`, `behavior`, `indirect_signal`, `preference`, `ambiguous`, `multi_trait`, `edge_case`, `conversational`, `correction`
- **User Message**: Exact utterance
- **Expected Trait IDs**: Comma-separated canonical IDs
- **Expected Values**: Comma-separated values (or `-` if N/A)
- **Notes**: Edge case description, normalization hints
- **Risk**: `low`/`med`/`high` (for FP potential)
- **Score (Local)**: Result from local LLM (✅ N/M, ❌ 0/M, ⚠️ partial)
- **Score (Alt)**: Result from alt LLM (filled after batch run)
- **Last Run**: ISO timestamp (filled after batch run)
- **Model**: Model used (filled after batch run)
- **Cost**: Estimated cost (filled after batch run)

### 3. Add to JSON Seed
Edit [tests/llm_benchmarks/backlog_seed.json](../tests/llm_benchmarks/backlog_seed.json):

```json
{
  "id": "behavior_009",
  "category": "behavior",
  "user_message": "I always drink water first thing in the morning",
  "expected_trait_ids": ["BehaviorDNA.Routine.Morning", "BehaviorDNA.Health.Hydration"],
  "expected_values": ["hydration", "high"],
  "notes": "Morning routine + health behavior inference",
  "risk": "med"
}
```

### 4. Update Change Log
Add entry to the **Change Log** section in the markdown:

```markdown
### 2025-10-17 — Added behavior_009
- **Author**: Your Name
- **Source**: Baseline report iteration 3
- **Reason**: Local LLM failed to extract morning routine from hydration statement
```

---

## Cost Estimation Reference

The batch runner uses these rate tables (as of 2025-10-16):

| Provider | Model | Input ($/1M tokens) | Output ($/1M tokens) | Avg cost/case |
|----------|-------|---------------------|----------------------|---------------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | ~$0.0002 |
| OpenAI | gpt-4o | $5.00 | $15.00 | ~$0.005 |
| Anthropic | claude-3-5-sonnet-20241022 | $3.00 | $15.00 | ~$0.004 |
| Anthropic | claude-3-5-haiku-20241022 | $1.00 | $5.00 | ~$0.0015 |

**Assumptions**:
- ~200 input tokens per case (HC prompt + user message)
- ~100 output tokens per case (extraction response)
- Actual costs may vary based on extraction complexity

**Example Runs**:
- 20 cases with `gpt-4o-mini`: **~$0.04**
- 50 cases with `gpt-4o-mini`: **~$0.10**
- 20 cases with `claude-3-5-sonnet`: **~$0.08**
- 100 cases with `gpt-4o`: **~$0.50**

---

## Safety Checklist

Before running a batch test:

- [ ] **API key is set** (check `echo $OPENAI_API_KEY` or `echo $ANTHROPIC_API_KEY`)
- [ ] **Core service is running** (check `curl http://127.0.0.1:8001/health`)
- [ ] **Cost limit is reasonable** (default $2.00 is safe for 100-1000 cases with gpt-4o-mini)
- [ ] **Dry run first** (validate plan: `--dry_run`)
- [ ] **Review backlog** (ensure cases are relevant and up-to-date)

After running:

- [ ] **Verify revert** (check env: `echo $UCNRR_LLM_PROVIDER` should be empty or `ollama`)
- [ ] **Review report** (check `docs/reports/altllm_batch_*.md`)
- [ ] **Update backlog** (fill in alt-LLM scores in markdown table)
- [ ] **Commit changes** (if adding new cases or updating scores)

---

## Troubleshooting

### "API key not found"
```bash
# Ensure key is exported
export OPENAI_API_KEY=sk-...
# Verify
echo $OPENAI_API_KEY
```

### "Core service not responding"
```bash
# Check Core health
curl http://127.0.0.1:8001/health

# Restart Core if needed
cd /path/to/ReDNA_Demos
source .venv/bin/activate
# ... start Core service
```

### "Cost exceeds limit"
```bash
# Reduce number of cases
python scripts/run_alt_llm_benchmark.py ... --limit 10

# Or increase cost ceiling
python scripts/run_alt_llm_benchmark.py ... --max_cost_usd 5.00
```

### "3 consecutive errors"
- Check API key validity
- Check provider status (OpenAI/Anthropic may have outages)
- Review Core logs for ingestion errors
- Try with smaller `--limit` first

---

## Best Practices

### When to Run Batch Tests

1. **After baseline iteration** - Validate that system architecture is sound
2. **Before major LLM upgrade** - Quantify improvement potential
3. **After prompt changes** - Compare local vs. external LLM response to new prompts
4. **Quarterly checkpoints** - Track how local LLM is improving over time

### Choosing Test Cases

**High Priority**:
- Direct facts that local LLM fails (demographics, physical traits)
- Behavioral inferences that require nuance
- Negative controls (phatic/conversational - should NOT extract)

**Medium Priority**:
- Edge cases (metric conversions, age ranges)
- Indirect signals (inference from context)
- Qualified facts (hedged language)

**Low Priority**:
- Cases that local LLM already handles well
- Overly complex multi-trait statements (harder to debug)

### Interpreting Results

**Local LLM is good enough if**:
- Alt-LLM only improves recall by <10%
- Precision is already ≥95%
- Cost of switching outweighs marginal benefit

**Consider external LLM if**:
- Alt-LLM achieves recall ≥85% while local is <50%
- Critical demographics/behaviors are consistently missed
- False positives are costing user trust

---

## Example Workflow

### Scenario: Validate System After Prompt Update

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Run dry run to check plan
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 30 \
  --max_cost_usd 1.00 \
  --dry_run

# Output:
# 📊 Loading benchmark cases (limit: 30)...
# ✅ Loaded 30 cases
# 💰 Estimated cost: $0.0060
# 🔍 DRY RUN - Plan:
#    Provider: openai
#    Model: gpt-4o-mini
#    Cases: 30
#    Estimated cost: $0.0060
#    Cost limit: $1.00
# ✅ Dry run complete - no LLM calls made

# 3. Run actual batch
python scripts/run_alt_llm_benchmark.py \
  --provider openai \
  --model gpt-4o-mini \
  --limit 30 \
  --max_cost_usd 1.00

# 4. Review report
cat docs/reports/altllm_batch_20251016_195530.md

# 5. Update backlog with results
# Edit docs/AltLLM_Benchmark_Backlog.md to fill in alt-LLM scores

# 6. Commit if adding new cases
git add docs/AltLLM_Benchmark_Backlog.md tests/llm_benchmarks/backlog_seed.json
git commit -m "Update alt-LLM benchmark results (gpt-4o-mini)"
```

---

## FAQ

**Q: Will this change my production LLM config?**

No. The runner only modifies environment variables temporarily in the script process. Original config is restored immediately after the run (even on error).

**Q: Can I run this on CI/CD?**

Yes, but you'll need to:
1. Store API keys as CI secrets
2. Set `--max_cost_usd` conservatively
3. Use `--dry_run` for PRs (only run actual tests on main branch)

**Q: How do I compare two external LLMs?**

Run the batch twice with different providers/models:
```bash
# Run with GPT-4o-mini
python scripts/run_alt_llm_benchmark.py --provider openai --model gpt-4o-mini --limit 20

# Run with Claude 3.5 Sonnet
python scripts/run_alt_llm_benchmark.py --provider anthropic --model claude-3-5-sonnet-20241022 --limit 20

# Compare the two reports
diff docs/reports/altllm_batch_*.md
```

**Q: What if I want to test a new model not in the rate table?**

Edit `RATE_TABLES` in `scripts/run_alt_llm_benchmark.py` to add your model's pricing. If unknown, cost will be estimated as $0.00 (you'll still get P/R metrics).

---

## Security & Privacy

**API Keys**:
- Never commit API keys to git
- Use environment variables only
- Rotate keys regularly

**Test Data**:
- All test cases are synthetic/public (no user PII)
- If adding production failures, sanitize messages first
- Review backlog before sharing externally

**Cost Control**:
- Always set `--max_cost_usd` conservatively
- Monitor actual spend in provider dashboard
- Use `--dry_run` first for new models/providers

---

*For questions or issues, see [AltLLM_Benchmark_Backlog.md](AltLLM_Benchmark_Backlog.md) or contact the ReDNA team.*
