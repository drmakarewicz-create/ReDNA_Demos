# Control Panel++ (CP++)

Control Panel++ is the Streamlit-based launcher that orchestrates the demo stack. It manages
service ports, health checks, environment flags, and saved profiles for quick context switching.
This guide highlights the workflows that operators need during demos.

## Launching CP++

```bash
streamlit run control_panel_plus_plus.py
```

Environment variables are persisted in `.cpplusplus_env.json` at the repo root. Saved profiles live
at `~/.cpplusplus_profiles.json`.

## Profiles workflow

1. Configure ports, flags, provider credentials, and workspace settings on the **Environment & Flags**
   tab.
2. Switch to the **Profiles** tab to save the current environment (`Save / Update`). Profiles include:
   - `WORKSPACE_ROOT` & `WORKSPACE_LABEL`
   - Core / React / Streamlit ports
   - Provider configuration (OpenAI / Ollama)
   - Launch toggles (auto-open React/Streamlit/Dev Explorer)
3. Apply a profile to the environment, then hit **Save** on the environment tab to persist it.

Toggling between profiles allows instant workspace changes. React displays the workspace label in
its header, and Core reads from the corresponding root.

## Open UIs & health quick links

- **Open Head Coach** – launches the React shell (defaults to `http://127.0.0.1:3000`).
- **Open Control Panel++** – opens this Streamlit app in a new tab.
- **Open Explorer** – starts the Streamlit Explorer console.
- The Dev Explorer header mirrors these links (Core, React, CP++), so both shells stay in sync.

## Provider check CLI

The **Validate provider** button runs the same probe that `--provider-check` exposes on the command
line. It verifies:

- **OpenAI** – API key and model reachability.
- **Ollama** – local server availability and version endpoint.

Results are cached in the session state so you can review the last outcome after running a check.

## Launch guard & ports

CP++ guards against port collisions and prompts for sanity checks before spinning up services:

- It tracks whether ports (Core, React, CP++) are already in use and surfaces a warning when
  attempting to launch.
- Launch guard ensures workspace roots and provider settings are acknowledged before the “Launch
  All” sequence proceeds.
- Environment toggles decide whether to auto-open UIs (`AUTO_OPEN_REACT_AFTER_LAUNCH`, etc.).

## Workspace root integration

Each profile can override `WORKSPACE_ROOT`. When provided, CP++ injects both `WORKSPACE_ROOT` and the
matching `NEXT_PUBLIC_WORKSPACE_LABEL` into React. Core persists data under the workspace root’s
`data/` folder; this allows isolating demo state per tenant or scenario.

## Troubleshooting

| Symptom | Suggested check |
| --- | --- |
| Launch button no-ops | Confirm the profile was applied and the Environment tab saved. |
| React header label wrong | Reload CP++ profile or ensure `NEXT_PUBLIC_WORKSPACE_LABEL` is set. |
| Provider failures | Use **Validate provider** and re-check API keys or local Ollama status. |
| Auto-open not happening | Ensure the corresponding `AUTO_OPEN_*` toggle is enabled before pressing Launch. |

CP++ remains the system of record for demo configuration—always apply and save a profile before
launching services.
