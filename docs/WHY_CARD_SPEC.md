# Why-Card Pipeline (Phase 6 · Stage 1)

## Overview
- Why-Cards capture the rationale behind every successful promotion coming from UCNRR or Core.
- Each card is appended to `~/.redna/why_cards.jsonl` and logged as `promotion_whycard` via `stack_log`.
- Cards are exposed through two read APIs and power diagnostics for the Explorer stack.

## Card Schema
```json
{
  "user_id": "string",
  "trait_id": "string",
  "value": "string|null",
  "rr": 800.0,
  "why": "Matched phrase 'morning person' and 'before sunrise'",
  "ts": "2025-10-05T18:42:10.123456+00:00",
  "source": "ucnrr_rescore",
  "event_id": "text_1728153320000"
}
```

## Storage
- File: `~/.redna/why_cards.jsonl`
- Encoding: UTF-8, JSON per line, newest entries appended last
- Writes are synchronised through a module-level lock to avoid clobbering during bursts.

## Endpoints
| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/core/api/debug/set_toggle` | Live adjust `PROMOTE_ENABLE_*` or `RR_PROMOTE_MIN_*` env vars and reload promotion policies. |
| `GET` | `/core/api/traits/{trait_id}/why` | Returns the most recent Why-Card for a trait (optionally filtered by `user_id`, `limit`). |
| `GET` | `/core/api/whycards` | Lists recent Why-Cards, filterable by `user_id`, `trait_id`, `limit`. |

### `set_toggle` Payloads
```json
{"key": "PROMOTE_ENABLE_CHRONO", "value": true}
{"key": "RR_PROMOTE_MIN_CHRONO", "value": 780}
{"trait": "CHRONO", "enable": true, "rr_min": 780}
```
- Only `PROMOTE_ENABLE_*` and `RR_PROMOTE_MIN_*` keys are allowed.
- Response includes the updated keys, current env snapshot, and active policies.

### Trait Why Endpoint
```
GET /core/api/traits/BehaviorDNA.Sleep.Chronotype/why?user_id=tester&limit=1
-> 200 OK
{
  "user_id": "tester",
  "trait_id": "BehaviorDNA.Sleep.Chronotype",
  "value": "morning",
  "rr": 825.0,
  "why": "Matched phrase 'morning person' and 'before sunrise'",
  "ts": "2025-10-05T18:42:10.123456+00:00",
  "source": "ucnrr_rescore",
  "event_id": "text_1728153320000"
}
```
- For `limit > 1` the response is `{ "trait_id": "...", "items": [...] }`.

### Card Feed Endpoint
```
GET /core/api/whycards?user_id=tester&limit=5
-> 200 OK
{
  "items": [...],
  "count": 3
}
```

## UCNRR Why Attribution
- `/api/rescore` now returns `why_by_trait` in addition to RR and curiosity data.
- Chronotype detection looks for phrases such as “morning person”, “early riser”, “before sunrise”, “before dawn”.
- Matched phrases generate strings like `Matched phrase 'morning person' and 'before sunrise'` that flow into Core Why-Cards.

## Testing Notes
- `tests/integration/test_whycards.py` exercises the toggle endpoint, text ingest, and Why-Card retrieval end-to-end.
- Requirement: live stack on localhost (`CORE_BASE=http://127.0.0.1:8004`).
