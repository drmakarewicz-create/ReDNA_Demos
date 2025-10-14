#!/bin/bash
# ReDNA Phase 7 Verification Script
# Verifies all components are functional

set -e

echo ""
echo "=========================================="
echo "  ReDNA Phase 7 Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backend is running
echo "1. Checking backend API..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend API is running on port 8000"
else
    echo -e "${RED}✗${NC} Backend API is not running"
    echo "   Start with: cd ReDNACoreDemo && python3 -m uvicorn core.api:create_app --factory --reload --port 8000"
    exit 1
fi

# Test Phase 7 API endpoints
echo ""
echo "2. Testing Phase 7 API endpoints..."

test_endpoint() {
    local endpoint=$1
    local name=$2

    if curl -s "$endpoint" | jq -e '.ok == true' > /dev/null 2>&1; then
        echo -e "   ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "   ${RED}✗${NC} $name"
        return 1
    fi
}

FAILURES=0

test_endpoint "http://localhost:8000/ui/hc/brain_state/USER_DEMO1" "Brain State API" || ((FAILURES++))
test_endpoint "http://localhost:8000/ui/hc/tone_analysis/USER_DEMO1" "Tone Analysis API" || ((FAILURES++))
test_endpoint "http://localhost:8000/ui/hc/emotion_timeline/USER_DEMO1" "Emotion Timeline API" || ((FAILURES++))
test_endpoint "http://localhost:8000/coach/brain?user_id=USER_DEMO1" "Coach Brain API (reused)" || ((FAILURES++))
test_endpoint "http://localhost:8000/coach/chorus?user_id=USER_DEMO1" "Chorus API (reused)" || ((FAILURES++))

# Test dual coach compare (POST)
echo -n "   "
if curl -s -X POST "http://localhost:8000/ui/hc/dual_coach_compare?user_id=USER_DEMO1&coach_a=career_coach&coach_b=relationship_coach" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"Test"}' | jq -e '.ok == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Dual Coach Compare API"
else
    echo -e "${RED}✗${NC} Dual Coach Compare API"
    ((FAILURES++))
fi

# Check demo users exist
echo ""
echo "3. Checking demo users..."

check_user() {
    local user=$1
    if [ -d "data/users/$user" ]; then
        echo -e "   ${GREEN}✓${NC} $user exists"
        return 0
    else
        echo -e "   ${RED}✗${NC} $user missing"
        return 1
    fi
}

check_user "USER_DEMO1" || ((FAILURES++))
check_user "USER_DEMO2" || ((FAILURES++))
check_user "USER_DEMO3" || ((FAILURES++))

# Check frontend files
echo ""
echo "4. Checking frontend files..."

check_file() {
    local file=$1
    local name=$2
    if [ -f "$file" ]; then
        echo -e "   ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "   ${RED}✗${NC} $name missing"
        return 1
    fi
}

check_file "web/src/components/wow-factor/coach-brain-visualizer.tsx" "Coach Brain Visualizer" || ((FAILURES++))
check_file "web/src/components/wow-factor/chorus-preview.tsx" "Chorus Preview" || ((FAILURES++))
check_file "web/src/components/wow-factor/tone-echo.tsx" "Tone Echo" || ((FAILURES++))
check_file "web/src/components/wow-factor/trait-timeline.tsx" "Trait Timeline" || ((FAILURES++))
check_file "web/src/components/wow-factor/dual-coach-compare.tsx" "Dual Coach Compare" || ((FAILURES++))
check_file "web/src/components/wow-factor/emotion-timeline.tsx" "Emotion Timeline" || ((FAILURES++))
check_file "web/src/components/wow-factor/permission-overlay.tsx" "Permission Overlay" || ((FAILURES++))
check_file "web/src/components/wow-factor/wow-factor-dashboard.tsx" "Wow Factor Dashboard" || ((FAILURES++))
check_file "web/src/app/wow-demo/page.tsx" "Demo Page" || ((FAILURES++))

# Check documentation
echo ""
echo "5. Checking documentation..."

check_file "ReDNACoreDemo/docs/HC_WOW_FACTOR_PHASE7.md" "Phase 7 Documentation" || ((FAILURES++))
check_file "PHASE7_COMPLETION_SUMMARY.md" "Completion Summary" || ((FAILURES++))

# Check if web UI is running
echo ""
echo "6. Checking web UI..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Web UI is running on port 3000"
    echo "   Dashboard: http://localhost:3000/wow-demo"
else
    echo -e "${YELLOW}⚠${NC} Web UI is not running (optional)"
    echo "   Start with: cd web && npm run dev"
fi

# Summary
echo ""
echo "=========================================="
echo "  Verification Summary"
echo "=========================================="

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Phase 7 is ready for demo."
    echo "Visit: http://localhost:3000/wow-demo"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $FAILURES check(s) failed${NC}"
    echo ""
    echo "Please review the errors above and:"
    echo "  1. Ensure backend is running"
    echo "  2. Run: python3 scripts/create_demo_users_phase7.py"
    echo "  3. Check that all files were created correctly"
    echo ""
    exit 1
fi
