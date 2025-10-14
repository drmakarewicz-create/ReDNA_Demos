#!/bin/bash
# Jarvis-Codex DevX UI Verification Script
# Verifies UI panel integration and API connectivity

set -e

echo "🧪 Jarvis-Codex DevX UI Verification"
echo "===================================="
echo ""

# Check if core API is running
echo "1️⃣  Checking Core API..."
if curl -s http://localhost:8015/health > /dev/null 2>&1; then
    echo "   ✓ Core API running on port 8015"
else
    echo "   ✗ Core API not running. Start with: python3 ReDNACoreDemo/core/api.py"
    exit 1
fi

# Check if DevX frontend is running
echo ""
echo "2️⃣  Checking DevX Frontend..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "   ✓ DevX Frontend running on port 5173"
else
    echo "   ⚠️  DevX Frontend not running. Start with: cd ReDNACoreDemo/devx/frontend && npm run dev"
    echo "   (Optional for API-only verification)"
fi

# Test API endpoints
echo ""
echo "3️⃣  Testing Jarvis-Codex API Endpoints..."

# List proposals
echo "   Testing GET /jarvis_codex/proposals..."
PROPOSALS_RESPONSE=$(curl -s http://localhost:8015/jarvis_codex/proposals?limit=10)
if echo "$PROPOSALS_RESPONSE" | grep -q '"ok":true'; then
    PROPOSAL_COUNT=$(echo "$PROPOSALS_RESPONSE" | grep -o '"proposal_id"' | wc -l)
    echo "   ✓ List proposals working (found $PROPOSAL_COUNT proposals)"
else
    echo "   ✗ List proposals failed"
    echo "   Response: $PROPOSALS_RESPONSE"
    exit 1
fi

# Create test file if it doesn't exist
TEST_FILE="web/src/components/test/JarvisCodexTest.tsx"
mkdir -p "$(dirname "$TEST_FILE")"
if [ ! -f "$TEST_FILE" ]; then
    echo "export default function JarvisCodexTest() { return <div>Old Title</div>; }" > "$TEST_FILE"
    echo "   Created test file: $TEST_FILE"
fi

# Create test proposal
echo ""
echo "4️⃣  Creating Test Proposal..."
PROPOSE_PAYLOAD='{
  "scope": "frontend",
  "file": "web/src/components/test/JarvisCodexTest.tsx",
  "intent": "Verification test proposal",
  "suggested_change": {
    "type": "text_replace",
    "before": "Old Title",
    "after": "New Title"
  },
  "confidence": 0.92,
  "source": "verification_script"
}'

PROPOSE_RESPONSE=$(curl -s -X POST http://localhost:8015/jarvis_codex/propose \
  -H "Content-Type: application/json" \
  -d "$PROPOSE_PAYLOAD")

if echo "$PROPOSE_RESPONSE" | grep -q '"ok":true'; then
    PROPOSAL_ID=$(echo "$PROPOSE_RESPONSE" | grep -o '"proposal_id":"[^"]*"' | cut -d'"' -f4)
    echo "   ✓ Test proposal created: $PROPOSAL_ID"
else
    echo "   ✗ Proposal creation failed"
    echo "   Response: $PROPOSE_RESPONSE"
    exit 1
fi

# Test single proposal GET endpoint
echo ""
echo "5️⃣  Testing GET Single Proposal Endpoint..."
SINGLE_RESPONSE=$(curl -s http://localhost:8015/jarvis_codex/proposals/$PROPOSAL_ID)
if echo "$SINGLE_RESPONSE" | grep -q '"ok":true'; then
    echo "   ✓ Single proposal GET working"
else
    echo "   ✗ Single proposal GET failed"
    echo "   Response: $SINGLE_RESPONSE"
fi

# Test reject endpoint
echo ""
echo "6️⃣  Testing Reject Endpoint..."
REJECT_PAYLOAD="{
  \"proposal_id\": \"$PROPOSAL_ID\",
  \"user\": \"verification_script\",
  \"reason\": \"Test rejection for verification\"
}"

REJECT_RESPONSE=$(curl -s -X POST http://localhost:8015/jarvis_codex/reject \
  -H "Content-Type: application/json" \
  -d "$REJECT_PAYLOAD")

if echo "$REJECT_RESPONSE" | grep -q '"ok":true'; then
    echo "   ✓ Reject endpoint working"
else
    echo "   ✗ Reject endpoint failed"
    echo "   Response: $REJECT_RESPONSE"
fi

# Check audit log
echo ""
echo "7️⃣  Checking Audit Trail..."
AUDIT_FILE="prompts/insights/jarvis_codex_audit.jsonl"
if [ -f "$AUDIT_FILE" ]; then
    RECENT_ENTRY=$(tail -1 "$AUDIT_FILE")
    if echo "$RECENT_ENTRY" | grep -q "rejected"; then
        echo "   ✓ Audit trail updated with rejection"
        echo "   Latest entry: $(echo "$RECENT_ENTRY" | jq -c '{action:.action, proposal_id:.proposal_id, user:.user}')"
    else
        echo "   ⚠️  Audit trail exists but latest entry not as expected"
    fi
else
    echo "   ⚠️  Audit trail file not found: $AUDIT_FILE"
fi

# Frontend file checks
echo ""
echo "8️⃣  Verifying Frontend Files..."

# API Client
if [ -f "ReDNACoreDemo/devx/frontend/src/lib/jarvisCodexApi.ts" ]; then
    echo "   ✓ API client exists: jarvisCodexApi.ts"
else
    echo "   ✗ API client missing: jarvisCodexApi.ts"
    exit 1
fi

# Panel component
if [ -f "ReDNACoreDemo/devx/frontend/src/routes/jarvis-codex/JarvisCodexPanel.tsx" ]; then
    echo "   ✓ Panel component exists: JarvisCodexPanel.tsx"
else
    echo "   ✗ Panel component missing: JarvisCodexPanel.tsx"
    exit 1
fi

# Navigation integration
if grep -q "jarvis-codex" "ReDNACoreDemo/devx/frontend/src/App.tsx"; then
    echo "   ✓ Navigation integrated in App.tsx"
else
    echo "   ✗ Navigation missing in App.tsx"
    exit 1
fi

# Summary
echo ""
echo "================================"
echo "✅ Verification Complete"
echo "================================"
echo ""
echo "Next Steps:"
echo "  1. Open DevX UI: http://localhost:5173/jarvis-codex"
echo "  2. Verify panel renders without errors"
echo "  3. Test approve/reject workflows manually"
echo "  4. Check console for TypeScript errors"
echo ""
echo "Documentation:"
echo "  - Full docs: ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1.md"
echo "  - Completion report: JARVIS_CODEX_UI_COMPLETE.md"
echo ""
