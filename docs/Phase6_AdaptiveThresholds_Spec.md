# Phase 6 – Stage 2: Adaptive Thresholds (MVP)

## Overview
Adaptive thresholds replace static `RR_PROMOTE_MIN_*` gates with a lightweight learner that shifts promotion cutoffs based on recent outcomes. The system maintains precision safeguards (±100 RR clamp, hard env overrides, kill switch) while allowing controlled adaptation.

## Data Capture
- Every promotion decision writes a JSON line to `~/.redna/policy/promotion_history.jsonl`.
- Schema:
```json
{
  "ts": "2025-10-18T01:23:45Z",
  "user_id": "dbg",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "decision": "promote",
  "rr": 720.0,
  "base_rr": 780.0,
  "effective_rr": 730.0,
  "curiosity": 0.16,
  "value": "morning",
  "why": "Matched 'morning person' and 'before sunrise'",
  "reason": "promotion",
  "source": "ucnrr_rescore",
  "event_id": "text_1729211023000"
}
```
- A concise textual line is mirrored to `~/.redna/logs/policy.log`, e.g.
```
policy_decision trait=BehaviorDNA.Sleep.Chronotype rr=720.0 base=780.0 effective=730.0 curiosity=0.16 decision=promote
```

## Learner
- Prior mean: current env threshold (`RR_PROMOTE_MIN_*`).
- Evidence window: last `N` decisions per trait (`POLICY_LEARNER_WINDOW`, default 100).
- Update rule (per record):
  - Curiosity in [0,1] → `alpha = clamp(0.02, 0.15, 0.05 + 0.10 * curiosity)`.
  - Promotions: `learned_rr = (1 - alpha) * learned_rr + alpha * observed_rr`.
  - Skips above base: nudge upward via `learned_rr += alpha * 0.5 * (observed_rr - base_rr)`.
- Clamp final `learned_rr` to `[base_rr - 100, base_rr + 100]` and round to nearest 5.
- Results saved to `~/.redna/policy/learned_thresholds.json`.

## Serving Logic
- Effective threshold = learned value when `POLICY_LEARNER_ENABLED=true`; otherwise falls back to env.
- Promotion evaluation logs both base and effective thresholds and records the decision in history.

## API Surface
| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/core/api/policies` | Returns per-trait `{base_rr, learned_rr, sample_size, last_update, last_alpha}` plus learner status. |
| `POST` | `/core/api/learn_thresholds` | Runs learner pass, updates in-memory thresholds, persists to disk, logs `policy_learn_update`. |
| `GET` | `/core/api/debug/thresholds` | Raw JSON view of learned thresholds (debug). |

## Kill Switch & Controls
- `POLICY_LEARNER_ENABLED=false` disables serving of learned thresholds (base thresholds remain authoritative).
- `POLICY_LEARNER_WINDOW` tunes evidence window.
- Setting env toggles (`PROMOTE_ENABLE_*`, `RR_PROMOTE_MIN_*`) still overrides availability and priors.

## Failure / Rollback
- Set `POLICY_LEARNER_ENABLED=false` and rerun `/core/api/learn_thresholds` to restart with base priors.
- Delete `learned_thresholds.json` to reset learned state; next learner run rebuilds from history.
- Logs and history provide audit trail for manual inspection.

## Example Before/After
```
Base rr: 780
Recent promotions (rr=720–735, curiosity≈0.2) → learned rr ≈ 730
Effective threshold used during promotion: 730
```
Promotions at 720 now clear the gate while base policy remains visible for diagnostics.
