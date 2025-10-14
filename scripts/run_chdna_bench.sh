#!/bin/bash
# One-command ChatDNA benchmark runner
# Validates bundles, runs smoke test, and executes mini-bench with assertions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 ChatDNA Benchmark Suite"
echo "=========================="
echo ""

# Step 1: Validate bundles
echo "Step 1: Validating persona bundles..."
bash "$SCRIPT_DIR/validate_chatdna_bundles.sh"
echo ""

# Step 2: Smoke test - call /panel for one persona
echo "Step 2: Smoke test (ChatDNA panel endpoint)..."
SMOKE_PERSONA="persona_hemingway"
SMOKE_URL="http://127.0.0.1:8000/api/coach/chatdna_coach/panel?user_id=$SMOKE_PERSONA"

echo -n "   GET $SMOKE_URL ... "
SMOKE_RESPONSE=$(curl -s -w "\n%{http_code}" "$SMOKE_URL")
SMOKE_CODE=$(echo "$SMOKE_RESPONSE" | tail -n 1)
SMOKE_BODY=$(echo "$SMOKE_RESPONSE" | sed '$d')

if [ "$SMOKE_CODE" = "200" ]; then
    # Check if response contains expected fields
    if echo "$SMOKE_BODY" | grep -q '"snapshot"'; then
        echo "✅ PASS (200 OK, contains snapshot)"
    else
        echo "❌ FAIL (200 OK but missing expected fields)"
        echo "Response: $SMOKE_BODY"
        exit 1
    fi
else
    echo "❌ FAIL (HTTP $SMOKE_CODE)"
    echo "Response: $SMOKE_BODY"
    exit 1
fi
echo ""

# Step 3: Run mini-bench
echo "Step 3: Running mini-bench (5 personas, 2 prompts each)..."
python3 "$PROJECT_ROOT/eval/chatdna/harness.py" --mini
echo ""

# Step 4: Verify metrics.json exists and has valid structure
METRICS_PATH="$PROJECT_ROOT/eval/chatdna/leaderboards/metrics.json"
echo "Step 4: Verifying metrics output..."
echo -n "   Checking $METRICS_PATH ... "

if [ -f "$METRICS_PATH" ]; then
    # Check if JSON is valid
    if python3 -c "
import json
with open('$METRICS_PATH') as f:
    data = json.load(f)
    assert 'leaderboard' in data, 'Missing leaderboard'
    assert 'aa_tests' in data, 'Missing aa_tests'
    assert len(data['personas']) > 0, 'No personas'
" 2>&1; then
        echo "✅ PASS (valid metrics.json)"
    else
        echo "❌ FAIL (invalid metrics.json structure)"
        exit 1
    fi
else
    echo "❌ FAIL (metrics.json not found)"
    exit 1
fi
echo ""

# Step 5: Assert A/A > 0.5 for at least one persona (sanity check)
echo "Step 5: Asserting A/A scores > 0.5 (sanity check)..."
ASSERTION_PASSED=$(python3 -c "
import json
with open('$METRICS_PATH') as f:
    data = json.load(f)
    aa_tests = data['aa_tests']
    high_aa_count = sum(1 for persona, result in aa_tests.items() if result['mean'] > 0.5)
    print(high_aa_count)
")

if [ "$ASSERTION_PASSED" -gt 0 ]; then
    echo "   ✅ PASS ($ASSERTION_PASSED persona(s) with A/A > 0.5)"
else
    echo "   ❌ FAIL (No personas with A/A > 0.5 - check /render endpoint)"
    exit 1
fi
echo ""

echo "=========================="
echo "✅ All benchmark steps passed!"
echo "=========================="
exit 0
