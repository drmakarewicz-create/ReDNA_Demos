#!/bin/bash
# Comprehensive smoke test for all coach mode switches
# Tests both backend API and verifies mode switching works correctly

set -e

API_BASE="${API_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-TEST}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

echo "========================================="
echo "  Coach Mode Switching Smoke Test"
echo "========================================="
echo "API Base: $API_BASE"
echo "User ID: $USER_ID"
echo ""

# Function to test coach mode switch
test_coach_switch() {
    local coach_id=$1
    local expected_display_name=$2

    echo -n "Testing switch to ${coach_id}... "

    response=$(curl -s -X POST "${API_BASE}/users/${USER_ID}/coach-mode" \
        -H "Content-Type: application/json" \
        -d "{\"target_mode\":\"${coach_id}\",\"context\":{\"source\":\"smoke_test\"}}")

    # Check if request was successful
    ok=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('ok', False))" 2>/dev/null)

    if [ "$ok" = "True" ]; then
        # Verify the mode was actually set
        new_mode=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('new_mode', ''))" 2>/dev/null)
        display_name=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('mode_info', {}).get('display_name', ''))" 2>/dev/null)

        if [ "$new_mode" = "$coach_id" ]; then
            echo -e "${GREEN}✓ PASS${NC} (mode: ${new_mode}, display: ${display_name})"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            echo -e "${RED}✗ FAIL${NC} - Expected mode ${coach_id}, got ${new_mode}"
            echo "  Response: $response"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        error_msg=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', 'Unknown error'))" 2>/dev/null)
        echo -e "${RED}✗ FAIL${NC} - ${error_msg}"
        echo "  Response: $response"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Function to verify mode persists
verify_mode_persists() {
    local expected_mode=$1

    echo -n "Verifying mode persists (${expected_mode})... "

    # Get current mode via user data
    response=$(curl -s "${API_BASE}/users/${USER_ID}")
    current_mode=$(echo $response | python3 -c "import sys, json; print(json.load(sys.stdin).get('coach_mode', ''))" 2>/dev/null)

    if [ "$current_mode" = "$expected_mode" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} - Expected ${expected_mode}, got ${current_mode}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "=== Testing All Coach Mode Switches ==="
echo ""

# Test each coach mode
test_coach_switch "head_coach" "Head Coach"
verify_mode_persists "head_coach"
echo ""

test_coach_switch "relationship_coach" "Relationship Coach"
verify_mode_persists "relationship_coach"
echo ""

test_coach_switch "career_coach" "Career Coach"
verify_mode_persists "career_coach"
echo ""

test_coach_switch "personality_test_coach" "Personality Test Coach"
verify_mode_persists "personality_test_coach"
echo ""

test_coach_switch "photo_coach" "Photo Coach"
verify_mode_persists "photo_coach"
echo ""

test_coach_switch "padna_coach" "PaDNA Coach"
verify_mode_persists "padna_coach"
echo ""

# Test legacy aliases
echo "=== Testing Legacy Aliases ==="
echo ""

test_coach_switch "photo" "Photo Coach"
echo ""

test_coach_switch "padna" "PaDNA Coach"
echo ""

test_coach_switch "relationship" "Relationship Coach"
echo ""

# Switch back to head coach for cleanup
test_coach_switch "head_coach" "Head Coach"
echo ""

echo "========================================="
echo "  Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. ✗${NC}"
    exit 1
fi
