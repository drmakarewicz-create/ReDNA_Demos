# Head Coach React Shell (Track A)

This is a minimal Next.js + Tailwind scaffold for the Head Coach "Track A" experience.

## Prerequisites
- Node.js 18+
- npm 9+

## Quick start
```bash
npm install
NEXT_PUBLIC_CORE_API_BASE="http://127.0.0.1:8015" npm run dev
```
Then open http://localhost:3000 to view the live layout.

> ❗️ Avoid running `npm audit fix --force` before demos. Forced upgrades often
> pull prerelease dependencies that break the validated UI bundle.

### Helpful scripts

- `npm run lint` – ESLint with the Next.js config
- `npm run typecheck` – TypeScript `--noEmit` validation
- `npm run pree2e` – Convenience wrapper for `lint` + `typecheck`
- `npm run provider:check` – Runs the CP++ provider validation helper for LLM credentials

## End-to-end smoke tests

Playwright checks cover the demo-critical flows (composer anchoring, persona swap,
Unabridged jump, planner ask actions, snapshot export).

```bash
npm install
npm run pree2e
npx playwright install  # once per machine to download the browsers
NEXT_PUBLIC_CORE_API_BASE="http://127.0.0.1:8015" npm run test:e2e
```

The tests stub `/ui/*` endpoints with deterministic fixtures, so Core does not need
to be running while the suite executes.

## Layout notes
- Transcript panel scrolls independently above the fixed composer.
- Persona rail chips remain visible regardless of scroll state.
- File upload uses a modal drawer to avoid shifting the composer.
- Header includes an Unabridged anchor that targets the read-only trait panel.
- Composer padding respects `env(safe-area-inset-bottom)` so iOS devices keep audio/chat controls visible.

### Responsive behaviour
- The header and persona rail collapse onto stacked rows below 960 px; persona chips scroll horizontally on very small widths while the dropdown remains available.
- Main content uses `pb=calc(10rem + safe-area)` to ensure the fixed composer never overlaps tables or drawers when the on-screen keyboard is visible.
- The debug overlay (`?ui_debug=1`) docks near the top of the viewport on phones/tablets so it never occludes the composer.

## Data wiring
- `_active_user_id` drives all read-only fetches (persisted in `localStorage`).
- The shell reads from:
  - `GET /ui/personas`
  - `GET /ui/asks`
  - `GET /ui/observations/aggregates`
  - `GET /ui/unabridged`
- Set `NEXT_PUBLIC_CORE_API_BASE` if Core runs on a different host/port.
- Append `?ui_debug=1` to the URL to view the developer overlay (roster, composer status, first widget, active user id).

Static transcript content remains for now; planner asks, metrics, personas, and unabridged traits load from the Core read-only adapters.

### Selecting the active shell

Set the repository-level environment variable `HC_SHELL_V2` to choose the
primary Head Coach shell for demos:

- `HC_SHELL_V2=react` (default) — use this Next.js shell. Launch with
  `python ExplorerDev/hc_shell_router.py` or `npm run dev` inside `web/`.
- `HC_SHELL_V2=streamlit` — prefer the Streamlit HC_v2 page. Launch with
  `python ExplorerDev/hc_shell_router.py` or
  `streamlit run ExplorerFinal/pages/HC_v2.py`.

Both shells read the same read-only `/ui/*` endpoints and honour the
`NEXT_PUBLIC_CORE_API_BASE` configuration.

## Production build

1. Install dependencies and run the build:

   ```bash
   npm install
   NEXT_PUBLIC_CORE_API_BASE="https://your-core-host" npm run build
   ```

2. If the React shell is served from a different origin than Core, the Core
   service must allow cross-origin `GET` requests on `/ui/*`. At a minimum
   configure:

   ```
   Access-Control-Allow-Origin: https://your-frontend-host
   Access-Control-Allow-Methods: GET
   Access-Control-Allow-Headers: Content-Type
   ```

3. Runtime configuration is driven by `NEXT_PUBLIC_*` variables. Ensure
   `NEXT_PUBLIC_CORE_API_BASE` matches the Core host both for `npm run dev`
   and `npm run build`.
