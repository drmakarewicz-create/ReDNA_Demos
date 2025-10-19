# Curiosity Queue Design (Phase 6 · Stage 3)

## Purpose
- Convert uncertain promotions into actionable follow-up prompts.
- Capture low-confidence and contradictory evidence so Northstar can ask clarifying questions.
- Maintain precision: promotions remain untouched; curiosity items are additive diagnostics.

## Data Model
- `CuriosityItem` (pydantic) lives in `ReDNACoreDemo/core/curiosity/models.py`.
- Key fields: `id`, `user_id`, `trait_id`, `reason_code`, `inputs` (rr/base_rr/learned_rr/p/curiosity/impact_weight), `expected_information_gain` (0–1), `cooldown_key`, lifecycle timestamps (`asked_at`, `answered_at`, etc.).
- `ReasonCode` = `low_confidence`, `schema_repair_low_conf`, `value_missing`, `contradiction`, `novel_signal`, `policy_borderline`.

## Storage & Ranking
- Backed by `curiosity.jsonl` per user (`data/users/<user>/curiosity.jsonl`).
- Store helpers (`ReDNACoreDemo/core/curiosity/store.py`):
  - `enqueue`, `list_items`, `ack`, `answer`, `dismiss`, `ttl_cleanup`.
  - In-memory caches keep an updated priority view for queued items.
  - Expiration (TTL) marks items `expired` when `expires_at` < now.
- Information gain recalculates on every list:
  - `uncertainty`: derived from probability (default RR proximity when absent).
  - `impact_weight`: per-trait prior (`CURIOSITY_TRAIT_WEIGHTS`).
  - `recency`: exponential decay (`exp(-age_hours / 168)`).
  - `reason_multiplier`: contradiction > novel_signal > borderline > …
  - `IG = clip01(uncertainty * impact_weight * recency * reason_multiplier)`.

## Autop Enqueue Triggers (promotion loop)
- `low_confidence`: probability in [0.4, 0.6].
- `policy_borderline`: RR within ±`CURIOSITY_NEAR_THRESHOLD_DELTA` (default 20) of learned threshold.
- `value_missing`: policy requires value but normalization failed.
- `schema_repair_low_conf`: UCNRR flagged repair with low confidence.
- `contradiction`: flipping trait value vs existing resolved entry.
- `novel_signal`: new trait surfaced with no prior record or explicit hint.
- Dedupe & limits: enforced via store (`cooldown_sec` default 7 days, max open per trait=2, per user=20).

## API Surface
| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/core/api/curiosity/enqueue` | Accepts full `CuriosityItem` or {user, trait, reason, inputs}. Returns enqueued item or 409 if deduped. |
| `GET` | `/core/api/curiosity` | Params: `user_id`, optional `status`, `limit`, `min_information_gain`. Sorted by fresh IG. |
| `POST` | `/core/api/curiosity/{id}/ack` | Marks `asked` (records `asked_at`). |
| `POST` | `/core/api/curiosity/{id}/answer` | Marks `answered`, stores text, triggers ingest for re-evaluation (`source="curiosity_answer"`). |
| `POST` | `/core/api/curiosity/{id}/dismiss` | Marks `dismissed` with optional reason. |

## Logging & Telemetry
- `curiosity_enqueue`, `curiosity_ack`, `curiosity_answer`, `curiosity_dismiss` emitted via `stack_log`.
- Stored JSONL history plus FastAPI responses expose lifecycle for DevX tooling.

## Guardrails & Environment
- `ENABLE_CURIOSITY_LOOP` (default `true`) toggles entire feature.
- `CURIOSITY_COOLDOWN_SEC`, `CURIOSITY_MAX_OPEN_PER_USER`, `CURIOSITY_MAX_OPEN_PER_TRAIT`, `CURIOSITY_DEFAULT_TTL_DAYS`, `CURIOSITY_NEAR_THRESHOLD_DELTA` configurable via env.
- Promotions remain unchanged—curiosity only adds follow-up metadata.

## Future Work
- Personalized question styles (gentle/direct/playful) driven by persona.
- Multi-turn curiosity trees and sequencing.
- Sync curiosity queue with Northstar UI acknowledgement states.
- Adaptive cooldowns per trait / per user.
