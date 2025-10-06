# ExplorerDev — Developer Explorer Shell

The Developer Explorer is a Streamlit-based console for internal tooling. It
ships disabled by default and requires explicit environment flags before any
panels render.

## Quick start

```bash
DEV_EXPLORER_ENABLED=true streamlit run ExplorerDev/explorer_dev.py
```

## Head Coach shell router

Use `ExplorerDev/hc_shell_router.py` to launch the preferred Head Coach shell.
Set `HC_SHELL_V2` to `react` (Next.js Track A) or `streamlit` (HC_v2 Track B);
the script defaults to `react`.

```bash
HC_SHELL_V2=react   python ExplorerDev/hc_shell_router.py  # Next.js dev server
HC_SHELL_V2=streamlit python ExplorerDev/hc_shell_router.py  # Streamlit HC_v2
```

React runs from `web/` on http://localhost:3000 (ensure
`NEXT_PUBLIC_CORE_API_BASE` points at Core, default `http://127.0.0.1:8015`).
Streamlit launches `ExplorerFinal/pages/HC_v2.py` directly.

Optional overrides:

- `WRITE_PROTECT` (default `true`) keeps all writes inside the repo under
  `data/dev_users/` and `persona_config/dev_overrides/`. Set it to `false` only
  when you intentionally want Dev Explorer to touch live storage or the root
  `.env`.
- `CORE_BASE` / `HC_CORE_TIMEOUT` follow the same semantics as Control Panel Plus.
- `UI_CONTRACTS_CARD_ENABLED` (default `true`) gates the "UI Contracts — Head Coach
  Shells" module, which probes the React and Streamlit shells.

The shell automatically loads variables from the repo’s `.env` via
`python-dotenv`, mirroring Control Panel Plus behaviour.

## Safety rails

- When `WRITE_PROTECT=true`, save actions write to the dev directories noted
  above (e.g. `.env` updates land in
  `persona_config/dev_overrides/.env.dev`).
- The UI shows a banner indicating whether write-protect is active. Leave the
  guard on unless you are running in a disposable environment.

## Current modules

- **Coach Workshop** — Persona registry viewer (read-only) using the shared
  persona registration contract.
- **System Settings** — Holistic scheduler card to inspect cadence settings,
  trigger ad-hoc runs, and stage interval changes for review.

All other panels are presently placeholders. Refer to
`docs/Core_Benchmarks_Roadmap.md` for upcoming work.

## CI quick checks

Run the repository smoke tests with:

```bash
bash ExplorerDev/scripts/run_ci_smoke.sh
```

The script compiles Python sources in `ReDNACoreDemo/`, `ExplorerDev/`, and
`ExplorerFinal/`, executes the Core unit suite, and—when Node/npm is available—
invokes `npm run lint` and `npm run build` inside `web/`. Output ends with a
PASS/FAIL banner so the command can gate local commits or lightweight CI jobs.

## Control Panel Plus Plus (CP++)

Control Panel Plus Plus lives alongside the original Control Panel+ as an
experimental orchestrator for the Head Coach demo stack. Launch it with:

```bash
streamlit run control_panel_plus_plus.py
```

Features include:

- Start/stop orchestration for Core (uvicorn), React (Next.js), and Streamlit
  HC v2 with shared environment flags (`HC_CHAT_ENABLED`, streaming toggles,
  ports, `NEXT_PUBLIC_CORE_API_BASE`).
- Live log tails and one-click “Launch All / Open UIs” demo sequence.
- Health probes for `/ui/personas`, React debug overlay, and Streamlit
  `?ui_debug=1&format=json`.
- Port scanner/cleanup for common dev ports (Next.js 3000-3005, Streamlit
  8501-8510).
- Test runners for the Playwright e2e suite and the repository CI smoke script.
- Router helper to invoke `ExplorerDev/hc_shell_router.py` with
  `HC_SHELL_V2=react|streamlit`.

⚠️ The legacy `control_panel_plus.py` remains unchanged and available as a
fallback. CP++ stores its configuration in `.cpplusplus_env.json` and never
modifies the original CP+ settings files.
