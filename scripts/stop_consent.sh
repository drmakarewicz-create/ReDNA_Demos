#!/bin/bash
# Stop Consent Service
#
# Stops the running Consent Service gracefully.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/data/consent/logs"
PID_FILE="$LOG_DIR/consent.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found. Consent Service may not be running."

    # Try to kill by port anyway
    if lsof -ti:8200,8201,8202 > /dev/null 2>&1; then
        echo "🔍 Found processes on Consent Service ports, killing..."
        lsof -ti:8200,8201,8202 | xargs kill 2>/dev/null || true
        echo "   ✅ Killed processes on ports 8200-8202"
    fi

    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "🛑 Stopping Consent Service (PID: $PID)..."
    kill "$PID"

    # Wait for graceful shutdown (max 5 seconds)
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "   ✅ Consent Service stopped gracefully"
            rm "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "   ⚠️  Graceful shutdown timeout, forcing..."
        kill -9 "$PID" 2>/dev/null || true
        echo "   ✅ Consent Service force-stopped"
    fi
else
    echo "⚠️  Process $PID not running, removing stale PID file"
fi

rm "$PID_FILE"
echo "✅ Consent Service stopped"
