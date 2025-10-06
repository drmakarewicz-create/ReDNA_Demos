# ~/Documents/ReDNA_Demos/start_explorer.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/Documents/ReDNA_Demos/ExplorerDev"
exec "$HOME/Documents/ReDNA_Demos/.venv/bin/python" -m streamlit run explorer_dev.py \
  --server.port 8550 --server.address 0.0.0.0