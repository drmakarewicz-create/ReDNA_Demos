#!/usr/bin/env bash
#
# verify_ucnrr_system.sh
# ======================
#
# End-to-end verification of UCNRR connectivity system.
#

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

DEVX_BASE="${DEVX_BASE:-http://127.0.0.1:8012}"
CORE_BASE="${CORE_BASE:-http://127.0.0.1:8004}"
UCNRR_BASE="${UCNRR_BASE:-http://127.0.0.1:8017}"

pass() {
    echo -e "${GREEN}✓${NC} $*"
}

fail() {
    echo -e "${RED}✗${NC} $*"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_service() {
    local name=$1
    local url=$2

    if curl -fsS "$url" >/dev/null 2>&1; then
        pass "$name is reachable at $url"
        return 0
    else
        fail "$name is NOT reachable at $url"
        return 1
    fi
}

section "1. Service Health Checks"

check_service "DevX Backend" "$DEVX_BASE/health" || exit 1
check_service "Core API" "$CORE_BASE/health" || exit 1

# UCNRR may not be running yet, that's ok
if check_service "UCNRR" "$UCNRR_BASE/health"; then
    :
else
    warn "UCNRR not running (will be started by ensure endpoint)"
fi

section "2. UCNRR Status Endpoint"

info "Fetching UCNRR status from DevX..."
STATUS_RESP=$(curl -s -w "\n%{http_code}" "$DEVX_BASE/devx/api/stack/ucnrr/status" 2>/dev/null)
STATUS_CODE=$(echo "$STATUS_RESP" | tail -n 1)
STATUS_BODY=$(echo "$STATUS_RESP" | sed '$d')

if [ "$STATUS_CODE" != "200" ]; then
    fail "UCNRR status endpoint failed (HTTP $STATUS_CODE)"
    echo "$STATUS_BODY"
    exit 1
else
    pass "UCNRR status endpoint is working (HTTP $STATUS_CODE)"
    echo "$STATUS_BODY" | jq '.' 2>/dev/null || echo "$STATUS_BODY"
    STATUS="$STATUS_BODY"
fi

section "3. UCNRR Ensure Endpoint"

info "Calling ensure endpoint to start/verify UCNRR..."
ENSURE_RESULT=$(curl -fsS -X POST "$DEVX_BASE/devx/api/stack/ucnrr/ensure" \
    -H "Content-Type: application/json" \
    -d '{"force_restart": false}' 2>/dev/null || echo '{}')

if [ -n "$ENSURE_RESULT" ] && [ "$ENSURE_RESULT" != "{}" ]; then
    pass "UCNRR ensure endpoint responded"
    echo "$ENSURE_RESULT" | jq '.' 2>/dev/null || echo "$ENSURE_RESULT"

    STATUS=$(echo "$ENSURE_RESULT" | jq -r '.status' 2>/dev/null || echo "unknown")
    case "$STATUS" in
        started)
            pass "UCNRR was started successfully"
            ;;
        already_running)
            pass "UCNRR was already running"
            ;;
        failed)
            REASON=$(echo "$ENSURE_RESULT" | jq -r '.reason' 2>/dev/null || echo "unknown")
            fail "UCNRR ensure failed: $REASON"
            if echo "$REASON" | grep -q "ollama"; then
                warn "Hint: Start Ollama with: ollama serve & && ollama pull phi3:mini"
            fi
            exit 1
            ;;
        *)
            warn "Unknown ensure status: $STATUS"
            ;;
    esac
else
    fail "UCNRR ensure endpoint failed"
    exit 1
fi

# Wait a moment for UCNRR to fully start
sleep 2

section "4. Core Health with rr_mode"

info "Checking Core health for rr_mode..."
CORE_HEALTH=$(curl -fsS "$CORE_BASE/health" 2>/dev/null || echo '{}')

if [ -n "$CORE_HEALTH" ] && [ "$CORE_HEALTH" != "{}" ]; then
    pass "Core health endpoint responded"

    RR_MODE=$(echo "$CORE_HEALTH" | jq -r '.rr_mode' 2>/dev/null || echo "unknown")
    case "$RR_MODE" in
        online)
            pass "Core reports rr_mode: online"
            ;;
        degraded)
            warn "Core reports rr_mode: degraded (UCNRR not fully healthy)"
            ;;
        unavailable)
            warn "Core reports rr_mode: unavailable (UCNRR not configured)"
            ;;
        *)
            warn "Unknown rr_mode: $RR_MODE"
            ;;
    esac
else
    fail "Core health endpoint failed"
    exit 1
fi

section "5. Stack Ready with UCNRR Reason Codes"

info "Checking stack ready endpoint..."
READY=$(curl -fsS "$DEVX_BASE/devx/api/stack/ready" 2>/dev/null || echo '{}')

if [ -n "$READY" ] && [ "$READY" != "{}" ]; then
    pass "Stack ready endpoint responded"

    IS_READY=$(echo "$READY" | jq -r '.ready' 2>/dev/null || echo "false")
    STATUS=$(echo "$READY" | jq -r '.status' 2>/dev/null || echo "unknown")

    if [ "$IS_READY" = "true" ]; then
        pass "Stack is ready"
    else
        warn "Stack is not ready (status: $STATUS)"

        FAIL_CONDITIONS=$(echo "$READY" | jq -r '.fail_conditions[]' 2>/dev/null || echo "")
        if [ -n "$FAIL_CONDITIONS" ]; then
            echo "Fail conditions:"
            echo "$FAIL_CONDITIONS" | while read -r condition; do
                echo "  - $condition"
            done
        fi

        RECOVERY=$(echo "$READY" | jq -r '.recovery_suggestions[]?' 2>/dev/null || echo "")
        if [ -n "$RECOVERY" ]; then
            echo "Recovery suggestions:"
            echo "$RECOVERY" | jq -r '. | "  - [\(.service)] \(.action): \(.reason)"' 2>/dev/null || echo "$RECOVERY"
        fi
    fi
else
    fail "Stack ready endpoint failed"
    exit 1
fi

section "6. UCNRR Logs Endpoint"

info "Fetching recent UCNRR logs..."
LOGS=$(curl -fsS "$DEVX_BASE/devx/api/stack/ucnrr/logs?tail=10" 2>/dev/null || echo '{}')

if [ -n "$LOGS" ] && [ "$LOGS" != "{}" ]; then
    pass "UCNRR logs endpoint is working"

    LINE_COUNT=$(echo "$LOGS" | jq -r '.total_lines' 2>/dev/null || echo "0")
    LOG_FILE=$(echo "$LOGS" | jq -r '.log_file' 2>/dev/null || echo "unknown")

    info "Log file: $LOG_FILE ($LINE_COUNT lines)"
else
    warn "UCNRR logs endpoint failed (may be ok if logs not yet written)"
fi

section "7. Summary"

echo ""
if [ "$IS_READY" = "true" ] && [ "$RR_MODE" = "online" ]; then
    pass "All checks passed! UCNRR connectivity system is operational."
    echo ""
    echo "Next steps:"
    echo "  - View UI: http://localhost:3000/tools/llm-benchmarks"
    echo "  - Check logs: curl -s '$DEVX_BASE/devx/api/stack/ucnrr/logs?tail=50'"
    echo "  - Monitor status: watch -n5 'curl -s $DEVX_BASE/devx/api/stack/ucnrr/status | jq'"
    exit 0
else
    warn "System is operational but not fully ready"
    echo ""
    echo "Current state:"
    echo "  - Stack ready: $IS_READY"
    echo "  - Stack status: $STATUS"
    echo "  - RR mode: $RR_MODE"
    echo ""
    echo "Review recovery suggestions above or check:"
    echo "  - UCNRR status: curl -s $DEVX_BASE/devx/api/stack/ucnrr/status | jq"
    echo "  - Stack ready: curl -s $DEVX_BASE/devx/api/stack/ready | jq"
    exit 0
fi
