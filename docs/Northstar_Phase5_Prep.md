# Northstar Phase 5 Prep

This note captures the hooks and context objects added during Phase 5 kickoff
so Claude can wire them into the Northstar UI without spelunking.

## Runtime Hooks
- `GlobalMetricsContext` (exported from `web/src/app/tools/llm-benchmarks/page.client.tsx`)
  - Provides `{ roundtrip, ucnrrStatus }` payload mirroring DevX metrics.
  - Roundtrip payload matches `/devx/api/metrics/roundtrip` with `alerts`.
  - UCNRR status pulls from `/devx/api/stack/ucnrr/status` (alive, reason, last_check).
- `PulseOverlay` component (same file)
  - Visual “ReDNA Pulse” indicator; bright green pulse when total p95 < 1000 ms.
  - Safe to mount anywhere; pointer-events disabled.
- DevX Roundtrip API enhancements (`ReDNACoreDemo/devx/backend/llm_bench_api.py`)
  - Response now includes `alerts` and `ingest.error_rate_pct`.
  - Threshold env vars: `ROUNDTRIP_P95_MAX_MS`, `UCNRR_P95_MAX_MS`, `ERROR_RATE_MAX_PCT`.

## How to Consume
1. Wrap Northstar shell in `GlobalMetricsContext.Provider` (LLM Bench page already does this).
2. Use `useContext(GlobalMetricsContext)` to read latest roundtrip metrics and UCNRR status.
3. Display the `PulseOverlay` (or replicate styling) wherever a real-time pulse is desired.
4. Alert badges can be reused from `RoundtripChart.tsx` (look for `statusChips`).

## Next Steps (for Claude)
- Connect the metrics context to the Northstar dashboard cards (latency, UCNRR uptime).
- Gate dopamine animations behind total p95 < 1 s and error rate < 1.5%.
- Add quick actions: if `alerts.errors_rate_high`, surface log shortcuts in Northstar.
- Optional: port the `PulseOverlay` onto the Northstar home hero to emphasize stability.

