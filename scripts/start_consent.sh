#!/bin/bash
# Start Consent Service
#
# Starts the Consent Service on port 8200 (auto-increments if occupied).
# Logs output to data/consent/logs/consent.log

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/data/consent/logs"
PID_FILE="$LOG_DIR/consent.pid"

# Create log directory
mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  Consent Service already running (PID: $PID)"
        echo "   Use ./scripts/stop_consent.sh to stop it first"
        exit 1
    else
        echo "🧹 Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

echo "🔒 Starting Consent Service..."
echo "   Project root: $PROJECT_ROOT"
echo "   Logs: $LOG_DIR/consent.log"

# Start service in background
cd "$PROJECT_ROOT"
PYTHONPATH="$PROJECT_ROOT/ReDNACoreDemo:$PYTHONPATH" \
    python3 ReDNACoreDemo/services/consent/run_consent.py \
    > "$LOG_DIR/consent.log" 2>&1 &

CONSENT_PID=$!
echo $CONSENT_PID > "$PID_FILE"

echo "   PID: $CONSENT_PID"

# Wait for health check (max 10 seconds)
echo "🔍 Waiting for health check..."
for i in {1..10}; do
    # Read port from log file
    if [ -f "$PROJECT_ROOT/data/consent/consent_port.log" ]; then
        PORT=$(cat "$PROJECT_ROOT/data/consent/consent_port.log")
        if curl -s "http://127.0.0.1:$PORT/health" > /dev/null 2>&1; then
            echo "   ✅ Consent Service healthy on port $PORT"
            echo ""
            echo "📖 API Documentation: http://127.0.0.1:$PORT/docs"
            echo "🏥 Health Check:      http://127.0.0.1:$PORT/health"
            echo "📊 Logs:              tail -f $LOG_DIR/consent.log"
            echo ""
            exit 0
        fi
    fi
    sleep 1
done

echo "   ⚠️  Health check timeout (service may still be starting)"
echo "   Check logs: tail -f $LOG_DIR/consent.log"
exit 1
