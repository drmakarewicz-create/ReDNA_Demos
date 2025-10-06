# Core AI Inference Notes

## Enabling

1. Ensure the shared LLM service (Ollama) is running and exposes the model you want (defaults are `llama` / `llama3:latest`).
2. Export the Core AI env flags before starting the Core service, or toggle them in Control Panel+:

```bash
export CORE_USE_LLM=true
# Optional overrides (otherwise the values fall back to the global LLM_* env vars)
export CORE_LLM_PROVIDER=llama
export CORE_LLM_MODEL="llama3:latest"
export CORE_LLM_BASE_URL="http://127.0.0.1:11434"
export CORE_LLM_API_KEY="dummy"
```

Restart Core so it picks up the new env values. `/health` will now report:

```json
{
  "core_ai_enabled": true,
  "core_ai_provider": "llama",
  "core_ai_model": "llama3:latest"
}
```

## Smoke Test

```bash
UCNRR=http://127.0.0.1:8011
CORE=http://127.0.0.1:8015
USER=core_ai_user

# 1. Create user (UCN/RR will nudge Core to create storage)
curl -s -X POST "$UCNRR/users/init" -H 'content-type: application/json' -d '{"username":"'$USER'"}' | jq

# 2. Send a single canonical trait via UCN/RR
curl -s -X POST "$UCNRR/ingest_text" -H 'content-type: application/json' \
  -d '{"user_id":"'$USER'","text":"My eyes are dark brown","lines":["PaDNA.HairDNA.Color=Red"],"provenance":{"actor":"user","source":"cli"}}' | jq

# Expect the response to include "changed_keys" from UCN/RR and, when enabled,
# "added_by_core_ai" for any additional traits Core inferred.

# 3. Inspect resolved traits – each trait now carries ucn (0-1000), rr, curiosity, and notes
curl -s "$CORE/resolved/$USER" | jq '.resolved'

# 4. Flat view with RR / Curiosity quick scan
curl -s "$CORE/resolved/flat/$USER" | jq -r '.rows[] | [.path,.ucn,.rr,.curiosity,.notes.summary] | @tsv'

# 5. Manual expansion (optional)
curl -s -X POST "$CORE/recompute/$USER" | jq
```

Success criteria:
- `/health` shows Core AI enabled and the RR engine metadata (sample size, baselines path).
- `/ingest_text` populates `ucn` (0–1000), `rr` (0–100), `curiosity = 100 - rr`, and `notes` for each changed trait.
- `/ingest_from_ucnrr` response includes `rr_curiosity_updated` plus any `added_by_core_ai` traits when the model is active.
- `/recompute/{user_id}` produces additional traits and keeps notes/rr fields in sync.

## UCN / RR / Curiosity pipeline

- **UCN** is calculated inside UCN/RR before publishing observations. Canonical lines arrive around 940–980, LLM inferences land in the 500–900 band, and heuristics sit lower. Each observation carries a short notes block (summary, evidence, instructions, gaps).
- **RR** is computed inside Core by comparing the user’s UCN with the population sample in `data/storage/_stats/trait_ucn.json`. When fewer than `CORE_RR_MIN_POINTS` peers exist, Core blends in draws from the baseline priors (`data/config/rr_baselines.yaml`).
- **Curiosity** is derived as `100 - RR`. Lower RR → higher curiosity. Deterministic notes explain what the Head Coach should do next even when Core-AI is disabled.
- Core persists the merged notes (UCN/RR + Core deterministic/AI) and timestamps every update in `resolved.json` and the flat cache.

The stats file and baselines can be inspected at runtime:

```bash
jq 'keys' ReDNACoreDemo/data/storage/_stats/trait_ucn.json
cat ReDNACoreDemo/data/config/rr_baselines.yaml
curl -s "$CORE/health" | jq '{rr_engine, rr_sample_size, rr_baselines_path, rr_baselines_loaded}'
```

The pipeline remains backward compatible — callers that omit the new env vars or run without the LLM continue to get deterministic Core behaviour.
