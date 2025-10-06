# Holistic Review Overview

The Core holistic review pass normalizes imported traits, backfills UCN/RR, and applies inference rules so Explorer surfaces stay consistent after every ingest.

## When it runs
- Automatic: `CORE_HOLISTIC_ON_INGEST=1` triggers a pass after `/ingest_from_ucnrr`, `/import/padna_json`, and `/recompute/{user_id}`.
- Manual: `POST /holistic/{user_id}` runs the same routine on demand.
- Control Panel+: toggle the feature, adjust the time budget, and launch a per-user run from the Holistic Controls panel.

## Time budget
`CORE_HOLISTIC_MAX_MS` (default 300) bounds the synchronous window. If the review exceeds the budget, Core marks the response with `"holistic": {"async": true}` and finishes persistence in the background.

## Outputs
Each pass writes a `last_holistic.json` snapshot under `data/storage/users/<user_id>/`. It contains:
- `counts`: adjustments, implied additions, and contradictions.
- `paths`: every trait touched (used by Explorer tables for badges).
- `implied_reasons`: rule → trait rationale for tooltips.

## Inference rules
Rules live in `data/config/inference_rules.yaml`. Update or add entries, then rerun Core to reload. Explorer tooltips surface the `reason` string from each rule.

## Manual workflow
1. Toggle holistic ingest in Control Panel+ if you want automatic passes.
2. Use `curl -X POST http://<core-host>:<port>/holistic/<user_id>` for ad-hoc reviews.
3. Explorer’s Head Coach tab surfaces a “Run Holistic Review” button (with dev-mode feedback) and badges after each automatic pass.

## Safety
- Existing trait provenance is preserved; the pass annotates `provenance.step = "core-holistic"` and notes any adjustments.
- RR/UCN floors prevent `RR=0` with a known value, and curiosity is clamped to `100 - RR`.
- Re-runs without new data are idempotent; counts fall back to zero when nothing changes.
