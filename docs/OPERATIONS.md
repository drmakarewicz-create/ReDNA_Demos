# Operations Quick Reference

## Fix Ports Banner
- **Detection**: CP++ compares running ports against `.env`, `web/.env.local`, and `.cpplusplus_env.json`. Any drift raises a banner at the top of the app.
- **Fix Ports**: The button regenerates `.cpplusplus_env.json` from the canonical `.env`, optionally rewrites the env files (checkbox), restarts services in sequence (UCNRR → Core → React → DevX), and records an entry in `~/.redna/nuclear_reset.log`.
- **Safety**: The helper refuses to run while environment edits are unsaved. Service restarts reuse `_launch_stack`, so the UI stays aligned with CP++ port settings after the repair.

## Nuclear Diagnostics Rotation
- **Archive path**: Sanitised bundles are archived under `~/.redna/nuclear/bundles/` as `nuclear_YYYYMMDDThhmmssZ.tgz`.
- **Contents**: Each bundle includes pre/post restart copies of `devx_backend.log`, `devx_ui.log`, `logs/stack.log` (with API keys, JWTs, and bearer tokens redacted), plus `metadata.json` summarising kill, rebuild, and sanity results.
- **Retention**: CP++ keeps the five most recent bundles and prunes older archives automatically. Active log files are truncated after the bundle is written so new runs start fresh.

## Post-Nuclear Sanity Block
- **Automated checks**: After a Nuclear reset CP++ runs three probes using the dedicated `NUCLEAR_SANITY` user:
  1. `POST /core/api/ingest_text` with a chronotype phrase.
  2. `GET /core/api/traits/BehaviorDNA.Sleep.Chronotype/why?user_id=NUCLEAR_SANITY`.
  3. `GET /devx/api/ingestion/ai_ready`.
- **Visibility**: Results appear in the “🔬 Post-Nuclear Sanity Checks” expander and are appended to `~/.redna/nuclear_reset.log` via `_append_nuclear_log`.
- **Why it matters**: The trio verifies ingestion, Why-Card generation, and DevX readiness before declaring the stack healthy.

## CI Green Gate
- **Workflow**: `.github/workflows/test-suite.yml` now contains the `ai-readiness-green-gate` job.
- **Guards**:
  - Runs `python scripts/enforce_prod_flags.py` to ensure no mock/skip/bypass flags are set for production.
  - Boots UCNRR/Core/DevX headless with `scripts/cppp_bootstrap.py --quiet`.
  - Calls `GET /devx/api/ingestion/ai_ready` and fails unless `.result == "ALL-GOOD"`.
- **Outcome**: Pull requests only pass once the live stack is green and all prod safeguards are respected.
