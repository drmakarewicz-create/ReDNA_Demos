#!/usr/bin/env bash
# Post-Merge QA Harness
#
# Validates the complete resolver/Northstar pipeline:
# 1. Mapper audit (detects unmapped trait_ids)
# 2. Golden fixtures (resolver contract tests)
# 3. Live smoke test (real API call through Northstar path)
#
# Usage:
#   ./scripts/post_merge_qa.sh
#
# Environment variables:
#   QA_ENDPOINT - API endpoint to test (default: http://127.0.0.1:8015/ui/chat/send)
#   QA_USER - Test user ID (default: TEST_QA_USER)
#   QA_MSG - Test message (default: "I have blue eyes")
#   PYTHON - Python interpreter (default: python3)
#   DATA_ROOT - Data directory (default: ROOT/data)

set -euo pipefail

# Determine root directory
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-${ROOT}/data}"
PY="${PYTHON:-python3}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
echo_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

echo_step() {
    echo -e "${BLUE}▶${NC} $*"
}

fail() {
    echo -e "${RED}❌ FAIL:${NC} $*" >&2
    exit 1
}

pass() {
    echo -e "${GREEN}✅ PASS:${NC} $*"
}

warn() {
    echo -e "${YELLOW}⚠️  WARN:${NC} $*"
}

info() {
    echo -e "${BLUE}ℹ️  INFO:${NC} $*"
}

# Start QA
echo_header "🔎 ReDNA Post-Merge QA — $(date -u +%FT%TZ)"
echo "ROOT: ${ROOT}"
echo "DATA_ROOT: ${DATA_ROOT}"
echo "PYTHON: ${PY}"
echo ""

# Track overall status
QA_FAILED=0

# 0) Preflight checks
echo_header "Preflight Checks"

# Check Python
if ! command -v "${PY}" >/dev/null 2>&1; then
    fail "Python interpreter not found: ${PY}"
fi
pass "Python: $(${PY} --version 2>&1)"

# Check curl (optional)
if command -v curl >/dev/null 2>&1; then
    pass "curl: available"
else
    warn "curl not found; live smoke test will be skipped"
fi

# Check Ollama (optional)
if command -v curl >/dev/null 2>&1; then
    if curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        info "Ollama: healthy at port 11434"
    else
        warn "Ollama not responding at port 11434 (continuing)"
    fi
fi

echo ""

# 1) Trait-ID Mapping Audit
echo_header "1/3: Trait-ID Mapping Audit"
echo_step "Scanning all users for unmapped trait_ids..."

AUDIT_CMD="${PY} ${ROOT}/ReDNACoreDemo/core/tools/audit_trait_mapping.py --all ${DATA_ROOT}"
echo "Command: ${AUDIT_CMD}"
echo ""

if ${AUDIT_CMD}; then
    pass "Mapper audit: no unmapped trait_ids found"
else
    fail "Mapper audit failed. Update core/traits/trait_id_map.json with missing mappings."
fi

echo ""

# 2) Golden Fixtures (Resolver)
echo_header "2/3: Golden Fixtures (Resolver)"
echo_step "Running resolver contract tests..."

GOLDEN_GLOB="${ROOT}/ReDNACoreDemo/core/resolver/tests/golden_*.json"

# Check if golden tests exist
if ! compgen -G "${GOLDEN_GLOB}" > /dev/null; then
    fail "No golden fixtures found at: ${GOLDEN_GLOB}"
fi

FIXTURE_CMD="${PY} ${ROOT}/ReDNACoreDemo/core/resolver/run_fixture.py ${GOLDEN_GLOB}"
echo "Command: ${FIXTURE_CMD}"
echo ""

if ${FIXTURE_CMD}; then
    pass "Golden fixtures: all tests passing"
else
    fail "Golden fixtures failed. See output above for details."
fi

echo ""

# 3) Live Smoke Test
echo_header "3/3: Live Smoke Test"

# Skip if curl not available
if ! command -v curl >/dev/null 2>&1; then
    warn "curl not available; skipping live smoke test"
    echo ""
    echo_header "🎉 Post-Merge QA PASSED (smoke test skipped)"
    exit 0
fi

ENDPOINT="${QA_ENDPOINT:-http://127.0.0.1:8015/ui/chat/send}"
USER_ID="${QA_USER:-TEST_QA_USER}"
MSG="${QA_MSG:-I have blue eyes}"

echo_step "Testing live ingestion via: ${ENDPOINT}"
echo "User ID: ${USER_ID}"
echo "Message: ${MSG}"
echo ""

# Build request payload
REQ_PAYLOAD=$(cat <<JSON
{
  "user_id": "${USER_ID}",
  "persona": "head_coach",
  "text": "${MSG}",
  "client_ts": $(date +%s)000
}
JSON
)

# Make API call
echo_step "Sending API request..."
if ! RESP=$(curl -sS -X POST "${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -d "${REQ_PAYLOAD}" 2>&1); then
    fail "API call failed: ${RESP}"
fi

info "Response received"

# Try to extract req_id if present (non-fatal)
REQ_ID=$(echo "${RESP}" | grep -o '"req_id"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)".*/\1/' | head -n1 || true)
if [ -n "${REQ_ID}" ]; then
    info "Trace req_id: ${REQ_ID}"
fi

# Verify resolved.json
echo ""
echo_step "Verifying resolved.json..."

RESOLVED_PATH="${DATA_ROOT}/users/${USER_ID}/resolved.json"
if [ ! -f "${RESOLVED_PATH}" ]; then
    fail "resolved.json not found at: ${RESOLVED_PATH}"
fi

info "Found resolved.json"

# Check for IrisColor trait
if ! grep -q "PaDNA.EyeDNA.IrisColor" "${RESOLVED_PATH}"; then
    fail "PaDNA.EyeDNA.IrisColor not found in resolved.json"
fi

info "Found PaDNA.EyeDNA.IrisColor trait"

# Validate UCN using Python
echo_step "Validating UCN..."

UCN_CHECK=$(${PY} - "${RESOLVED_PATH}" <<'PYCODE'
import json
import sys

resolved_path = sys.argv[1]

try:
    with open(resolved_path, 'r') as f:
        data = json.load(f)

    trait = data.get("PaDNA.EyeDNA.IrisColor", {})
    ucn = float(trait.get("ucn", 0))
    value = trait.get("value", {})
    status = trait.get("status", "unknown")

    print(f"UCN: {ucn}")
    print(f"Value: {value}")
    print(f"Status: {status}")

    # UCN should be >= 0.15 (minimum for fallback prior)
    if ucn < 0.15:
        print(f"ERROR: UCN too low: {ucn} < 0.15", file=sys.stderr)
        sys.exit(1)

    # Value should contain "blue"
    if not (isinstance(value, dict) and value.get("enum") == "blue"):
        print(f"ERROR: Expected value {{'enum': 'blue'}}, got {value}", file=sys.stderr)
        sys.exit(1)

    print("VALIDATION: OK")
    sys.exit(0)

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYCODE
)

UCN_EXIT=$?

echo "${UCN_CHECK}"

if [ ${UCN_EXIT} -ne 0 ]; then
    fail "UCN validation failed"
fi

pass "Live smoke test: IrisColor resolved correctly"

# Check for resolver trace
TRACE_DIR="${DATA_ROOT}/users/${USER_ID}/resolver_traces"
if [ -d "${TRACE_DIR}" ]; then
    TRACE_COUNT=$(find "${TRACE_DIR}" -name "*.json" -type f | wc -l | tr -d ' ')
    info "Resolver traces found: ${TRACE_COUNT}"
else
    warn "Resolver traces directory not found: ${TRACE_DIR}"
fi

echo ""
echo_header "🎉 Post-Merge QA PASSED"
echo ""
echo "Summary:"
echo "  ✅ Mapper audit: clean"
echo "  ✅ Golden fixtures: all passing"
echo "  ✅ Live smoke: IrisColor resolved with valid UCN"
echo ""
echo "Ready for merge!"

exit 0
