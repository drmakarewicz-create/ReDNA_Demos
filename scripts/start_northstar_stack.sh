#!/bin/bash
# Northstar Stack Startup Script
# Starts all services in the correct order with proper configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Northstar Stack Startup ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are already running
echo "Checking for running services..."
if lsof -i :8004 > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port 8004 (Core) is already in use${NC}"
    echo "Run 'pkill -f uvicorn.*core' to stop existing Core instances"
    exit 1
fi

if lsof -i :8017 > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port 8017 (UCNRR) is already in use${NC}"
    echo "Run 'pkill -f uvicorn.*ucnrr' to stop existing UCNRR instances"
    exit 1
fi

if lsof -i :8100 > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port 8100 (DevX) is already in use${NC}"
    echo "Run 'pkill -f uvicorn.*devx' to stop existing DevX instances"
    exit 1
fi

if lsof -i :3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Port 3000 (Next.js) is already in use${NC}"
    echo "Run 'pkill -f \"next dev\"' to stop existing Next.js instances"
    exit 1
fi

echo -e "${GREEN}All ports are free${NC}"
echo ""

# Activate virtual environment
echo "Activating Python virtual environment..."
source .venv/bin/activate

# Step 1: Start Core API
echo "=== Step 1/4: Starting Core API (port 8004) ==="
nohup uvicorn ReDNACoreDemo.core.api:app \
    --host 127.0.0.1 \
    --port 8004 \
    --log-level info \
    > /tmp/core_api.log 2>&1 &
CORE_PID=$!
echo "Core API started (PID: $CORE_PID)"
echo "Waiting for Core to be healthy..."
sleep 2

# Wait for Core health
for i in {1..30}; do
    if curl -s http://127.0.0.1:8004/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Core API is healthy${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Core API failed to start${NC}"
        echo "Check logs: tail -f /tmp/core_api.log"
        exit 1
    fi
    sleep 1
done
echo ""

# Step 2: Start UCNRR API with LLM configuration
echo "=== Step 2/4: Starting UCNRR API (port 8017) ==="

# Check if Ollama is running
if ! curl -s http://127.0.0.1:11434/api/version > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Ollama doesn't appear to be running${NC}"
    echo "UCNRR may start without LLM configured"
fi

# Ensure UCN_RR_Demo directory exists
if [ ! -d "UCN_RR_Demo" ]; then
    echo -e "${RED}Error: UCN_RR_Demo directory not found${NC}"
    exit 1
fi

# Run uvicorn from project root to ensure module imports work
nohup uvicorn UCN_RR_Demo.ucnrr_app:app \
    --host 127.0.0.1 \
    --port 8017 \
    --log-level info \
    > /tmp/ucnrr_api.log 2>&1 &
UCNRR_PID=$!
echo "UCNRR API started (PID: $UCNRR_PID)"
echo "Waiting for UCNRR to be healthy..."
sleep 2

# Wait for UCNRR health
for i in {1..30}; do
    HEALTH_RESPONSE=$(curl -s http://127.0.0.1:8017/health 2>&1)
    if echo "$HEALTH_RESPONSE" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ UCNRR API is healthy${NC}"

        # Check LLM configuration
        LLM_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.llm_configured // false')
        LLM_PROVIDER=$(echo "$HEALTH_RESPONSE" | jq -r '.llm_provider // "none"')
        LLM_MODEL=$(echo "$HEALTH_RESPONSE" | jq -r '.llm_model // "none"')

        if [ "$LLM_STATUS" = "true" ]; then
            echo -e "${GREEN}✓ UCNRR has LLM configured: $LLM_PROVIDER / $LLM_MODEL${NC}"
        else
            echo -e "${YELLOW}⚠ UCNRR started but LLM not configured${NC}"
            echo "  This is expected if Ollama isn't running"
        fi
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ UCNRR API failed to start${NC}"
        echo "Check logs: tail -f /tmp/ucnrr_api.log"
        exit 1
    fi
    sleep 1
done
echo ""

# Step 3: Start DevX Backend
echo "=== Step 3/4: Starting DevX Backend (port 8100) ==="
export DEVX_CORE_BASE=http://127.0.0.1:8004
export DEVX_UCNRR_BASE=http://127.0.0.1:8017

nohup uvicorn ReDNACoreDemo.devx.backend.api:app \
    --host 127.0.0.1 \
    --port 8100 \
    --log-level info \
    > /tmp/devx_api.log 2>&1 &
DEVX_PID=$!
echo "DevX Backend started (PID: $DEVX_PID)"
echo "Waiting for DevX to be healthy..."
sleep 2

# Wait for DevX health
for i in {1..30}; do
    if curl -s http://127.0.0.1:8100/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ DevX Backend is healthy${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ DevX Backend failed to start${NC}"
        echo "Check logs: tail -f /tmp/devx_api.log"
        exit 1
    fi
    sleep 1
done
echo ""

# Step 4: Start Next.js Frontend
echo "=== Step 4/4: Starting Next.js Frontend (port 3000) ==="

# Ensure .env.local exists in web directory
if [ ! -f "web/.env.local" ]; then
    echo -e "${YELLOW}Warning: web/.env.local not found, creating from template...${NC}"
    cat > web/.env.local << 'EOF'
# Core API endpoint
NEXT_PUBLIC_CORE_API_BASE=http://127.0.0.1:8004

# Core API for server-side API routes
CORE_API_URL=http://127.0.0.1:8004

# UCN/RR API endpoint
NEXT_PUBLIC_UCNRR_API_BASE=http://127.0.0.1:8017

# DevX backend (LLM Benchmarks, AI readiness)
NEXT_PUBLIC_DEVX_API_BASE=http://127.0.0.1:8100

# Provenance Lab (Streamlit, typically port 8501)
NEXT_PUBLIC_PROVENANCE_LAB_URL=http://127.0.0.1:8501/?tab=provenance

# Feature flags
NEXT_PUBLIC_FLAGS=focusedChatLayout

# Life OS (disabled by default until backend ready)
NEXT_PUBLIC_LIFE_ENABLED=false
EOF
fi

cd web
# Clean build cache to avoid stale state
rm -rf .next

nohup npm run dev > /tmp/nextjs.log 2>&1 &
NEXTJS_PID=$!
cd "$PROJECT_ROOT"
echo "Next.js started (PID: $NEXTJS_PID)"
echo "Waiting for Next.js to be ready..."
sleep 3

# Wait for Next.js to be serving
for i in {1..60}; do
    if curl -s --max-time 2 http://127.0.0.1:3000 2>&1 | grep -q "DOCTYPE html"; then
        echo -e "${GREEN}✓ Next.js is serving on port 3000${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}✗ Next.js failed to start${NC}"
        echo "Check logs: tail -f /tmp/nextjs.log"
        exit 1
    fi
    sleep 1
done
echo ""

# Final verification
echo "=== Final Verification ==="
echo "Testing API connectivity..."

# Test Core
CORE_HEALTH=$(curl -s http://127.0.0.1:8004/health | jq -r '.status')
echo "Core API: $CORE_HEALTH"

# Test UCNRR
UCNRR_HEALTH=$(curl -s http://127.0.0.1:8017/health | jq -r '.status')
UCNRR_LLM=$(curl -s http://127.0.0.1:8017/health | jq -r '.llm_configured // "unknown"')
UCNRR_MODEL=$(curl -s http://127.0.0.1:8017/health | jq -r '.llm_model // "none"')
echo "UCNRR API: status=$UCNRR_HEALTH, llm_configured=$UCNRR_LLM, model=$UCNRR_MODEL"

# Test DevX
DEVX_HEALTH=$(curl -s http://127.0.0.1:8100/health | jq -r '.status')
echo "DevX Backend: $DEVX_HEALTH"

# Test Next.js -> Core connectivity
NEXTJS_HEALTH=$(curl -s http://127.0.0.1:3000/api/health | jq -r '.core')
echo "Next.js → Core: $NEXTJS_HEALTH"

echo ""
echo "=== Startup Complete ==="
echo -e "${GREEN}✓ All services are running${NC}"
echo ""
echo "Access Northstar at: http://localhost:3000"
echo ""
echo "Process IDs:"
echo "  Core:    $CORE_PID"
echo "  UCNRR:   $UCNRR_PID"
echo "  DevX:    $DEVX_PID"
echo "  Next.js: $NEXTJS_PID"
echo ""
echo "Logs:"
echo "  Core:    tail -f /tmp/core_api.log"
echo "  UCNRR:   tail -f /tmp/ucnrr_api.log"
echo "  DevX:    tail -f /tmp/devx_api.log"
echo "  Next.js: tail -f /tmp/nextjs.log"
echo ""
echo "To stop all services:"
echo "  pkill -P $CORE_PID && pkill -P $UCNRR_PID && pkill -P $DEVX_PID && pkill -P $NEXTJS_PID"
