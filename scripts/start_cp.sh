#!/usr/bin/env bash
#
# Start Control Panel++ on its dedicated port (8502)
# This script loads CP_PORT from .env and ensures CP++ doesn't conflict with other Streamlit services
#

set -euo pipefail

# Change to project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Load .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Default to 8502 if not set in .env
CP_PORT="${CP_PORT:-8502}"

echo "Starting Control Panel++ on port $CP_PORT..."

# Kill any existing CP++ instances
pkill -f "streamlit run control_panel_plus_plus.py" 2>/dev/null || true
sleep 1

# Start CP++ with explicit port binding
env STREAMLIT_SERVER_PORT="$CP_PORT" \
  streamlit run control_panel_plus_plus.py --server.port "$CP_PORT" --server.headless false

# Note: --server.headless false allows it to auto-open browser
