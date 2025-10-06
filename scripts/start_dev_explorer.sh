#!/bin/bash
# Start Developer Explorer with proper configuration
# Usage: ./scripts/start_dev_explorer.sh [--port PORT]

set -e

# Default port
PORT=${1:-8502}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛠️  Starting Developer Explorer...${NC}"
echo ""

# Check if we're in repo root
if [ ! -f "ExplorerDev/explorer_dev.py" ]; then
    echo -e "${YELLOW}⚠️  Warning: Run this script from repo root${NC}"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Check if backend is running
echo -e "${BLUE}🔍 Checking backend status...${NC}"
if lsof -i :8001 -t >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend running on port 8001${NC}"
else
    echo -e "${YELLOW}⚠️  Backend not detected on port 8001${NC}"
    echo "   Start with: uvicorn ReDNACoreDemo.core.api:app --port 8001"
    echo ""
fi

# Check for recent test files
TEST_COUNT=$(find . -maxdepth 1 -name "test_*acceptance*.py" | wc -l | tr -d ' ')
echo -e "${BLUE}📋 Found ${TEST_COUNT} acceptance test files${NC}"

# Check for user data
if [ -d "data/users" ]; then
    USER_COUNT=$(find data/users -maxdepth 1 -type d | wc -l | tr -d ' ')
    echo -e "${BLUE}📁 Found $((USER_COUNT - 1)) users in data/users/${NC}"
fi

echo ""
echo -e "${GREEN}🚀 Launching ExplorerDev on port ${PORT}...${NC}"
echo ""
echo -e "${BLUE}📖 Quick Tips:${NC}"
echo "   1. Navigate to 'Developer Tools' in sidebar"
echo "   2. Use Test Runner to run acceptance tests"
echo "   3. Use Log Tails to monitor backend (auto-refresh)"
echo "   4. Use Artifact Browser to inspect user data"
echo "   5. Use HTTP Helpers to test API endpoints"
echo ""
echo -e "${BLUE}📚 Docs:${NC}"
echo "   - User Guide: ExplorerDev/DEV_TOOLS_README.md"
echo "   - Tech Spec: ExplorerDev/IMPLEMENTATION_SUMMARY.md"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Start Streamlit
streamlit run ExplorerDev/explorer_dev.py --server.port="${PORT}" --server.headless=true
