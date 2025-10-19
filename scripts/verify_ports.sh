#!/bin/bash
# Port Configuration Verification Script
# Checks consistency across .env, .cpplusplus_env.json, and running services
# Usage: ./scripts/verify_ports.sh

set -e

echo "========================================"
echo "  ReDNA Port Configuration Verification"
echo "========================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Track issues
ISSUES=0

echo ""
echo "1. Checking .env file ports..."
echo "----------------------------------------"
if [ -f .env ]; then
    CORE_PORT_ENV=$(grep "^CORE_PORT=" .env | cut -d'=' -f2)
    REACT_PORT_ENV=$(grep "^REACT_PORT=" .env | cut -d'=' -f2)
    UCNRR_PORT_ENV=$(grep "^UCNRR_PORT=" .env | cut -d'=' -f2)

    echo "  CORE_PORT  = ${CORE_PORT_ENV:-not set}"
    echo "  REACT_PORT = ${REACT_PORT_ENV:-not set}"
    echo "  UCNRR_PORT = ${UCNRR_PORT_ENV:-not set}"

    # Check if they match canonical values
    if [ "$CORE_PORT_ENV" != "8004" ]; then
        echo -e "  ${YELLOW}⚠️  CORE_PORT should be 8004${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$REACT_PORT_ENV" != "3000" ]; then
        echo -e "  ${YELLOW}⚠️  REACT_PORT should be 3000${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$UCNRR_PORT_ENV" != "8017" ]; then
        echo -e "  ${YELLOW}⚠️  UCNRR_PORT should be 8017${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "  ${RED}❌ .env file not found${NC}"
    ISSUES=$((ISSUES + 1))
fi

echo ""
echo "2. Checking .cpplusplus_env.json..."
echo "----------------------------------------"
if [ -f .cpplusplus_env.json ]; then
    CORE_PORT_CPP=$(cat .cpplusplus_env.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('core_port', 'not set'))")
    REACT_PORT_CPP=$(cat .cpplusplus_env.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('react_port', 'not set'))")
    UCNRR_PORT_CPP=$(cat .cpplusplus_env.json | python3 -c "import json,sys; print(json.load(sys.stdin).get('ucnrr_port', 'not set'))")

    echo "  core_port  = $CORE_PORT_CPP"
    echo "  react_port = $REACT_PORT_CPP"
    echo "  ucnrr_port = $UCNRR_PORT_CPP"

    # Check if they match canonical values
    if [ "$CORE_PORT_CPP" != "8004" ]; then
        echo -e "  ${YELLOW}⚠️  core_port should be 8004${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$REACT_PORT_CPP" != "3000" ]; then
        echo -e "  ${YELLOW}⚠️  react_port should be 3000${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$UCNRR_PORT_CPP" != "8017" ] && [ "$UCNRR_PORT_CPP" != "not set" ]; then
        echo -e "  ${YELLOW}⚠️  ucnrr_port should be 8017${NC}"
        ISSUES=$((ISSUES + 1))
    fi

    # Check cross-file consistency
    if [ "$CORE_PORT_ENV" != "$CORE_PORT_CPP" ] && [ "$CORE_PORT_CPP" != "not set" ]; then
        echo -e "  ${YELLOW}⚠️  Core port mismatch: .env=$CORE_PORT_ENV, CP++=$CORE_PORT_CPP${NC}"
        ISSUES=$((ISSUES + 1))
    fi
    if [ "$REACT_PORT_ENV" != "$REACT_PORT_CPP" ] && [ "$REACT_PORT_CPP" != "not set" ]; then
        echo -e "  ${YELLOW}⚠️  React port mismatch: .env=$REACT_PORT_ENV, CP++=$REACT_PORT_CPP${NC}"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo "  (File does not exist - will use defaults from .env)"
fi

echo ""
echo "3. Checking running services..."
echo "----------------------------------------"
check_port() {
    local port=$1
    local service=$2
    local pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        local process=$(ps -p $pid -o comm= 2>/dev/null)
        echo -e "  ${GREEN}✅${NC} Port $port ($service): Running (PID $pid - $process)"
    else
        echo -e "  ${RED}❌${NC} Port $port ($service): Not running"
    fi
}

check_port 8004 "Core API"
check_port 8017 "UCNRR"
check_port 3000 "React/Next.js"
check_port 8100 "DevX Backend"
check_port 8501 "CP++ Streamlit"

echo ""
echo "4. Checking health endpoints..."
echo "----------------------------------------"
check_health() {
    local port=$1
    local path=$2
    local service=$3
    local url="http://127.0.0.1:$port$path"

    if curl -sf "$url" -m 2 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅${NC} $service: Healthy ($url)"
    else
        echo -e "  ${RED}❌${NC} $service: Not responding ($url)"
        ISSUES=$((ISSUES + 1))
    fi
}

check_health 8004 "/health" "Core API"
check_health 8017 "/health" "UCNRR"
check_health 3000 "/api/health" "React"
check_health 8100 "/health" "DevX Backend"
check_health 8501 "/_stcore/health" "CP++"

echo ""
echo "5. Checking for stale state files..."
echo "----------------------------------------"
if [ -f .cp_state.json ]; then
    echo "  .cp_state.json exists"
    # Check if PIDs in state file are still alive
    STALE=0
    for pid in $(cat .cp_state.json | python3 -c "import json,sys; data=json.load(sys.stdin); print(' '.join([str(v.get('pid', '')) for v in data.values() if 'pid' in v]))" 2>/dev/null); do
        if [ -n "$pid" ] && ! ps -p $pid > /dev/null 2>&1; then
            echo -e "  ${YELLOW}⚠️  Stale PID found: $pid (process no longer running)${NC}"
            STALE=$((STALE + 1))
        fi
    done

    if [ $STALE -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  Found $STALE stale PID(s) - consider deleting .cp_state.json${NC}"
        ISSUES=$((ISSUES + 1))
    else
        echo -e "  ${GREEN}✅${NC} All PIDs in state file are valid"
    fi
else
    echo "  .cp_state.json does not exist (clean state)"
fi

echo ""
echo "========================================"
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ All port configurations are correct!${NC}"
    echo "========================================"
    exit 0
else
    echo -e "${YELLOW}⚠️  Found $ISSUES issue(s)${NC}"
    echo "========================================"
    echo ""
    echo "Recommended fixes:"
    echo "1. Update .env and .cpplusplus_env.json with correct ports"
    echo "2. Delete .cp_state.json if it has stale PIDs"
    echo "3. Restart services via CP++ Nuclear button"
    echo "4. See docs/Port_Configuration_Guide.md for details"
    exit 1
fi
