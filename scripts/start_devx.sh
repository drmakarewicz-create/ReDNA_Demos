#!/bin/bash
# Start DevX (backend + frontend)
# Does NOT affect Core, UCNRR, or CP++ services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEVX_ROOT="$PROJECT_ROOT/ReDNACoreDemo/devx"
LOG_DIR="$DEVX_ROOT/logs"

mkdir -p "$LOG_DIR"

echo "🚀 Starting DevX..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if backend is already running
if lsof -ti:8100 > /dev/null 2>&1; then
    echo "⚠️  DevX backend already running on port 8100"
else
    echo "📡 Starting DevX backend..."
    cd "$PROJECT_ROOT"
    PYTHONPATH="$PROJECT_ROOT/ReDNACoreDemo:$PYTHONPATH" \
        python3 ReDNACoreDemo/devx/backend/run_devx.py > "$LOG_DIR/backend.log" 2>&1 &

    BACKEND_PID=$!
    echo $BACKEND_PID > "$LOG_DIR/backend.pid"
    echo "   ✅ Backend started (PID: $BACKEND_PID)"

    # Wait for backend to be ready
    for i in {1..10}; do
        if curl -s http://127.0.0.1:8100/health > /dev/null 2>&1; then
            echo "   ✅ Backend health check passed"
            break
        fi
        if [ $i -eq 10 ]; then
            echo "   ❌ Backend failed to start (timeout)"
            exit 1
        fi
        sleep 1
    done
fi

# Check if frontend is already running
FRONTEND_PORT=3100

if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
    echo "⚠️  DevX frontend already running on port 3100"
else
    echo "🎨 Starting DevX frontend..."
    cd "$DEVX_ROOT/frontend"

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "   📦 Installing frontend dependencies..."
        npm install
    fi

    # Start frontend
    npm run dev -- --port $FRONTEND_PORT > "$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"
    echo "   ✅ Frontend started (PID: $FRONTEND_PID)"

    echo "   ⏳ Waiting for DevX frontend to be ready..."
    # Detect port from log if Vite auto-selected a fallback
    for i in {1..30}; do
        if [ -f "$LOG_DIR/frontend.log" ]; then
            CANDIDATE=$(grep -Eo 'http://(127\.0\.0\.1|localhost):[0-9]+' "$LOG_DIR/frontend.log" | tail -n 1)
            if [ -n "$CANDIDATE" ]; then
                FRONTEND_PORT=${CANDIDATE##*:}
                break
            fi
        fi
        sleep 1
    done

    for i in {1..30}; do
        if curl -s "http://127.0.0.1:$FRONTEND_PORT" > /dev/null 2>&1; then
            echo "   ✅ Frontend listening on port $FRONTEND_PORT"
            if command -v python3 >/dev/null 2>&1; then
                python3 - <<PY
import webbrowser
webbrowser.open("http://127.0.0.1:$FRONTEND_PORT")
PY
            fi
            break
        fi
        sleep 1
    done
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DevX is running!"
echo ""
echo "   Backend:  http://127.0.0.1:8100"
echo "   Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo "   Logs:     $LOG_DIR"
echo ""
echo "To stop DevX: ./scripts/stop_devx.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
