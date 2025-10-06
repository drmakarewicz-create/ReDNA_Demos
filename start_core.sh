#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Documents/ReDNA_Demos"
source "$HOME/Documents/ReDNA_Demos/set_env_llama3.sh"
exec "$HOME/Documents/ReDNA_Demos/PhotoRefinementCoach/.venv/bin/python" -m uvicorn ReDNACoreDemo.core.api:build_app --factory --host 0.0.0.0 --port 8015