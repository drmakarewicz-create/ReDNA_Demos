#!/bin/bash
# Unified startup script for all ReDNA services
# Makes the system less fragile by managing all services together

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service ports
CORE_PORT=8000
UCNRR_PORT=8011
NEXT_PORT=3001

# Log files
LOG_DIR="$PROJECT_ROOT/.run"
mkdir -p "$LOG_DIR"
CORE_LOG="$LOG_DIR/core.log"
UCNRR_LOG="$LOG_DIR/ucnrr.log"
NEXT_LOG="$LOG_DIR/next.log"

echo -e "${BLUE}🚀 Starting ReDNA Services${NC}"
echo "================================"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -ti:$port > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    local service=$2
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port already in use by $service, killing...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service=$2
    local max_attempts=30
    local attempt=0

    echo -n "   Waiting for $service to be ready..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}✗ Timeout${NC}"
    return 1
}

# Clean up old processes
echo -e "${BLUE}1. Cleaning up existing processes${NC}"
kill_port $CORE_PORT "Core API"
kill_port $UCNRR_PORT "UCNRR API"
kill_port $NEXT_PORT "Next.js"
echo -e "   ${GREEN}✓${NC} Cleanup complete"
echo ""

# Start Core API
echo -e "${BLUE}2. Starting Core API (port $CORE_PORT)${NC}"
cd "$PROJECT_ROOT"

# Check for LLM API keys
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "   ${YELLOW}⚠️  No LLM API key found. Head Coach will run in MOCK MODE.${NC}"
    echo -e "   ${YELLOW}   Set OPENAI_API_KEY or ANTHROPIC_API_KEY for live responses.${NC}"
fi

PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/ReDNACoreDemo:$PYTHONPATH" \
    UCNRR_BASE="http://127.0.0.1:$UCNRR_PORT" \
    CORE_CURIOSITY_ENABLED=1 \
    .venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app \
    --factory --reload --port $CORE_PORT \
    > "$CORE_LOG" 2>&1 &
CORE_PID=$!
echo $CORE_PID > "$LOG_DIR/core.pid"
echo "   PID: $CORE_PID"
if wait_for_service "http://127.0.0.1:$CORE_PORT/health" "Core API"; then
    echo -e "   ${GREEN}✓${NC} Core API started successfully"
else
    echo -e "   ${RED}✗${NC} Core API failed to start. Check logs: tail -f $CORE_LOG"
    exit 1
fi
echo ""

# Start UCNRR API
echo -e "${BLUE}3. Starting UCNRR API (port $UCNRR_PORT)${NC}"
cd "$PROJECT_ROOT/UCN_RR_Demo"
../.venv/bin/python -m uvicorn ucnrr_app:app \
    --host 0.0.0.0 --port $UCNRR_PORT --reload \
    > "$UCNRR_LOG" 2>&1 &
UCNRR_PID=$!
echo $UCNRR_PID > "$LOG_DIR/ucnrr.pid"
echo "   PID: $UCNRR_PID"
if wait_for_service "http://127.0.0.1:$UCNRR_PORT/health" "UCNRR API"; then
    echo -e "   ${GREEN}✓${NC} UCNRR API started successfully"
else
    echo -e "   ${YELLOW}⚠️${NC}  UCNRR API may not be ready. Check logs: tail -f $UCNRR_LOG"
    # Don't exit - UCNRR is optional
fi
echo ""

# Start Next.js
echo -e "${BLUE}4. Starting Next.js (port $NEXT_PORT)${NC}"
cd "$PROJECT_ROOT/web"
rm -rf .next  # Clean build
PORT=$NEXT_PORT npx next dev \
    > "$NEXT_LOG" 2>&1 &
NEXT_PID=$!
echo $NEXT_PID > "$LOG_DIR/next.pid"
echo "   PID: $NEXT_PID"
if wait_for_service "http://127.0.0.1:$NEXT_PORT" "Next.js"; then
    echo -e "   ${GREEN}✓${NC} Next.js started successfully"
else
    echo -e "   ${RED}✗${NC} Next.js failed to start. Check logs: tail -f $NEXT_LOG"
    exit 1
fi
echo ""

# Summary
echo "================================"
echo -e "${GREEN}✓ All services started successfully!${NC}"
echo ""
echo "📍 Service URLs:"
echo "   Core API:  http://127.0.0.1:$CORE_PORT"
echo "   UCNRR API: http://127.0.0.1:$UCNRR_PORT"
echo "   Web UI:    http://127.0.0.1:$NEXT_PORT"
echo ""
echo "📋 Quick links:"
echo "   BeliefDNA Coach (Utilitarian): http://127.0.0.1:$NEXT_PORT/?user=persona_utilitarian&persona=beliefdna_coach"
echo "   ChatDNA Coach (Obama):         http://127.0.0.1:$NEXT_PORT/?user=persona_obama&persona=chatdna_coach"
echo "   Head Coach (TEST):             http://127.0.0.1:$NEXT_PORT/?user=TEST"
echo ""
echo "📊 Process IDs:"
echo "   Core:   $CORE_PID"
echo "   UCNRR:  $UCNRR_PID"
echo "   Next:   $NEXT_PID"
echo ""
echo "📝 Log files:"
echo "   Core:   $CORE_LOG"
echo "   UCNRR:  $UCNRR_LOG"
echo "   Next:   $NEXT_LOG"
echo ""
echo "🛑 To stop all services: ./scripts/stop_all_services.sh"
echo "📊 To check status:      ./scripts/check_services.sh"
echo ""
