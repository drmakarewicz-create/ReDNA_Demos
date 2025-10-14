#!/bin/bash
# Stop DevX (backend + frontend)
# Does NOT affect Core, UCNRR, or CP++ services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/ReDNACoreDemo/devx/logs"

echo "🛑 Stopping DevX..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Stop backend
if [ -f "$LOG_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$LOG_DIR/backend.pid")
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "   Stopping backend (PID: $BACKEND_PID)..."
        kill "$BACKEND_PID"
        rm "$LOG_DIR/backend.pid"
        echo "   ✅ Backend stopped"
    else
        echo "   ⚠️  Backend not running"
        rm "$LOG_DIR/backend.pid"
    fi
else
    # Try to kill by port
    if lsof -ti:8100 > /dev/null 2>&1; then
        echo "   Stopping backend on port 8100..."
        lsof -ti:8100 | xargs kill
        echo "   ✅ Backend stopped"
    else
        echo "   ⚠️  Backend not running"
    fi
fi

# Stop frontend
if [ -f "$LOG_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$LOG_DIR/frontend.pid")
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "   Stopping frontend (PID: $FRONTEND_PID)..."
        kill "$FRONTEND_PID"
        rm "$LOG_DIR/frontend.pid"
        echo "   ✅ Frontend stopped"
    else
        echo "   ⚠️  Frontend not running"
        rm "$LOG_DIR/frontend.pid"
    fi
else
    # Try to kill by port
    if lsof -ti:3100 > /dev/null 2>&1; then
        echo "   Stopping frontend on port 3100..."
        lsof -ti:3100 | xargs kill
        echo "   ✅ Frontend stopped"
    else
        echo "   ⚠️  Frontend not running"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DevX stopped"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
