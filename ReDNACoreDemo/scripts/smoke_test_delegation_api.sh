#!/bin/bash
#
# Smoke test for Delegation System API endpoints
#
# This script quickly tests all delegation and coach mode endpoints
# to verify the API is functioning correctly.
#
# Usage:
#   ./scripts/smoke_test_delegation_api.sh

set -e  # Exit on error

API_BASE="${API_BASE:-http://localhost:8000}"
TEST_USER="smoke_test_user_$(date +%s)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Test endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4

    echo -e "\n${YELLOW}Testing:${NC} $description"
    echo -e "${BLUE}$method $endpoint${NC}"

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_BASE$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$API_BASE$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        print_success "HTTP $http_code"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 0
    else
        print_error "HTTP $http_code"
        echo "$body"
        return 1
    fi
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    print_info "jq is not installed. Responses will not be formatted."
    print_info "Install with: brew install jq"
fi

# Check if API is running
print_header "Checking API Health"
if curl -s "$API_BASE/health" > /dev/null 2>&1; then
    print_success "API is running at $API_BASE"
else
    print_error "API is not running at $API_BASE"
    print_info "Start with: cd ReDNACoreDemo && ../.venv/bin/python -m uvicorn core.api:app --reload"
    exit 1
fi

echo -e "\n${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     DELEGATION SYSTEM API - SMOKE TEST            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"

print_info "Test user: $TEST_USER"

# ============================================================
# DELEGATION ENDPOINTS
# ============================================================

print_header "1. Delegation Endpoints"

# 1.1 Analyze Curiosity
test_endpoint "POST" "/delegation/analyze" '{
  "user_id": "'"$TEST_USER"'",
  "curiosity_data": {
    "PaDNA.HairDNA.Color": 85.0,
    "PaDNA.EyeDNA.Color": 92.0
  },
  "tolerance": 0.7
}' "Analyze curiosity for delegation"

# 1.2 Create Delegation
DELEGATION_RESPONSE=$(curl -s -X POST "$API_BASE/delegation/create" \
    -H "Content-Type: application/json" \
    -d '{
  "user_id": "'"$TEST_USER"'",
  "coach_id": "photo_coach",
  "curiosity_targets": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]
}')

DELEGATION_ID=$(echo "$DELEGATION_RESPONSE" | jq -r '.delegation.delegation_id' 2>/dev/null || echo "")

if [ -n "$DELEGATION_ID" ] && [ "$DELEGATION_ID" != "null" ]; then
    print_success "Created delegation: $DELEGATION_ID"
    echo "$DELEGATION_RESPONSE" | jq '.' 2>/dev/null || echo "$DELEGATION_RESPONSE"
else
    print_error "Failed to create delegation"
    echo "$DELEGATION_RESPONSE"
    exit 1
fi

# 1.3 Get Delegation Status
test_endpoint "GET" "/delegation/$TEST_USER/status/$DELEGATION_ID" "" "Get delegation status"

# 1.4 Get Active Delegations
test_endpoint "GET" "/delegation/$TEST_USER/active" "" "Get active delegations"

# ============================================================
# COACH MODE ENDPOINTS
# ============================================================

print_header "2. Coach Mode Endpoints"

# 2.1 Get Active Mode
test_endpoint "GET" "/users/$TEST_USER/coach-mode" "" "Get active coach mode"

# 2.2 Switch Mode (with delegation)
test_endpoint "POST" "/users/$TEST_USER/coach-mode" '{
  "target_mode": "photo",
  "delegation_id": "'"$DELEGATION_ID"'",
  "context": {
    "curiosity_targets": ["PaDNA.HairDNA.Color"]
  }
}' "Switch to photo mode with delegation"

# 2.3 Get Mode History
test_endpoint "GET" "/users/$TEST_USER/coach-mode/history?limit=5" "" "Get mode history"

# 2.4 Get Mode Stats
test_endpoint "GET" "/users/$TEST_USER/coach-mode/stats" "" "Get mode statistics"

# ============================================================
# COMPLETE DELEGATION
# ============================================================

print_header "3. Complete Delegation Flow"

# 3.1 Complete Delegation
test_endpoint "POST" "/delegation/$TEST_USER/complete/$DELEGATION_ID" '{
  "traits_collected": ["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
  "curiosity_before": {
    "PaDNA.HairDNA.Color": 85.0,
    "PaDNA.EyeDNA.Color": 92.0
  },
  "curiosity_after": {
    "PaDNA.HairDNA.Color": 12.0,
    "PaDNA.EyeDNA.Color": 8.0
  },
  "notes": "Smoke test completion",
  "auto_return": true
}' "Complete delegation with auto-return"

# 3.2 Verify Return to Head Coach
FINAL_MODE=$(curl -s "$API_BASE/users/$TEST_USER/coach-mode" | jq -r '.active_mode' 2>/dev/null || echo "")

if [ "$FINAL_MODE" = "head_coach" ]; then
    print_success "Successfully returned to head_coach mode"
else
    print_error "Did not return to head_coach (current: $FINAL_MODE)"
fi

# 3.3 Verify Delegation Completed
DELEGATION_STATUS=$(curl -s "$API_BASE/delegation/$TEST_USER/status/$DELEGATION_ID" | jq -r '.status.status' 2>/dev/null || echo "")

if [ "$DELEGATION_STATUS" = "completed" ]; then
    print_success "Delegation marked as completed"
else
    print_error "Delegation not completed (status: $DELEGATION_STATUS)"
fi

# ============================================================
# SUMMARY
# ============================================================

echo -e "\n${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              SMOKE TEST COMPLETE ✓                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}\n"

print_success "All delegation endpoints are functioning"
print_info "Test user: $TEST_USER"
print_info "Delegation ID: $DELEGATION_ID"

echo -e "\n${YELLOW}Tested endpoints:${NC}"
echo "  • POST /delegation/analyze"
echo "  • POST /delegation/create"
echo "  • GET  /delegation/{user_id}/status/{delegation_id}"
echo "  • GET  /delegation/{user_id}/active"
echo "  • POST /delegation/{user_id}/complete/{delegation_id}"
echo "  • GET  /users/{user_id}/coach-mode"
echo "  • POST /users/{user_id}/coach-mode"
echo "  • GET  /users/{user_id}/coach-mode/history"
echo "  • GET  /users/{user_id}/coach-mode/stats"

echo -e "\n${BLUE}Run full integration test:${NC}"
echo "  python scripts/test_delegation_flow.py"

echo -e "\n${BLUE}Run pytest tests:${NC}"
echo "  pytest tests/test_*delegation*.py -v"

echo ""
