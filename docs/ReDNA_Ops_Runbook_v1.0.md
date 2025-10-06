# ReDNA Operational Runbook v1.0

## Goal
Cold start → verified Data Cycle in <2 minutes.

## 0) Preconditions
- Ollama running locally (`ollama serve`) and model pulled (`ollama pull llama3`).
- Python venv present at `~/Documents/ReDNA_Demos/PhotoRefinementCoach/.venv`.

## 1) Environment
Run once per terminal or ensure Control Panel Plus uses the scripts:
```bash
source scripts/set_env_llama3.sh