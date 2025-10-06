#!/usr/bin/env bash
# scripts/smoke_check.sh
# Quick health check for Core and UCNRR services

set -e

CORE_PORT=${CORE_PORT:-8015}
UCNRR_PORT=${UCNRR_PORT:-8011}

echo "=========================================="
echo "ReDNA Smoke Check"
echo "=========================================="
echo ""

echo "== Core Health Check =="
CORE_URL="http://127.0.0.1:${CORE_PORT}/health"
if curl -s --max-time 3 "$CORE_URL" > /dev/null 2>&1; then
    echo "✓ Core is UP at $CORE_URL"
    curl -s "$CORE_URL" | python3 -m json.tool 2>/dev/null || echo "  (Response received but not valid JSON)"
else
    echo "✗ Core is DOWN or unreachable at $CORE_URL"
fi
echo ""

echo "== UCNRR Health Check =="
UCNRR_URL="http://127.0.0.1:${UCNRR_PORT}/api/health"
if curl -s --max-time 3 "$UCNRR_URL" > /dev/null 2>&1; then
    echo "✓ UCNRR is UP at $UCNRR_URL"
    curl -s "$UCNRR_URL" | python3 -m json.tool 2>/dev/null || echo "  (Response received but not valid JSON)"
else
    echo "✗ UCNRR is DOWN or unreachable at $UCNRR_URL"
fi
echo ""

echo "== Core → UCNRR Integration Check =="
CORE_UCNRR_URL="http://127.0.0.1:${CORE_PORT}/ui/ucnrr/health"
if curl -s --max-time 3 "$CORE_UCNRR_URL" > /dev/null 2>&1; then
    RESPONSE=$(curl -s "$CORE_UCNRR_URL")
    REACHABLE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('reachable', False))" 2>/dev/null || echo "false")
    if [ "$REACHABLE" = "True" ]; then
        echo "✓ Core can reach UCNRR"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "  (Response received but not valid JSON)"
    else
        echo "✗ Core CANNOT reach UCNRR"
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null
    fi
else
    echo "✗ Core integration endpoint is DOWN or unreachable at $CORE_UCNRR_URL"
fi
echo ""

echo "=========================================="
echo "Smoke check complete"
echo "=========================================="
