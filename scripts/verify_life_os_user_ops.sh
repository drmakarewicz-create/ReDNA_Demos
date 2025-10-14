#!/usr/bin/env bash
set -euo pipefail

echo "🧪 Life OS → User Ops Integration Verification"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CORE_BASE="http://localhost:8015"
DEVX_BASE="http://localhost:8100"
USER_ID="USER1"

echo "1️⃣  Checking Core Life OS summary endpoint..."
SUMMARY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$CORE_BASE/ui/hc/life/$USER_ID/summary")
if [ "$SUMMARY_STATUS" = "200" ]; then
    echo -e "${GREEN}✓${NC} Core Life OS summary returns 200"
    SUMMARY=$(curl -s "$CORE_BASE/ui/hc/life/$USER_ID/summary")
    echo "   North Star: $(echo "$SUMMARY" | jq -r '.summary.north_star.identity // "not set"')"
    echo "   Today's 3: $(echo "$SUMMARY" | jq -r '.summary.today_three | length') tasks"
    echo "   Goals: $(echo "$SUMMARY" | jq -r '.summary.goals | length') goals"
    echo "   Inbox: $(echo "$SUMMARY" | jq -r '.summary.inbox | length') items"
else
    echo -e "${RED}✗${NC} Core Life OS summary returned $SUMMARY_STATUS (expected 200)"
fi
echo ""

echo "2️⃣  Checking agent configuration for $USER_ID..."
AGENT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DEVX_BASE/devx/api/agents/$USER_ID")
if [ "$AGENT_STATUS" = "200" ]; then
    AGENT=$(curl -s "$DEVX_BASE/devx/api/agents/$USER_ID")
    AGENCY_LEVEL=$(echo "$AGENT" | jq -r '.record.metadata.agency_level // 0')
    echo -e "${GREEN}✓${NC} Agent found with agency level L$AGENCY_LEVEL"

    if [ "$AGENCY_LEVEL" -ge 2 ]; then
        echo -e "   ${GREEN}✓${NC} Life OS will be editable (L2+)"
    else
        echo -e "   ${YELLOW}⚠${NC}  Life OS will be read-only (L0/L1)"
    fi
else
    echo -e "${RED}✗${NC} Agent config returned $AGENT_STATUS"
fi
echo ""

echo "3️⃣  Checking DevX frontend is running..."
DEVX_UI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3100/")
if [ "$DEVX_UI_STATUS" = "200" ]; then
    echo -e "${GREEN}✓${NC} DevX UI is accessible at http://localhost:3100"
    echo -e "   ${GREEN}→${NC} Navigate to: http://localhost:3100/user-ops/$USER_ID/hc"
else
    echo -e "${RED}✗${NC} DevX UI not accessible (status: $DEVX_UI_STATUS)"
fi
echo ""

echo "4️⃣  Testing Quick Capture (capability-gated write)..."
# Get a capability token
TOKEN_RESPONSE=$(curl -s "$DEVX_BASE/devx/api/capabilities/mint" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"scope\": \"core.agent.config\", \"duration_seconds\": 60}")

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.token // empty')

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓${NC} Capability token obtained"

    # Test Quick Capture
    CAPTURE_RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        "$CORE_BASE/ui/hc/life/$USER_ID/capture" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-Capability: $TOKEN" \
        -d '{"text": "Verify Life OS integration", "when": "backlog"}')

    CAPTURE_STATUS=$(echo "$CAPTURE_RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)

    if [ "$CAPTURE_STATUS" = "200" ]; then
        echo -e "${GREEN}✓${NC} Quick Capture succeeded with capability token"
    else
        echo -e "${RED}✗${NC} Quick Capture failed (status: $CAPTURE_STATUS)"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Could not obtain capability token"
fi
echo ""

echo "5️⃣  Feature flag check..."
if grep -q "LIFE_OS_IN_USER_OPS.*true" ReDNACoreDemo/devx/frontend/src/lib/featureFlags.ts 2>/dev/null; then
    echo -e "${GREEN}✓${NC} LIFE_OS_IN_USER_OPS feature flag is enabled"
else
    echo -e "${YELLOW}⚠${NC}  Feature flag file not found or disabled"
fi
echo ""

echo "=============================================="
echo "✅ Verification complete!"
echo ""
echo "📋 Manual testing checklist:"
echo "   1. Open http://localhost:3100/user-ops/$USER_ID/hc"
echo "   2. Verify Life OS section appears below RSC Collaboration"
echo "   3. Check that cards show friendly empty states"
echo "   4. If L0/L1: verify read-only badge and disabled controls"
echo "   5. If L2+: test Quick Capture and checkbox toggles"
echo "   6. Switch agency level and verify editable state changes"
echo ""
