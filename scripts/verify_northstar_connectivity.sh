#!/bin/bash
# Verify Northstar can reach all backend services

set -e

echo "=== Northstar Backend Connectivity Verification ==="
echo

# Check Core
echo "1. Core API (8004):"
CORE_STATUS=$(curl -s http://127.0.0.1:8004/health | jq -r '.status // "unreachable"')
if [ "$CORE_STATUS" = "healthy" ]; then
    echo "   ✅ Core is healthy"
else
    echo "   ❌ Core is $CORE_STATUS"
    exit 1
fi

# Check UCNRR
echo "2. UCNRR API (8017):"
UCNRR_STATUS=$(curl -s http://127.0.0.1:8017/health | jq -r '.status // "unreachable"')
if [ "$UCNRR_STATUS" = "healthy" ]; then
    echo "   ✅ UCNRR is healthy"
else
    echo "   ❌ UCNRR is $UCNRR_STATUS"
    exit 1
fi

# Check DevX
echo "3. DevX API (8100):"
DEVX_STATUS=$(curl -s http://127.0.0.1:8100/health | jq -r '.status // "unreachable"')
if [ "$DEVX_STATUS" = "healthy" ]; then
    echo "   ✅ DevX is healthy"
else
    echo "   ❌ DevX is $DEVX_STATUS"
    exit 1
fi

# Check Next.js
echo "4. Next.js (3000):"
if curl -s http://127.0.0.1:3000 | head -1 | grep -q "DOCTYPE html"; then
    echo "   ✅ Next.js is serving"
else
    echo "   ❌ Next.js is not responding"
    exit 1
fi

# Check Core endpoint that Northstar uses
echo "5. Core /ui/asks/list endpoint:"
ASKS_RESULT=$(curl -s "http://127.0.0.1:8004/ui/asks/list?user_id=TEST&limit=1")
if echo "$ASKS_RESULT" | jq -e '.items' > /dev/null 2>&1; then
    echo "   ✅ Asks endpoint responding"
else
    echo "   ❌ Asks endpoint failed: $ASKS_RESULT"
    exit 1
fi

# Check env vars
echo "6. Environment Variables:"
if [ -f "web/.env.local" ]; then
    CORE_BASE=$(grep NEXT_PUBLIC_CORE_API_BASE web/.env.local | cut -d'=' -f2)
    UCNRR_BASE=$(grep NEXT_PUBLIC_UCNRR_API_BASE web/.env.local | cut -d'=' -f2)
    DEVX_BASE=$(grep NEXT_PUBLIC_DEVX_API_BASE web/.env.local | cut -d'=' -f2)

    echo "   NEXT_PUBLIC_CORE_API_BASE=$CORE_BASE"
    echo "   NEXT_PUBLIC_UCNRR_API_BASE=$UCNRR_BASE"
    echo "   NEXT_PUBLIC_DEVX_API_BASE=$DEVX_BASE"

    if [ "$CORE_BASE" = "http://127.0.0.1:8004" ] && \
       [ "$UCNRR_BASE" = "http://127.0.0.1:8017" ] && \
       [ "$DEVX_BASE" = "http://127.0.0.1:8100" ]; then
        echo "   ✅ Environment variables correct"
    else
        echo "   ❌ Environment variables incorrect"
        exit 1
    fi
else
    echo "   ❌ web/.env.local not found"
    exit 1
fi

echo
echo "=== All checks passed! Northstar should be able to reach backends ==="
echo "Access Northstar at: http://127.0.0.1:3000"
echo
