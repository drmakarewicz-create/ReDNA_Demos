#!/bin/bash
# Validate DevX installation
# Checks that all required files and configurations are in place

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEVX_ROOT="$PROJECT_ROOT/ReDNACoreDemo/devx"

echo "🔍 Validating DevX Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ERRORS=0

# Check backend files
echo ""
echo "📁 Backend Files:"
for file in \
    "$DEVX_ROOT/backend/__init__.py" \
    "$DEVX_ROOT/backend/api.py" \
    "$DEVX_ROOT/backend/config.py" \
    "$DEVX_ROOT/backend/run_devx.py" \
    "$DEVX_ROOT/backend/routers/__init__.py" \
    "$DEVX_ROOT/backend/routers/traits.py"
do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename $file)"
    else
        echo "   ❌ MISSING: $(basename $file)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check frontend files
echo ""
echo "🎨 Frontend Files:"
for file in \
    "$DEVX_ROOT/frontend/package.json" \
    "$DEVX_ROOT/frontend/vite.config.ts" \
    "$DEVX_ROOT/frontend/tsconfig.json" \
    "$DEVX_ROOT/frontend/index.html" \
    "$DEVX_ROOT/frontend/src/App.tsx" \
    "$DEVX_ROOT/frontend/src/main.tsx" \
    "$DEVX_ROOT/frontend/src/lib/devxApi.ts"
do
    if [ -f "$file" ]; then
        echo "   ✅ $(basename $file)"
    else
        echo "   ❌ MISSING: $(basename $file)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check scripts
echo ""
echo "🔧 Scripts:"
for script in \
    "$PROJECT_ROOT/scripts/start_devx.sh" \
    "$PROJECT_ROOT/scripts/stop_devx.sh"
do
    if [ -f "$script" ] && [ -x "$script" ]; then
        echo "   ✅ $(basename $script) (executable)"
    elif [ -f "$script" ]; then
        echo "   ⚠️  $(basename $script) (not executable)"
        chmod +x "$script"
        echo "      → Made executable"
    else
        echo "   ❌ MISSING: $(basename $script)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check documentation
echo ""
echo "📚 Documentation:"
for doc in \
    "$DEVX_ROOT/README.md" \
    "$PROJECT_ROOT/docs/DEVX_OVERVIEW.md" \
    "$PROJECT_ROOT/docs/DEVX_PORT_SAFETY.md" \
    "$PROJECT_ROOT/DEVX_COMPLETION_SUMMARY.md"
do
    if [ -f "$doc" ]; then
        echo "   ✅ $(basename $doc)"
    else
        echo "   ❌ MISSING: $(basename $doc)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Check Python import
echo ""
echo "🐍 Python Import Test:"
cd "$PROJECT_ROOT"
if PYTHONPATH="$PROJECT_ROOT/ReDNACoreDemo:$PYTHONPATH" python3 -c "from devx.backend.config import find_available_port; print('   ✅ Backend imports successful')" 2>/dev/null; then
    true
else
    echo "   ❌ Backend import failed"
    ERRORS=$((ERRORS + 1))
fi

# Check registry file
echo ""
echo "📊 Registry File:"
REGISTRY_PATH="$PROJECT_ROOT/ReDNACoreDemo/core/ontology/dna_registry.json"
if [ -f "$REGISTRY_PATH" ]; then
    CONTAINER_COUNT=$(python3 -c "import json; data=json.load(open('$REGISTRY_PATH')); print(len(data.get('containers', [])))")
    echo "   ✅ Registry found ($CONTAINER_COUNT containers)"
else
    echo "   ❌ MISSING: dna_registry.json"
    ERRORS=$((ERRORS + 1))
fi

# Check port availability
echo ""
echo "🔌 Port Availability:"
if ! lsof -ti:8100 > /dev/null 2>&1; then
    echo "   ✅ Port 8100 available"
else
    echo "   ⚠️  Port 8100 in use (will auto-increment)"
fi

if ! lsof -ti:3100 > /dev/null 2>&1; then
    echo "   ✅ Port 3100 available"
else
    echo "   ⚠️  Port 3100 in use (will auto-increment)"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
    echo "✅ Validation PASSED - DevX is ready to start"
    echo ""
    echo "Next steps:"
    echo "  1. Start DevX: ./scripts/start_devx.sh"
    echo "  2. Open browser: http://127.0.0.1:3100"
    echo "  3. Check API docs: http://127.0.0.1:8100/docs"
    exit 0
else
    echo "❌ Validation FAILED - $ERRORS error(s) found"
    echo ""
    echo "Please fix the errors above before starting DevX"
    exit 1
fi
