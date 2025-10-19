#!/usr/bin/env bash
#
# ensure_ucnrr.sh
# ===============
#
# Validates environment and starts UCNRR if not already running.
# - Checks Ollama is reachable
# - Validates port availability
# - Starts UCNRR via uvicorn
#

set -euo pipefail

# Configuration
: "${UCNRR_LLM_PROVIDER:=ollama}"
: "${UCNRR_LLM_MODEL:=phi3:mini}"
: "${OLLAMA_BASE_URL:=http://127.0.0.1:11434}"
: "${UCNRR_PORT:=8017}"

UCNRR_LOG_FILE="${UCNRR_LOG_FILE:-/tmp/ucnrr.log}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# 1. Validate Ollama is reachable
log_info "Checking Ollama at $OLLAMA_BASE_URL..."
if ! curl -fsS "$OLLAMA_BASE_URL/api/tags" >/dev/null 2>&1; then
    log_error "Ollama not reachable at $OLLAMA_BASE_URL"
    log_info "Start Ollama with: ollama serve &"
    log_info "Pull model with: ollama pull $UCNRR_LLM_MODEL"
    exit 2
fi
log_info "Ollama is reachable"

# 2. Check if UCNRR is already running on port
if lsof -nP -iTCP:"$UCNRR_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    log_info "UCNRR already running on port $UCNRR_PORT"

    # Check health
    if curl -fsS "http://127.0.0.1:$UCNRR_PORT/health" >/dev/null 2>&1; then
        log_info "UCNRR health check passed"
        exit 0
    else
        log_warn "UCNRR is listening but health check failed"
    fi
else
    log_info "Port $UCNRR_PORT is available"
fi

# 3. Start UCNRR
log_info "Starting UCNRR on port $UCNRR_PORT..."
cd "$REPO_ROOT"

# Export environment
export PYTHONPATH="$REPO_ROOT"
export UCNRR_PORT
export UCNRR_LLM_PROVIDER
export UCNRR_LLM_MODEL
export OLLAMA_BASE_URL

# Start UCNRR in background
nohup python3 -m uvicorn UCN_RR_Demo.ucnrr_app:app \
    --host 127.0.0.1 \
    --port "$UCNRR_PORT" \
    --log-level info \
    > "$UCNRR_LOG_FILE" 2>&1 &

UCNRR_PID=$!
log_info "UCNRR started (PID $UCNRR_PID)"
log_info "Logs: $UCNRR_LOG_FILE"

# Wait for startup (max 10 seconds)
for i in {1..10}; do
    if curl -fsS "http://127.0.0.1:$UCNRR_PORT/health" >/dev/null 2>&1; then
        log_info "UCNRR is healthy"
        exit 0
    fi
    sleep 1
done

log_warn "UCNRR started but health check not passing yet"
log_info "Check logs: tail -f $UCNRR_LOG_FILE"
exit 0
