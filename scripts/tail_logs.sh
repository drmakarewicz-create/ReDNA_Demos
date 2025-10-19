#!/usr/bin/env bash
set -euo pipefail

LOG_PATH="${REDNA_STACK_LOG:-$HOME/.redna/logs/stack.log}"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to pretty-print stack logs" >&2
  exit 1
fi

mkdir -p "$(dirname "$LOG_PATH")"
touch "$LOG_PATH"

echo "Tailing $LOG_PATH (Ctrl+C to exit)..." >&2

tail -F "$LOG_PATH" | jq -r '"\(.ts) [\(.service)] \(.level) \(.event) - \(.msg)"'
