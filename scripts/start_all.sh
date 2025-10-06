#!/usr/bin/env bash
# start_all.sh - Launch ReDNA demo services (core API, web UI, control panel, optional Ollama)
# Usage: scripts/start_all.sh
# Creates logs/ and run/ directories, starts required services in the background, and
# writes PID files under run/. Run scripts/stop_all.sh to stop everything.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/run" "$PROJECT_ROOT/logs"

log() {
  local level=$1; shift
  printf '[%s] %s\n' "$level" "$*"
}

warn() {
  log "WARN" "$*"
}

info() {
  log "INFO" "$*"
}

port_open() {
  local host=$1
  local port=$2
  python - <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    try:
        sock.connect((host, port))
    except OSError:
        sys.exit(1)
PY
}

wait_for_port() {
  local host=$1
  local port=$2
  local name=$3
  local timeout=${4:-60}
  local interval=1
  local start
  start=$(date +%s)
  while true; do
    if port_open "$host" "$port" >/dev/null 2>&1; then
      info "OK: $name listening on $host:$port"
      return 0
    fi
    local now=$(date +%s)
    if (( now - start >= timeout )); then
      warn "Timeout waiting for $name on $host:$port"
      return 1
    fi
    sleep "$interval"
  done
}

rotate_log() {
  local file=$1
  : > "$file"
}

# Activate virtualenv if present
if [[ -d "$PROJECT_ROOT/.venv" ]]; then
  info "Activating virtualenv .venv"
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate" || warn "Failed to activate .venv"
else
  warn "Virtualenv .venv not found; continuing without activation"
fi

CORE_LOG="logs/core.log"
WEB_LOG="logs/web.log"
CP_LOG="logs/cp.log"
OLLAMA_LOG="logs/ollama.log"

CORE_PID_FILE="run/core.pid"
WEB_PID_FILE="run/web.pid"
CP_PID_FILE="run/cp.pid"
OLLAMA_PID_FILE="run/ollama.pid"

CORE_PORT=8015
WEB_DEFAULT_PORT=3001
CP_PORT=8502
OLLAMA_PORT=11434

start_core() {
  info "Starting Core API (uvicorn)"
  rotate_log "$CORE_LOG"
  local core_env=(
    HC_CHAT_ENABLED=1
    HC_CHAT_STREAM_ENABLED=1
    HC_ASK_ACTIONS_ENABLED=1
  )
  local provider_value="${HC_CHAT_PROVIDER:-stub}"
  export HC_CHAT_PROVIDER="$provider_value"
  (
    cd "$PROJECT_ROOT/ReDNACoreDemo"
    env "HC_CHAT_PROVIDER=$HC_CHAT_PROVIDER" "HC_CHAT_ENABLED=1" "HC_CHAT_STREAM_ENABLED=1" "HC_ASK_ACTIONS_ENABLED=1" \
      uvicorn core.api:build_app --factory --reload --port "$CORE_PORT" >> "$PROJECT_ROOT/$CORE_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PROJECT_ROOT/$CORE_PID_FILE"
  )
  wait_for_port 127.0.0.1 "$CORE_PORT" "Core API" 60 || warn "Core API may not have started correctly"
}

parse_web_port() {
  local log_file=$1
  local attempts=30
  local actual=""
  while (( attempts-- > 0 )); do
    if [[ -f "$log_file" ]]; then
      actual=$(grep -E -m1 "started server on .*:(\\d+)" "$log_file" | sed -E 's/.*:(\\d+).*/\\1/')
      if [[ -n "$actual" ]]; then
        break
      fi
    fi
    sleep 1
  done
  if [[ -z "$actual" ]]; then
    echo "$WEB_DEFAULT_PORT"
  else
    echo "$actual"
  fi
}

start_web() {
  info "Starting web (Next.js dev server)"
  rotate_log "$WEB_LOG"
  (
    cd "$PROJECT_ROOT/web"
    env PORT="$WEB_DEFAULT_PORT" \
      NEXT_PUBLIC_CORE_API_BASE="http://127.0.0.1:$CORE_PORT" \
      ${NEXT_PUBLIC_FLAGS:+NEXT_PUBLIC_FLAGS="$NEXT_PUBLIC_FLAGS"} \
      npm run dev >> "$PROJECT_ROOT/$WEB_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PROJECT_ROOT/$WEB_PID_FILE"
  )
  sleep 2
  local detected_port
  detected_port=$(parse_web_port "$WEB_LOG")
  if [[ "$detected_port" != "$WEB_DEFAULT_PORT" ]]; then
    warn "Web dev server bumped to port $detected_port"
  fi
  wait_for_port 127.0.0.1 "$detected_port" "Web UI" 90 || warn "Web UI may not have started correctly"
}

start_cp() {
  info "Starting control_panel_plus_plus (Streamlit)"
  rotate_log "$CP_LOG"
  env STREAMLIT_SERVER_PORT="$CP_PORT" \
    streamlit run control_panel_plus_plus.py --server.port "$CP_PORT" --server.headless true >> "$CP_LOG" 2>&1 &
  local pid=$!
  echo "$pid" > "$CP_PID_FILE"
  wait_for_port 127.0.0.1 "$CP_PORT" "Control Panel++" 60 || warn "Control Panel++ may not have started correctly"
}

ensure_ollama() {
  if [[ "${HC_CHAT_PROVIDER:-stub}" != "ollama" ]]; then
    return
  fi
  info "HC_CHAT_PROVIDER=ollama - ensuring Ollama is running"
  if port_open 127.0.0.1 "$OLLAMA_PORT" >/dev/null 2>&1; then
    info "Ollama already running on port $OLLAMA_PORT"
    local pid
    pid=$(lsof -ti tcp:$OLLAMA_PORT | head -n1 || true)
    if [[ -n "$pid" ]]; then
      echo "$pid" > "$OLLAMA_PID_FILE"
    fi
    return
  fi

  rotate_log "$OLLAMA_LOG"
  if command -v brew >/dev/null 2>&1; then
    info "Attempting to start Ollama via brew services"
    if brew services start ollama >> "$OLLAMA_LOG" 2>&1; then
      sleep 3
      if wait_for_port 127.0.0.1 "$OLLAMA_PORT" "Ollama" 60; then
        local pid
        pid=$(lsof -ti tcp:$OLLAMA_PORT | head -n1 || true)
        if [[ -n "$pid" ]]; then
          echo "$pid" > "$OLLAMA_PID_FILE"
        else
          warn "Unable to determine Ollama PID after brew start"
        fi
        return
      else
        warn "Ollama did not start via brew services"
      fi
    else
      warn "brew services start ollama failed"
    fi
  else
    warn "Homebrew not available; skipping brew services start"
  fi

  if command -v ollama >/dev/null 2>&1; then
    info "Starting ollama serve directly"
    ollama serve >> "$OLLAMA_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$OLLAMA_PID_FILE"
    wait_for_port 127.0.0.1 "$OLLAMA_PORT" "Ollama" 60 || warn "Ollama serve may not have started correctly"
  else
    warn "ollama command not found; cannot start Ollama"
  fi
}

start_core
start_web
start_cp
ensure_ollama

info "All services launched. Logs in logs/, PIDs in run/."
