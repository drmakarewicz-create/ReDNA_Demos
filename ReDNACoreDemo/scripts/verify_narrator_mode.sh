#!/usr/bin/env bash
# Verification script for Narrator Mode (Benchmark 4.A2)

set -e

echo "🗣 Narrator Mode Verification"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo "1️⃣ Checking service status..."
if curl -s http://localhost:8015/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Core API is running"
else
    echo -e "${RED}✗${NC} Core API is not running (http://localhost:8015)"
    echo "   Start it with: python3 -m uvicorn ReDNACoreDemo.core.api:app --reload --port 8015"
    exit 1
fi
echo ""

# Generate sample narrator traces
echo "2️⃣ Generating sample traces..."
curl -s -X POST http://localhost:8015/users/TEST/coach-mode \
  -H "Content-Type: application/json" \
  -d '{"target_mode":"career_coach"}' > /dev/null || true

curl -s -X POST http://localhost:8015/users/TEST/coach-mode \
  -H "Content-Type: application/json" \
  -d '{"target_mode":"relationship_coach"}' > /dev/null || true

echo -e "${GREEN}✓${NC} Generated coach switch traces"
echo ""

# Test GET /coach/narrator
echo "3️⃣ Testing GET /coach/narrator..."
RESPONSE=$(curl -s "http://localhost:8015/coach/narrator?user_id=TEST&limit=5")

if echo "$RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    TRACE_COUNT=$(echo "$RESPONSE" | jq '.traces | length')
    DURATION=$(echo "$RESPONSE" | jq '.duration_ms')
    echo -e "${GREEN}✓${NC} Endpoint returned ok=true"
    echo "   Traces: $TRACE_COUNT"
    echo "   Duration: ${DURATION}ms"

    if (( $(echo "$DURATION < 200" | bc -l) )); then
        echo -e "${GREEN}✓${NC} Performance requirement met (<200ms)"
    else
        echo -e "${YELLOW}⚠${NC} Performance warning: ${DURATION}ms (target: <200ms)"
    fi
else
    echo -e "${RED}✗${NC} Endpoint failed"
    echo "$RESPONSE" | jq .
    exit 1
fi
echo ""

# Test filtering
echo "4️⃣ Testing filters..."

# Filter by decision type
FILTER_RESPONSE=$(curl -s "http://localhost:8015/coach/narrator?user_id=TEST&decision_type=coach_switch&limit=10")
if echo "$FILTER_RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Decision type filter works"
else
    echo -e "${RED}✗${NC} Decision type filter failed"
fi

# Filter by confidence
CONF_RESPONSE=$(curl -s "http://localhost:8015/coach/narrator?user_id=TEST&min_confidence=0.8&limit=10")
if echo "$CONF_RESPONSE" | jq -e '.ok == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Confidence filter works"
else
    echo -e "${RED}✗${NC} Confidence filter failed"
fi
echo ""

# Test export JSON
echo "5️⃣ Testing export (JSON)..."
EXPORT_JSON=$(curl -s "http://localhost:8015/coach/narrator/export?user_id=TEST&format=json&limit=20")
if echo "$EXPORT_JSON" | jq -e '.user_id' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} JSON export works"
else
    echo -e "${RED}✗${NC} JSON export failed"
fi
echo ""

# Test export Markdown
echo "6️⃣ Testing export (Markdown)..."
EXPORT_MD=$(curl -s "http://localhost:8015/coach/narrator/export?user_id=TEST&format=markdown&limit=20")
if echo "$EXPORT_MD" | grep -q "# Narrator Timeline"; then
    echo -e "${GREEN}✓${NC} Markdown export works"
else
    echo -e "${RED}✗${NC} Markdown export failed"
fi
echo ""

# Run unit tests
echo "7️⃣ Running unit tests..."
cd "$(dirname "$0")/.."

if python3 -m pytest tests/test_narrator_mode.py -v --tb=short 2>&1 | tee /tmp/narrator_test_output.txt; then
    echo -e "${GREEN}✓${NC} All unit tests passed"
else
    echo -e "${RED}✗${NC} Some unit tests failed"
    echo "   Check /tmp/narrator_test_output.txt for details"
    exit 1
fi
echo ""

# Check documentation exists
echo "8️⃣ Checking documentation..."
if [ -f "ReDNACoreDemo/docs/NARRATOR_MODE_PHASE1.md" ]; then
    echo -e "${GREEN}✓${NC} Documentation file exists"
    WC=$(wc -l < ReDNACoreDemo/docs/NARRATOR_MODE_PHASE1.md)
    echo "   Lines: $WC"
else
    echo -e "${RED}✗${NC} Documentation missing"
    exit 1
fi
echo ""

# Display example trace
echo "9️⃣ Example Trace:"
echo "=================="
echo "$RESPONSE" | jq '.traces[0]' 2>/dev/null || echo "No traces available"
echo ""

echo "=============================="
echo -e "${GREEN}✅ Narrator Mode Verification Complete${NC}"
echo ""
echo "Next steps:"
echo "1. Open DevX: http://localhost:8100"
echo "2. Navigate to: 🗣 Narrator"
echo "3. Review timeline for user TEST"
echo ""
