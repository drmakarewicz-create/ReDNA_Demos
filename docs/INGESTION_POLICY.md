# Ingestion Policy Layer

Phase 4a introduces a deterministic policy layer that governs how raw evidence is retained, how conflicts are resolved, and how supersession events are logged.

## Evidence Tiering

Every canonical evidence record flows through `ReDNACoreDemo/core/ingest/policy.py::should_persist_raw`. The policy combines:

- **Source reliability** (`photo`, `external`, `coach`, `chat`, …)
- **Trait importance** (via `trait_importance_for`)
- **Recency / novelty** (ISO timestamp, comparison with the latest value)
- **Conflict impact** (does the new value contradict the current snapshot?)

The function returns `{tier, ttl_days, reason, reliability, conflict}`. Tiers map to retention windows:

| Tier | Description | TTL |
|------|-------------|-----|
| `hot`  | High-signal or conflicting evidence. Logged and persisted for a year. | 365 days |
| `warm` | Normal evidence with moderate importance/reliability. | 180 days |
| `cold` | Low-priority or redundant data. | 60 days |
| `drop` | Aged or redundant evidence that should not be persisted (still used for resolution). | 0 days |

Each decision is appended to `~/.redna/logs/evidence.log` (JSONL) and surfaced via `/metrics` as `policy.tier.*` counters.

## Supersession & Contradiction Handling

`apply_supersession()` compares the prior resolved trait entry with the new evidence and returns a `SupersessionDecision`:

- `action`: `new`, `contradiction`, `superseded`, or `reinforced`
- `new_status`: `stable`, `warming`, `contradicted`, or `superseded`
- `ucn_multiplier`: dampens confidence until confirmation
- `history_entry`: historical snapshot of the superseded value
- `context`: metadata for logging/metrics

Resolver integration automatically:

1. Appends the decision to `~/.redna/logs/supersession.log`
2. Emits `supersession_event` lines to the unified stack log (with `user_id`, `trait_id`, `action`, `ucn_delta`, etc.)
3. Updates `resolved.json` with the new schema:
   ```json
   {
     "value": {"enum": "green"},
     "ucn": 0.42,
     "status": "superseded",
     "last_updated": "2025-10-15T19:21:04Z",
     "last_confirmed_at": "2025-10-15T19:21:04Z",
     "history": [
       {
         "value": {"enum": "blue"},
         "status": "superseded",
         "timestamp": "2025-10-15T19:21:04Z",
         "previous_status": "stable",
         "action": "superseded"
       }
     ]
   }
   ```

### Example: Blue → Green Eyes

1. **Initial evidence** (`blue`, chat) → status `stable`, UCN ≈ 0.35.
2. **Conflicting chat report** (`green`, low reliability) → new value stored with status `contradicted`, UCN dampened; history records the blue value as supersession candidate.
3. **Photo confirmation** (`green`, high reliability) → status becomes `superseded`; history marks the blue entry as superseded; counters increment `policy.supersessions`.
4. **Future corroboration** with matching value will move status back to `stable` and bump confidence.

## Metrics & Observability

The policy layer increments new counters exposed via `/metrics`:

- `policy.supersessions`
- `policy.contradictions`
- `policy.tier.hot`, `.warm`, `.cold`, `.drop`

Smoke/resilience flows are unchanged; readiness stays green because rolling metrics are unaffected.

## Compatibility

`read_user_state()` migrates existing `resolved.json` files on load, adding default `status`, `last_confirmed_at`, and `history` fields so older data remains valid.

Log files live under `~/.redna/logs/` and can be tailed via `scripts/tail_logs.sh`.
