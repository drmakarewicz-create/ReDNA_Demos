#!/bin/bash
# Check status of all ReDNA services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.run"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}📊 ReDNA Services Status${NC}"
echo "================================"
echo ""

# Function to check service
check_service() {
    local name=$1
    local port=$2
    local url=$3
    local pid_file="$LOG_DIR/${name}.pid"

    echo -e "${BLUE}$name (port $port)${NC}"

    # Check PID
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "   Process: ${GREEN}✓ Running${NC} (PID $PID)"
        else
            echo -e "   Process: ${RED}✗ Stopped${NC} (stale PID $PID)"
        fi
    else
        echo -e "   Process: ${YELLOW}? Unknown${NC} (no PID file)"
    fi

    # Check port
    if lsof -ti:$port > /dev/null 2>&1; then
        ACTUAL_PID=$(lsof -ti:$port)
        echo -e "   Port:    ${GREEN}✓ In use${NC} (PID $ACTUAL_PID)"
    else
        echo -e "   Port:    ${RED}✗ Free${NC}"
    fi

    # Check HTTP
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "   Health:  ${GREEN}✓ Responding${NC}"
    else
        echo -e "   Health:  ${RED}✗ Not responding${NC}"
    fi

    echo ""
}

check_service "Core API" 8000 "http://127.0.0.1:8000/health"
check_service "UCNRR API" 8011 "http://127.0.0.1:8011/health"
check_service "Next.js" 3001 "http://127.0.0.1:3001"

echo "================================"
echo ""
echo "💡 Commands:"
echo "   Start all:  ./scripts/start_all_services.sh"
echo "   Stop all:   ./scripts/stop_all_services.sh"
echo "   View logs:  tail -f .run/core.log"
echo "   View logs:  tail -f .run/ucnrr.log"
echo "   View logs:  tail -f .run/next.log"
echo ""
