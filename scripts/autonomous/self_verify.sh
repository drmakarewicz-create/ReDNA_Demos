#!/usr/bin/env bash
set -euo pipefail

# Self-Verification System
# Comprehensive health check that can run autonomously

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🤖 ReDNA Self-Verification System"
echo "=================================="
echo ""

PASSED=0
FAILED=0
WARNINGS=0

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

# 1. Directory Structure
echo "1️⃣  Directory Structure"
echo "---"

if [ -d "ReDNACoreDemo/core" ]; then
    check_pass "Core module exists"
else
    check_fail "Core module missing"
fi

if [ -d "web" ]; then
    check_pass "Web frontend exists"
else
    check_warn "Web frontend missing"
fi

if [ -d "core" ]; then
    check_warn "Stray core/ directory exists (should be removed)"
else
    check_pass "No stray core/ directory"
fi

if [ -d "ReDNACoreDemo/tests" ]; then
    check_pass "Test directory exists"
else
    check_fail "Test directory missing"
fi

echo ""

# 2. Python Environment
echo "2️⃣  Python Environment"
echo "---"

if command -v python3 > /dev/null 2>&1; then
    PY_VERSION=$(python3 --version)
    check_pass "Python 3 available ($PY_VERSION)"
else
    check_fail "Python 3 not found"
fi

if command -v pytest > /dev/null 2>&1 || python3 -m pytest --version > /dev/null 2>&1; then
    check_pass "pytest available"
else
    check_warn "pytest not available"
fi

echo ""

# 3. Critical Imports
echo "3️⃣  Import Validation"
echo "---"

if PYTHONPATH=.:ReDNACoreDemo python3 -c "from ReDNACoreDemo.core import api" 2>/dev/null; then
    check_pass "Core API imports"
else
    check_fail "Core API import failed"
fi

if PYTHONPATH=.:ReDNACoreDemo python3 -c "from ReDNACoreDemo.core.policy import evaluate_capability" 2>/dev/null; then
    check_pass "Policy engine imports"
else
    check_fail "Policy engine import failed"
fi

if PYTHONPATH=.:ReDNACoreDemo python3 -c "from ReDNACoreDemo.core import hc_orchestrator" 2>/dev/null; then
    check_pass "Head Coach orchestrator imports"
else
    check_warn "Head Coach import failed (may need dependencies)"
fi

echo ""

# 4. Syntax Validation
echo "4️⃣  Python Syntax Check"
echo "---"

if [ -f "scripts/autonomous/verify_imports.py" ]; then
    if python3 scripts/autonomous/verify_imports.py > /tmp/import_check.log 2>&1; then
        check_pass "Import verification passed"
    else
        check_warn "Import verification found issues (see /tmp/import_check.log)"
    fi
else
    check_warn "Import verifier not found"
fi

echo ""

# 5. Git Status
echo "5️⃣  Git Repository"
echo "---"

if git status > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current)
    check_pass "Git repository valid (branch: $BRANCH)"

    STATUS_COUNT=$(git status --porcelain | wc -l | tr -d ' ')
    if [ "$STATUS_COUNT" -lt 500 ]; then
        check_pass "Git status count acceptable ($STATUS_COUNT entries)"
    elif [ "$STATUS_COUNT" -lt 1000 ]; then
        check_warn "Git status count moderate ($STATUS_COUNT entries)"
    else
        check_warn "Git status count high ($STATUS_COUNT entries - run hygiene script)"
    fi
else
    check_fail "Not a git repository"
fi

echo ""

# 6. Service Ports
echo "6️⃣  Service Health"
echo "---"

if curl -s -f http://localhost:8015/health > /dev/null 2>&1; then
    check_pass "Core API (8015) responding"
else
    check_warn "Core API (8015) not running"
fi

if curl -s -f http://localhost:8100/health > /dev/null 2>&1; then
    check_pass "DevX Backend (8100) responding"
else
    check_warn "DevX Backend (8100) not running"
fi

if curl -s http://localhost:3100 2>&1 | grep -q "html\|HTML"; then
    check_pass "DevX Frontend (3100) responding"
else
    check_warn "DevX Frontend (3100) not running"
fi

echo ""

# 7. Test Suite
echo "7️⃣  Test Suite Smoke Test"
echo "---"

if PYTHONPATH=.:ReDNACoreDemo python3 -m pytest ReDNACoreDemo/tests/test_policy.py -q --tb=line > /dev/null 2>&1; then
    check_pass "Policy tests pass"
else
    check_fail "Policy tests failing"
fi

echo ""

# 8. Git Hygiene Tools
echo "8️⃣  Git Hygiene Tools"
echo "---"

if [ -f "scripts/git_sanity/scan_status.py" ]; then
    check_pass "Git status scanner present"
else
    check_fail "Git status scanner missing"
fi

if [ -f "scripts/git_sanity/apply_ignore.sh" ]; then
    check_pass "Git ignore applier present"
else
    check_fail "Git ignore applier missing"
fi

if [ -f ".gitignore" ]; then
    if grep -q "git-sanity ignore block" .gitignore; then
        check_pass "Git ignore configured"
    else
        check_warn "Git ignore not configured"
    fi
else
    check_fail ".gitignore missing"
fi

echo ""

# 9. Backup System
echo "9️⃣  Backup System"
echo "---"

if [ -f "scripts/backups/create_backup.sh" ]; then
    check_pass "Backup script present"
else
    check_fail "Backup script missing"
fi

ICLOUD_BACKUP_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups"

if [ -d "$ICLOUD_BACKUP_DIR" ]; then
    BACKUP_COUNT=$(find "$ICLOUD_BACKUP_DIR" -name "*.tar.gz" 2>/dev/null | wc -l | tr -d ' ')

    if [ "$BACKUP_COUNT" -gt 0 ]; then
        check_pass "iCloud backups present ($BACKUP_COUNT backups)"

        # Check age of most recent backup
        LATEST_BACKUP=$(find "$ICLOUD_BACKUP_DIR" -name "*.tar.gz" -type f 2>/dev/null | head -1)
        if [ -n "$LATEST_BACKUP" ]; then
            if [ "$(uname)" = "Darwin" ]; then
                BACKUP_TIME=$(stat -f %m "$LATEST_BACKUP" 2>/dev/null || echo "0")
            else
                BACKUP_TIME=$(stat -c %Y "$LATEST_BACKUP" 2>/dev/null || echo "0")
            fi

            CURRENT_TIME=$(date +%s)
            BACKUP_AGE=$((CURRENT_TIME - BACKUP_TIME))

            if [ "$BACKUP_AGE" -lt 86400 ]; then
                BACKUP_AGE_HOURS=$((BACKUP_AGE / 3600))
                check_pass "Latest backup is fresh (${BACKUP_AGE_HOURS}h ago)"
            else
                BACKUP_AGE_DAYS=$((BACKUP_AGE / 86400))
                check_warn "Latest backup is ${BACKUP_AGE_DAYS} days old"
            fi
        fi
    else
        check_warn "iCloud backup directory empty"
    fi
else
    check_warn "iCloud backup directory not found"
fi

echo ""

# Summary
echo "=================================="
echo "📊 Verification Summary"
echo "=================================="
echo ""
echo -e "${GREEN}Passed:   $PASSED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
echo -e "${RED}Failed:   $FAILED${NC}"
echo ""

if [ "$FAILED" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo "🎉 All checks passed! System is healthy."
    exit 0
elif [ "$FAILED" -eq 0 ]; then
    echo "✅ System functional with minor warnings."
    exit 0
else
    echo "⚠️  Critical issues found. Please review failures above."
    exit 1
fi
