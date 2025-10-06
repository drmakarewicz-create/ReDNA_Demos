#!/usr/bin/env bash
#
# Test suite runner with WRITE_PROTECT safety checks
#
# This script runs all test suites and validates WRITE_PROTECT mode
# before allowing demo presentations.
#
# Usage:
#   ./scripts/run_tests.sh                    # Run all tests
#   ./scripts/run_tests.sh --quick            # Skip slow tests
#   ./scripts/run_tests.sh --write-protect    # Force WRITE_PROTECT=true

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Parse arguments
QUICK_MODE=false
FORCE_WRITE_PROTECT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --write-protect)
            FORCE_WRITE_PROTECT=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Header
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  ${GREEN}${BOLD}ReDNA Test Suite${NC}                                                   ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check WRITE_PROTECT status
check_write_protect() {
    local write_protect="${WRITE_PROTECT:-}"

    echo -e "${BLUE}[INFO]${NC} Checking WRITE_PROTECT status..."

    if [[ "$FORCE_WRITE_PROTECT" == "true" ]]; then
        export WRITE_PROTECT=true
        echo -e "${YELLOW}[WARN]${NC} WRITE_PROTECT forced to: ${GREEN}true${NC}"
        return 0
    fi

    if [[ -z "$write_protect" ]]; then
        echo -e "${YELLOW}[WARN]${NC} WRITE_PROTECT not set (defaulting to false)"
        echo -e "${YELLOW}[WARN]${NC} Tests will modify disk state!"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}[FAIL]${NC} Aborted by user"
            exit 1
        fi
    elif [[ "$write_protect" == "true" ]] || [[ "$write_protect" == "1" ]]; then
        echo -e "${GREEN}[PASS]${NC} WRITE_PROTECT is enabled (safe mode)"
    else
        echo -e "${YELLOW}[WARN]${NC} WRITE_PROTECT is disabled: ${write_protect}"
        echo -e "${YELLOW}[WARN]${NC} Tests will modify disk state!"
    fi
}

# Run a single test
run_test() {
    local test_name="$1"
    local test_command="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Test ${TESTS_RUN}: ${test_name}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"

    if eval "$test_command"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "${GREEN}✓ PASSED${NC}: $test_name"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        echo -e "${RED}✗ FAILED${NC}: $test_name"
        return 1
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${GREEN}${BOLD}Test Summary${NC}                                                      ${BLUE}║${NC}"
    echo -e "${BLUE}╠════════════════════════════════════════════════════════════════════╣${NC}"
    printf "${BLUE}║${NC}  Total tests run:    %-45s ${BLUE}║${NC}\n" "$TESTS_RUN"
    printf "${BLUE}║${NC}  Tests passed:       ${GREEN}%-45s${NC} ${BLUE}║${NC}\n" "$TESTS_PASSED"
    printf "${BLUE}║${NC}  Tests failed:       ${RED}%-45s${NC} ${BLUE}║${NC}\n" "$TESTS_FAILED"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}All tests PASSED ✓${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}${BOLD}Some tests FAILED ✗${NC}"
        echo ""
        return 1
    fi
}

# Change to repo root
cd "$REPO_ROOT"

# Check WRITE_PROTECT
check_write_protect

# Test 1: Nudge store tests
if [[ -f "ExplorerFinal/tests/test_nudge_store.py" ]]; then
    run_test "Nudge Store Unit Tests" \
        "python3 -m pytest ExplorerFinal/tests/test_nudge_store.py -v --tb=short" || true
else
    echo -e "${YELLOW}[SKIP]${NC} Nudge store tests not found"
fi

# Test 2: RR baseline utils tests
if [[ -f "ExplorerDev/tests/test_rr_baseline_utils.py" ]]; then
    run_test "RR Baseline Utils Tests" \
        "python3 -m pytest ExplorerDev/tests/test_rr_baseline_utils.py -v --tb=short" || true
else
    echo -e "${YELLOW}[SKIP]${NC} RR baseline utils tests not found"
fi

# Test 3: CReDNA ops tests
if [[ -f "ExplorerDev/tests/test_credna_ops.py" ]]; then
    run_test "CReDNA Ops Tests" \
        "python3 -m pytest ExplorerDev/tests/test_credna_ops.py -v --tb=short" || true
else
    echo -e "${YELLOW}[SKIP]${NC} CReDNA ops tests not found"
fi

# Test 4: Golden path regression test
if [[ -f "scripts/golden_path_test.py" ]]; then
    run_test "Golden Path Regression Test" \
        "python3 scripts/golden_path_test.py" || true
else
    echo -e "${YELLOW}[SKIP]${NC} Golden path test not found"
fi

# Test 5: Existing Core tests (if not quick mode)
if [[ "$QUICK_MODE" == "false" ]] && [[ -d "ReDNACoreDemo/tests" ]]; then
    run_test "Core Integration Tests" \
        "python3 -m pytest ReDNACoreDemo/tests/ -v --tb=short -x" || true
fi

# Test 6: Existing Explorer tests (if not quick mode)
if [[ "$QUICK_MODE" == "false" ]] && [[ -d "ExplorerFinal/tests" ]]; then
    run_test "Explorer Integration Tests" \
        "python3 -m pytest ExplorerFinal/tests/ -v --tb=short -x" || true
fi

# Print summary and exit
print_summary
exit $?
