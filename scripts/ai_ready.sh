#!/bin/bash
#
# AI Readiness CLI Wrapper
#
# Usage:
#   ./scripts/ai_ready.sh                    # Summary probe (all layers)
#   ./scripts/ai_ready.sh status             # Quick status check
#   ./scripts/ai_ready.sh devx               # Diagnose DevX layer
#   ./scripts/ai_ready.sh ucnrr              # Diagnose UCNRR layer
#   ./scripts/ai_ready.sh core               # Diagnose Core layer
#   ./scripts/ai_ready.sh e2e                # Diagnose E2E layer
#   ./scripts/ai_ready.sh e2e --no-write     # E2E diagnostic without writes
#   ./scripts/ai_ready.sh ucnrr --minimal    # Minimal output (no verbose)
#   ./scripts/ai_ready.sh --help             # Show help
#

set -e

# Configuration
DEVX_BASE="${DEVX_BASE:-http://127.0.0.1:8012}"
ENDPOINT="${DEVX_BASE}/devx/api/ingestion/ai_ready"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
show_help() {
    cat <<EOF
AI Readiness CLI Wrapper

USAGE:
    ./scripts/ai_ready.sh [COMMAND] [OPTIONS]

COMMANDS:
    (none)          Run summary probe for all layers
    status          Show quick status (ALL-GOOD or NEEDS-FIX)
    devx            Diagnose DevX backend layer
    ucnrr           Diagnose UCNRR processing layer
    core            Diagnose Core processing layer
    e2e             Diagnose end-to-end test layer
    help            Show this help message

OPTIONS:
    --minimal       Skip verbose diagnostic data
    --no-write      Skip E2E writes (for e2e command only)
    --json          Output raw JSON (no formatting)

EXAMPLES:
    # Quick status check
    ./scripts/ai_ready.sh status

    # Full summary probe
    ./scripts/ai_ready.sh

    # Diagnose UCNRR with verbose data
    ./scripts/ai_ready.sh ucnrr

    # E2E test without database writes
    ./scripts/ai_ready.sh e2e --no-write

    # Get raw JSON for scripting
    ./scripts/ai_ready.sh ucnrr --json

ENVIRONMENT:
    DEVX_BASE       DevX backend URL (default: http://127.0.0.1:8012)

EOF
}

check_jq() {
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}Warning: jq not found. Install with: brew install jq${NC}" >&2
        echo -e "${YELLOW}Falling back to raw JSON output${NC}" >&2
        return 1
    fi
    return 0
}

fetch_probe() {
    local url="$1"
    if ! curl -s -f "$url" 2>/dev/null; then
        echo -e "${RED}Error: Failed to connect to ${url}${NC}" >&2
        echo -e "${YELLOW}Is DevX backend running? Try: ./scripts/dev_up.sh${NC}" >&2
        exit 1
    fi
}

format_traffic_light() {
    local status="$1"
    if [ "$status" = "green" ]; then
        echo -e "${GREEN}●${NC} GREEN"
    else
        echo -e "${RED}●${NC} RED"
    fi
}

# Parse arguments
COMMAND="${1:-summary}"
VERBOSE=1
NO_WRITE=0
JSON_OUTPUT=0

shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --minimal)
            VERBOSE=0
            shift
            ;;
        --no-write)
            NO_WRITE=1
            shift
            ;;
        --json)
            JSON_OUTPUT=1
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            show_help
            exit 1
            ;;
    esac
done

# Execute command
case "$COMMAND" in
    help|--help|-h)
        show_help
        exit 0
        ;;

    status)
        # Quick status check
        RESULT=$(fetch_probe "$ENDPOINT" | jq -r '.result' 2>/dev/null || echo "ERROR")
        if [ "$RESULT" = "ALL-GOOD" ]; then
            echo -e "${GREEN}✓ ALL-GOOD${NC} — All systems operational"
            exit 0
        elif [ "$RESULT" = "NEEDS-FIX" ]; then
            echo -e "${RED}✗ NEEDS-FIX${NC} — System degraded"

            # Show which layer is red
            if check_jq; then
                DATA=$(fetch_probe "$ENDPOINT")
                echo ""
                echo "Layer Status:"
                echo -e "  HC/DevX: $(format_traffic_light "$(echo "$DATA" | jq -r '.hc_devx.status')")"
                echo -e "  UCNRR:   $(format_traffic_light "$(echo "$DATA" | jq -r '.ucnrr.status')")"
                echo -e "  Core:    $(format_traffic_light "$(echo "$DATA" | jq -r '.core.status')")"

                # Show first red reason
                REASON=$(echo "$DATA" | jq -r '
                    if .hc_devx.status == "red" then "HC/DevX: " + (.hc_devx.reason // "Unknown")
                    elif .ucnrr.status == "red" then "UCNRR: " + (.ucnrr.reason // "Unknown")
                    elif .core.status == "red" then "Core: " + (.core.reason // "Unknown")
                    else "Unknown issue"
                    end
                ')
                echo ""
                echo -e "${YELLOW}Issue: ${REASON}${NC}"
            fi
            exit 1
        else
            echo -e "${RED}ERROR: Could not determine status${NC}" >&2
            exit 1
        fi
        ;;

    summary)
        # Full summary probe
        DATA=$(fetch_probe "$ENDPOINT")

        if [ "$JSON_OUTPUT" -eq 1 ]; then
            echo "$DATA"
            exit 0
        fi

        if check_jq; then
            RESULT=$(echo "$DATA" | jq -r '.result')
            DURATION=$(echo "$DATA" | jq -r '.probe_duration_ms')

            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${BLUE}  AI Readiness Probe Summary${NC}"
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""

            if [ "$RESULT" = "ALL-GOOD" ]; then
                echo -e "  Overall: ${GREEN}✓ ALL-GOOD${NC}"
            else
                echo -e "  Overall: ${RED}✗ NEEDS-FIX${NC}"
            fi

            echo -e "  Duration: ${DURATION}ms"
            echo ""
            echo "Layer Status:"
            echo -e "  HC/DevX: $(format_traffic_light "$(echo "$DATA" | jq -r '.hc_devx.status')")"
            echo -e "  UCNRR:   $(format_traffic_light "$(echo "$DATA" | jq -r '.ucnrr.status')")"
            echo -e "  Core:    $(format_traffic_light "$(echo "$DATA" | jq -r '.core.status')")"

            # Show E2E if present
            E2E_STATUS=$(echo "$DATA" | jq -r '.core.details.e2e.status // "none"')
            if [ "$E2E_STATUS" != "none" ]; then
                echo -e "  E2E:     $(format_traffic_light "$E2E_STATUS")"
            fi

            echo ""
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

            # Show remediation for first red layer
            if [ "$RESULT" != "ALL-GOOD" ]; then
                echo ""
                echo -e "${YELLOW}Run layer diagnostics for remediation steps:${NC}"
                if [ "$(echo "$DATA" | jq -r '.hc_devx.status')" = "red" ]; then
                    echo "  ./scripts/ai_ready.sh devx"
                fi
                if [ "$(echo "$DATA" | jq -r '.ucnrr.status')" = "red" ]; then
                    echo "  ./scripts/ai_ready.sh ucnrr"
                fi
                if [ "$(echo "$DATA" | jq -r '.core.status')" = "red" ]; then
                    echo "  ./scripts/ai_ready.sh core"
                fi
            fi
        else
            echo "$DATA"
        fi
        ;;

    devx|ucnrr|core)
        # Layer-specific diagnostic
        LAYER="$COMMAND"
        URL="${ENDPOINT}?layer=${LAYER}&verbose=${VERBOSE}"
        DATA=$(fetch_probe "$URL")

        if [ "$JSON_OUTPUT" -eq 1 ]; then
            echo "$DATA"
            exit 0
        fi

        if check_jq; then
            STATUS=$(echo "$DATA" | jq -r '.status')
            REASON=$(echo "$DATA" | jq -r '.reason // "None"')

            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${BLUE}  ${LAYER^^} Layer Diagnostic${NC}"
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "  Status: $(format_traffic_light "$STATUS")"

            if [ "$REASON" != "None" ] && [ "$REASON" != "null" ]; then
                echo -e "  Reason: ${REASON}"
            fi

            echo ""
            echo "Details:"
            echo "$DATA" | jq -r '.details | to_entries[] | "  \(.key): \(.value)"'

            # Show suggestions if red
            SUGGESTIONS=$(echo "$DATA" | jq -r '.suggestions[]?' 2>/dev/null || echo "")
            if [ -n "$SUGGESTIONS" ]; then
                echo ""
                echo -e "${YELLOW}Remediation Steps:${NC}"
                echo "$DATA" | jq -r '.suggestions[] | "  • \(.)"'
            fi

            # Show verbose data if present
            if [ "$VERBOSE" -eq 1 ] && [ "$(echo "$DATA" | jq '.verbose_data | length' 2>/dev/null || echo 0)" -gt 0 ]; then
                echo ""
                echo "Verbose Diagnostic Data:"
                echo "$DATA" | jq -r '.verbose_data | to_entries[] | "  \(.key): \(.value)"'
            fi

            echo ""
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        else
            echo "$DATA"
        fi
        ;;

    e2e)
        # E2E layer diagnostic
        URL="${ENDPOINT}?layer=core_e2e&verbose=${VERBOSE}&no_write=${NO_WRITE}"
        DATA=$(fetch_probe "$URL")

        if [ "$JSON_OUTPUT" -eq 1 ]; then
            echo "$DATA"
            exit 0
        fi

        if check_jq; then
            STATUS=$(echo "$DATA" | jq -r '.status')
            REASON=$(echo "$DATA" | jq -r '.reason // "None"')
            RESCORE_RR=$(echo "$DATA" | jq -r '.details.rescore_rr // "N/A"')

            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${BLUE}  End-to-End Test Diagnostic${NC}"
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "  Status: $(format_traffic_light "$STATUS")"

            if [ "$NO_WRITE" -eq 1 ]; then
                echo -e "  Mode: ${YELLOW}No-Write${NC} (no database writes)"
            fi

            if [ "$REASON" != "None" ] && [ "$REASON" != "null" ]; then
                echo -e "  Reason: ${REASON}"
            fi

            echo ""
            echo "E2E Test Results:"
            echo "  Chronotype RR Score: $RESCORE_RR"

            WHY_EXCERPT=$(echo "$DATA" | jq -r '.details.why_excerpt // "N/A"')
            if [ "$WHY_EXCERPT" != "N/A" ]; then
                echo "  Why-Card Excerpt: ${WHY_EXCERPT:0:80}..."
            fi

            # Show timing if verbose
            if [ "$VERBOSE" -eq 1 ] && [ "$(echo "$DATA" | jq '.verbose_data.ingest_duration_ms' 2>/dev/null || echo 0)" -gt 0 ]; then
                TIMING=$(echo "$DATA" | jq -r '.verbose_data.ingest_duration_ms')
                echo "  Ingest Duration: ${TIMING}ms"
            fi

            # Show suggestions if red
            SUGGESTIONS=$(echo "$DATA" | jq -r '.suggestions[]?' 2>/dev/null || echo "")
            if [ -n "$SUGGESTIONS" ]; then
                echo ""
                echo -e "${YELLOW}Remediation Steps:${NC}"
                echo "$DATA" | jq -r '.suggestions[] | "  • \(.)"'
            fi

            echo ""
            echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        else
            echo "$DATA"
        fi
        ;;

    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}" >&2
        echo "Run './scripts/ai_ready.sh help' for usage" >&2
        exit 1
        ;;
esac
