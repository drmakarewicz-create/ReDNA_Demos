# Git Hygiene Guide

This guide documents how to shrink Git status noise safely while protecting user-generated data.

## What we ignore

- **Runtime artifacts**: `ReDNACoreDemo/data/**`, `backups/**`, `data/telemetry/**`, `prompts/insights/**`
- **Build outputs**: `**/dist/`, `**/.vite/`, `web/.next/`, `**/coverage/`
- **Caches**: `**/node_modules/`, `**/.venv/`, `**/__pycache__/`, `**/.pytest_cache/`
- **Generated media**: `*.mp3`, `*.wav`, `*.zip`, `*.gz`
- README placeholders live in each ignored root to explain the policy and keep documentation trackable.

## Step 1 — Scan first

```bash
python3 scripts/git_sanity/scan_status.py
cat docs/ops/GIT_STATUS_REPORT.md
```

The scanner prints the current totals, highlights the busiest folders (up to three levels deep), and measures disk usage for the 20 noisiest directories.

## Step 2 — Dry run (no commits)

```bash
bash scripts/git_sanity/apply_ignore.sh --local --dry-run
```

- Updates `.git/info/exclude` with the shared ignore block.
- Writes `docs/ops/UNTRACK_DRYRUN.txt` so you can review the affected paths.
- Leaves the working tree untouched and stays on your current branch.

## Step 3 — Apply on the hygiene branch

```bash
bash scripts/git_sanity/apply_ignore.sh --apply
```

- Ensures you are on `chore/git-hygiene` (creates it if needed).
- Removes ignored files from the index with `git rm -r --cached` (files stay on disk).
- Commits the ignore block with message `chore: ignore runtime/build artifacts; keep files on disk.`
- Records revert instructions in `docs/ops/GIT_HYGIENE_REVERT.md`.

## How to revert

The revert recipe is stored in `docs/ops/GIT_HYGIENE_REVERT.md`. In short:

```bash
git switch -
git reset --hard <pre-hygiene-sha>
git branch -D chore/git-hygiene    # optional cleanup
```

Double-check `git status` before running the reset to make sure you do not lose real work.

## Switching back to local-only ignores

If you prefer to keep the ignore rules local, rerun:

```bash
bash scripts/git_sanity/apply_ignore.sh --local --dry-run
```

Then remove or revert the `.gitignore` commit on `chore/git-hygiene`.

## Telemetry rotation

Use the maintenance script to compress aging telemetry logs while preserving recent activity:

```bash
bash scripts/maintenance/rotate_telemetry.sh
```

- Compresses `*.jsonl` and `agent_activity.jsonl` files older than 30 days to `*.jsonl.gz`.
- Copies very large archives (>100 MB) into daily `archives/YYYY-MM-DD/` folders.
- Appends a summary to `docs/ops/ROTATION_LOG.md`.

Keep the last 30 days uncompressed for quick debugging. Older archives stay available inside the telemetry directories.
