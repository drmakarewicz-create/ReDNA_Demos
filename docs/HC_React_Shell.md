# Head Coach React Shell

The Head Coach (HC) React shell is the primary UI for live coaching demos. It runs as a Next.js
app (port 3000 by default) and talks to the Core FastAPI service via `/ui/*` endpoints. This page
summarises the key interaction patterns needed for operator-ready walkthroughs.

## Quick start

1. Ensure the Core service is running (standalone or via `docker compose up`).
2. Start the React shell with `npm run dev` inside `web/` (or the `react` service in
   `docker-compose.yml`).
3. Visit <http://localhost:3000>. The workspace badge in the header confirms the profile that was
   launched from Control Panel++ (CP++).

## Persona router & center views

- Persona chips (Head Coach, Relationship, PaDNA, Photo) appear in the right-hand rail. Disabled
  personas are hidden when the environment flag blocks them.
- Selecting a chip immediately swaps the active panel without reloading the transcript.
- The top navigation lets you toggle between **Coach Chat**, **Draft Chat**, and **Snapshots**; the
  currently active view is highlighted.

## Transcript search & pinned messages

- The transcript panel now includes a debounced search box (Ctrl/Cmd+Shift+F). Matches are
  highlighted inline and the Next/Prev buttons navigate between hits.
- Every message bubble has a **Pin** button (shortcut `P` when the message has focus). Pinned
  messages survive reloads via `localStorage`. The **Pinned** toggle filters the transcript to just
  pinned entries, and **Clear pins** removes the saved set for the current user.

## Persona toolbars

Each persona renders contextual tooling at the top of its panel:

- **Head Coach** – quick actions to generate a demo planner ask or approve the current top ask.
- **PaDNA** – JSON field-mapping preview and metadata grid toggles for outbound bundles.
- **Photo** – rotation controls, crop stub, EXIF inspector, and download links for the original and
  latest render job result. The render job list polls the `/ui/photo/status` endpoint until jobs are
  done.

## Draft Chat panel

The Draft Chat view pulls real planner drafts from `data/users/<id>/drafts/*.json` (or checkpoint
backups). Items are rendered as Markdown, with a filter for recent days and a deep-link to
Provenance Lab when `NEXT_PUBLIC_PROVENANCE_LAB_URL` is configured.

## Guided tour

- First-time visitors see a 5-step guided tour that introduces the user switcher, persona rail,
  view tabs, persona toolbars, and composer. The tour state persists under
  `_hc_intro_tour_v1` in `localStorage`.
- Operators can re-open the tour at any time via the **Help tour** button in the header or the
  `Ctrl + /` command palette shortcut.

## Keyboard shortcuts & command palette

The command palette (`Ctrl/Cmd + /`) lists all built-in shortcuts:

| Shortcut | Action |
| --- | --- |
| `Ctrl/Cmd + K` | Focus the active user switcher |
| `Ctrl/Cmd + Shift + F` | Focus transcript search |
| `S` | Open settings |
| `D` | Switch to Draft Chat |
| `G` | Switch to Snapshots |
| `P` | Pin/unpin the focused transcript bubble |
| `Ctrl/Cmd + /` | Open the command palette (also re-opens the guided tour) |

Settings → **Shortcuts** lists the same combinations with platform-aware modifier labels.

## Settings & preferences

User preferences render in the Settings modal and persist to `_hc_preferences_v1` in `localStorage`:

- Stream coach replies on/off
- Enter-to-send vs. Ctrl/Cmd+Enter
- Auto-scroll transcript
- Compact density
- Theme (dark/light)
- Locale (currently `en`)

Preferences update the page in real time and survive page reloads.

## Media uploads & render jobs

The Photo and PaDNA panels both rely on the hardened media upload endpoint:

- **Allowed extensions:** `.jpg`, `.png`, `.json`
- **MIME sniffing:** invalid payloads are rejected with `415`.
- **Size limit:** `MEDIA_MAX_MB` (default 20 MB).
- **Filenames:** slugified to prevent unsafe paths; the original name is kept in metadata.
- Violations are logged to `data/_stats/uploads.log` in JSONL format.

Photo render requests call `POST /ui/photo/render`, then poll `GET /ui/photo/status` until the job is
`done`. `GET /ui/photo/result` streams the generated preview, falling back to a placeholder.

## Troubleshooting

- **No personas visible:** check CP++ launch guard / profile config. The React header badge should
  match the CP++ profile label.
- **Pins/search not working:** ensure `localStorage` is available (e.g., not in private browsing
  mode with storage disabled).
- **Render job stuck queued:** Core writes jobs under
  `data/users/<id>/renders/<job_id>/`. Inspect `job.json` and logs for errors.
- **Draft Chat empty:** verify the user has JSON files under `data/users/<id>/drafts/` or
  checkpoints.
