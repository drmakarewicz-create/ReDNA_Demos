#!/bin/bash
# Stop all ReDNA services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.run"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Stopping all ReDNA services${NC}"
echo "================================"
echo ""

# Stop by PID files
for service in core ucnrr next; do
    PID_FILE="$LOG_DIR/$service.pid"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "Stopping $service (PID $PID)... ${GREEN}✓${NC}"
            kill $PID 2>/dev/null || kill -9 $PID 2>/dev/null
        else
            echo -e "Service $service (PID $PID) not running"
        fi
        rm "$PID_FILE"
    fi
done

# Backup: kill by port
for port in 8000 8011 3001; do
    if lsof -ti:$port > /dev/null 2>&1; then
        echo -e "Killing remaining process on port $port... ${GREEN}✓${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null || true
    fi
done

echo ""
echo -e "${GREEN}✓ All services stopped${NC}"
