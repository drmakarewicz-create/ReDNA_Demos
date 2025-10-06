/Documents/ReDNA_Demos
├─ ReDNACoreDemo/                     # Core service (app.py)
│  └─ data/users/<USER>/              # resolved.json, resolved.flat.json, observations.json, evidence.json
├─ UCN_RR_Demo/                       # UCN/RR service (ucnrr_app.py)
│  └─ data/users/<USER>/inbox/        # raw text snapshots; rr_snapshot.json at user root
├─ ExplorerFinal/                     # Explorer UI (explorer_final.py)
├─ prompts/                           # LLM prompts (ucn_rr_ai.md, ucn_rr_confidence.md, core_ai.md, core_ai_propagation.md)
├─ control_panel/ (optional)
│  ├─ ai_control_panel_agent.py       # Agent-only control panel (LLM cfg, harness, viewer, health)
│  └─ logs/                           # AI panel logs (if any)
├─ scripts/
│  ├─ set_env_llama3.sh               # Exports LLM + prompts env (source before launches)
│  ├─ start_core.sh                   # Sources env, launches Core on :8015
│  └─ start_ucnrr.sh                  # Sources env, launches UCN/RR on :8011
├─ tools/
│  ├─ golden_path_harness.py          # 4-case integration test
│  └─ resolved_viewer.py              # CLI viewer for resolved.json
└─ docs/
   ├─ ReDNA_Data_Cycle_Note_v1.0.pdf
   ├─ ReDNA_File_and_Folder_Map_v1.1.pdf
   ├─ ReDNA_File_and_Folder_Map_v1.2.md   # <-- add this file (content below)
   ├─ ReDNA_Ops_Runbook_v1.0.md           # <-- add this file (content below)
   └─ ReDNA_ChangeLog.md                  # <-- add this file (content below)

   # ReDNA File & Folder Map — v1.2 (Delta to v1.1)

## Purpose
Document the minimal, working layout that produced the successful Explorer → UCN/RR → Core loop, plus helper tools and control scripts.

## New/Relevant Paths
- `scripts/set_env_llama3.sh` – exports LLM + prompt variables.
- `scripts/start_core.sh` – starts Core (`app.py`) on :8015 with env loaded.
- `scripts/start_ucnrr.sh` – starts UCN/RR (`ucnrr_app.py`) on :8011 with env loaded.
- `control_panel/ai_control_panel_agent.py` – agent-only UI for LLM config, health, harness, resolved viewer.
- `tools/golden_path_harness.py` – 4 canonical tests (height, marriage, eyes, hair/bald).
- `tools/resolved_viewer.py` – quick trait dump.

## Canonical Ports
- Core: **8015**
- UCN/RR: **8011**
- Explorer: **8012** (current)
- AI Control Panel (agent): **8020**

## Data Files (authoritative)
Core per-user:
- `data/users/<USER>/resolved.json` (schema_version:4)
- `data/users/<USER>/resolved.flat.json`
- `data/users/<USER>/observations.json`
- `data/users/<USER>/evidence.json`

UCN/RR per-user:
- `data/users/<USER>/rr_snapshot.json`
- `data/users/<USER>/inbox/<ts>_text.json`

## Prompts
- `prompts/ucn_rr_ai.md`, `prompts/ucn_rr_confidence.md`
- `prompts/core_ai.md`, `prompts/core_ai_propagation.md`

## Launch (via Control Panel Plus)
Use the scripts (no `--reload`):
- Core: `.../scripts/start_core.sh`
- UCN/RR: `.../scripts/start_ucnrr.sh`