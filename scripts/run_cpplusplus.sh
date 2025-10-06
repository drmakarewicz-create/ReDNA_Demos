#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Root venv python not found at: $VENV_PY"
  echo "Create it with:  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

exec "$VENV_PY" -m streamlit run "$REPO_ROOT/control_panel_plus_plus.py" --server.port "${1:-8501}"
