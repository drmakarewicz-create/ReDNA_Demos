---

# 4) ReDNA_ChangeLog.md (drop-in)

```markdown
# ReDNA Change Log

## 2025-09-18 — Data Cycle benchmark achieved
- Stable loop: Explorer → UCN/RR → Core → Explorer.
- Added scripts:
  - `scripts/set_env_llama3.sh` (LLM env)
  - `scripts/start_core.sh`, `scripts/start_ucnrr.sh` (no reload)
- Added tools:
  - `tools/golden_path_harness.py`, `tools/resolved_viewer.py`
  - `control_panel/ai_control_panel_agent.py` (agent-only)
- Verified traits from free text:
  - Eye color, marriage status/year, partner gender/name inference, height, hair color, balding.
- Decision: Control Panel Plus owns processes; AI Control Panel manages LLM config and diagnostics.

## 2025-09-XX — (next entry)
- What changed:
- Why:
- Verification steps:
- Rollback plan: