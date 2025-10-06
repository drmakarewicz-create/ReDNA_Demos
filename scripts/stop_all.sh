#!/usr/bin/env bash
# stop_all.sh - Stop ReDNA demo services launched by start_all.sh
# Usage: scripts/stop_all.sh
# Reads PID files from run/ and attempts to terminate the associated processes.
# PID files are removed once the processes are stopped.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

PID_DIR="$PROJECT_ROOT/run"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOG_DIR"

log() {
  local level=$1; shift
  printf '[%s] %s\n' "$level" "$*"
}

info() {
  log "INFO" "$*"
}

warn() {
  log "WARN" "$*"
}

error() {
  log "ERROR" "$*"
}

read_pids() {
  local pid_file=$1
  mapfile -t pids < <(tr -s '\n\r ' '\n' < "$pid_file" | sed '/^$/d')
  printf '%s\n' "${pids[@]}"
}

stop_pid() {
  local name=$1
  local pid=$2
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    info "$name (PID $pid) not running"
    return 0
  fi

  info "Stopping $name (PID $pid)"
  kill "$pid" >/dev/null 2>&1 || true

  local waited=0
  local timeout=10
  while kill -0 "$pid" >/dev/null 2>&1; do
    if (( waited >= timeout )); then
      warn "$name (PID $pid) still running after $timeout seconds; sending SIGKILL"
      kill -9 "$pid" >/dev/null 2>&1 || true
      break
    fi
    sleep 1
    ((waited++))
  done

  if kill -0 "$pid" >/dev/null 2>&1; then
    warn "$name (PID $pid) could not be terminated"
    return 1
  fi

  info "$name (PID $pid) stopped"
  return 0
}

stop_service() {
  local name=$1
  local pid_file=$2
  local cleanup_cmd=${3:-}

  if [[ ! -f "$pid_file" ]]; then
    info "$name PID file not found ($pid_file); assuming not running"
    return 0
  fi

  local pids
  if ! pids=$(read_pids "$pid_file" 2>/dev/null); then
    warn "Could not read $name PID file $pid_file"
    return 1
  fi

  local status=0
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    if ! stop_pid "$name" "$pid"; then
      status=1
    fi
  done <<< "$pids"

  rm -f "$pid_file"

  if [[ -n "$cleanup_cmd" ]]; then
    eval "$cleanup_cmd" || warn "$name cleanup command failed"
  fi

  return "$status"
}

stop_brew_ollama_if_needed() {
  if ! command -v brew >/dev/null 2>&1; then
    return
  fi
  if brew services list 2>/dev/null | awk '$1=="ollama" {print $2, $3}' | grep -q "started"; then
    info "Stopping Ollama via brew services"
    if ! brew services stop ollama >> "$LOG_DIR/ollama.log" 2>&1; then
      warn "brew services stop ollama failed"
    fi
  fi
}

CORE_PID_FILE="$PID_DIR/core.pid"
WEB_PID_FILE="$PID_DIR/web.pid"
CP_PID_FILE="$PID_DIR/cp.pid"
OLLAMA_PID_FILE="$PID_DIR/ollama.pid"

status=0

stop_service "Core API" "$CORE_PID_FILE" || status=1
stop_service "Web UI" "$WEB_PID_FILE" || status=1
stop_service "Control Panel++" "$CP_PID_FILE" || status=1

if [[ -f "$OLLAMA_PID_FILE" ]]; then
  if ! stop_service "Ollama" "$OLLAMA_PID_FILE" ""; then
    status=1
  fi
fi

stop_brew_ollama_if_needed

if (( status == 0 )); then
  info "All services stopped."
else
  warn "One or more services may not have terminated cleanly."
fi

exit "$status"
