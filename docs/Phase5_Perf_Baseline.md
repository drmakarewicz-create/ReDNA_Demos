# Phase 5 Performance Baseline

This note explains how to capture the 24-hour roundtrip baseline and how to
interpret the resulting alerts and charts. Share this with Claude before
Phase 5.1 so they can extend monitoring without re-discovery.

## 1. Start the Capture Job
- Ensure Core (`start_core.sh`) and DevX (`start_devx.sh`) are running locally.
- From the repo root, launch the capture helper (a tmux session is recommended):

```bash
python scripts/roundtrip_capture.py --interval 60 &
```

- The script samples `/metrics` every 60 seconds and appends rows to
  `docs/reports/roundtrip_timeseries.csv`. Each row records hop timing
  percentiles, ingest counters, Core `rr_mode`, and UCNRR status.

## 2. Read the Chart (DevX Bench UI)
- The DevX `/metrics/roundtrip` endpoint now returns alert flags alongside
  the hop percentile series. RoundtripChart renders an amber/red badge when
  `total_p95_high` is true and shows ingest error counts/rates inline.
- Threshold env vars (tweakable without redeploy):
  - `ROUNDTRIP_P95_MAX_MS` (default 2000)
  - `UCNRR_P95_MAX_MS` (default 1200)
  - `ERROR_RATE_MAX_PCT` (default 3)

## 3. Respond to Alerts
- **High latency (total_p95_high)**: confirm UCNRR is online via DevX control
  panel, then check for recent deploys. If persistent >15 minutes, capture
  the offending rows from `roundtrip_timeseries.csv` and attach to Slack.
- **UCNRR latency (ucnrr_p95_high)**: warm cache using the Tier-2 verifier
  sentences or reduce concurrency until the cache repopulates.
- **Error rate (errors_rate_high)**: inspect Core logs (`logs_core.txt`) for
  ingestion failures; pause the capture if the error rate stays above 3%.

## 4. Closing the Baseline Window
- After 24 hours, stop the capture job (`Ctrl+C`) and archive the CSV
  alongside any annotated notes. Reference the timestamp of the last row in
  `docs/PHASE5_STATUS.md`.
- If the CSV exceeds 10 MB, gzip it and update `roundtrip_capture.py` to roll
  files (follow-up task, not required for Phase 5 kickoff).

