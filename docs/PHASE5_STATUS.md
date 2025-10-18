# Phase 5 Kickoff Status

**Last updated:** _(fill during handoff)_  
**Owner:** Codex → Claude (Phase 5)

## Sub-task Status
- **Tier-2 verification:** Env toggles landed, `scripts/tier2_verify.py` ready. Precision target 95% enforced via script summary (`docs/reports/tier2_verify_summary.md`).
- **Roundtrip capture:** `scripts/roundtrip_capture.py` in place; baseline instructions in `docs/Phase5_Perf_Baseline.md`.
- **DevX alerts:** `/devx/api/metrics/roundtrip` now returns alert flags and error-rate; UI badges live in `RoundtripChart`.
- **Northstar hooks:** `GlobalMetricsContext` + `PulseOverlay` shipped; see `docs/Northstar_Phase5_Prep.md` for integration notes.

## Env Toggles & Thresholds
- Promotion toggles: `PROMOTE_ENABLE_CHRONO`, `PROMOTE_ENABLE_DIET`, `PROMOTE_ENABLE_WORKLOC`, `PROMOTE_ENABLE_GROUPSIZE`, `PROMOTE_ENABLE_EXERCISE_TYPE`.
- RR gates: `RR_PROMOTE_MIN_CHRONO=780`, `RR_PROMOTE_MIN_DIET=780`, `RR_PROMOTE_MIN_WORKLOC=800`, `RR_PROMOTE_MIN_GROUPSIZE=800`, `RR_PROMOTE_MIN_EXERCISE_TYPE=800`.
- Alert bounds: `ROUNDTRIP_P95_MAX_MS=2000`, `UCNRR_P95_MAX_MS=1200`, `ERROR_RATE_MAX_PCT=3`.

## Data Trails
- Tier-2 verifier log: `docs/reports/tier2_verify_summary.md` (appends per run).
- Roundtrip time-series: `docs/reports/roundtrip_timeseries.csv` (append-only; rotate after 24h window).
- DevX metrics badge logic: `web/src/components/metrics/RoundtripChart.tsx`.

## Open Questions / TODOs
- Confirm UCNRR warm-cache sentence pack for Tier-2 traits (placeholder sentences live in `tier2_verify` samples).
- Decide whether to auto-roll the roundtrip CSV after baseline (currently manual).
- Validate precision ≥95% before turning traits ON in production; document any trait kept OFF in verifier summary.

