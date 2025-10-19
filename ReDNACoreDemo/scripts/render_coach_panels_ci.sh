#!/bin/bash
# Headless render smoke test for all coaches with fixtures
# Usage: ./scripts/render_coach_panels_ci.sh

set -e

echo "🎨 Coach Panel Render Smoke Test"
echo "=================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"

EXIT_CODE=0
TOTAL_COACHES=0
SUCCESSFUL_RENDERS=0
FAILED_RENDERS=0

# Check if API is running
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
    echo "❌ Core API not running at $API_BASE"
    echo "   Start it with: PYTHONPATH=... python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8000"
    exit 1
fi

echo "✅ Core API is running"
echo ""

# Get list of coaches from Workshop API
coaches_json=$(curl -s "$API_BASE/api/workshop/coaches?source=delegation")
coach_ids=$(echo "$coaches_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(' '.join([c['id'] for c in data.get('coaches', [])]))" 2>/dev/null || echo "")

if [ -z "$coach_ids" ]; then
    echo "⚠️  No coaches found"
    exit 0
fi

for coach_id in $coach_ids; do
    TOTAL_COACHES=$((TOTAL_COACHES + 1))
    echo "Testing: $coach_id"

    # Test preview endpoint
    response=$(curl -s -w "\n%{http_code}" "$API_BASE/api/workshop/coaches/$coach_id/preview?user_id=TEST&data_mode=stub")
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -eq 200 ]; then
        # Check performance
        compose_ms=$(echo "$body" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('performance', {}).get('compose_ms', 999))" 2>/dev/null || echo "999")

        if (( $(echo "$compose_ms < 200" | bc -l) )); then
            echo "  ✅ Rendered in ${compose_ms}ms (target: ≤200ms)"
            SUCCESSFUL_RENDERS=$((SUCCESSFUL_RENDERS + 1))
        else
            echo "  ⚠️  Slow render: ${compose_ms}ms (target: ≤200ms)"
            SUCCESSFUL_RENDERS=$((SUCCESSFUL_RENDERS + 1))
        fi
    else
        echo "  ❌ Failed (HTTP $http_code)"
        FAILED_RENDERS=$((FAILED_RENDERS + 1))
        EXIT_CODE=1
    fi
done

echo ""
echo "=================================="
echo "Summary:"
echo "  Total:      $TOTAL_COACHES"
echo "  Success:    $SUCCESSFUL_RENDERS"
echo "  Failed:     $FAILED_RENDERS"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All coach panels rendered successfully!"
else
    echo "❌ Some coach panels failed to render"
fi

exit $EXIT_CODE
