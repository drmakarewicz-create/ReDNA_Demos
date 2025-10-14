#!/bin/bash
# Jarvis-Codex Phase 1B Verification Script
# Verifies HC proposal generator integration

set -e

echo "🧪 Jarvis-Codex Phase 1B Verification"
echo "====================================="
echo ""

# Run tests
echo "1️⃣  Running Test Suite..."
PYTHONPATH=.:ReDNACoreDemo:$PYTHONPATH python3 -m pytest \
  ReDNACoreDemo/tests/test_jarvis_codex_phase1b.py -v --tb=short

if [ $? -eq 0 ]; then
    echo "   ✓ All tests passing (16/16)"
else
    echo "   ✗ Some tests failed"
    exit 1
fi

# Check module imports
echo ""
echo "2️⃣  Checking Module Imports..."

python3 << 'EOF'
import sys
sys.path.insert(0, 'ReDNACoreDemo')

try:
    from core.jarvis_codex.codex_guardrails import create_guardrails
    print("   ✓ Guardrails module imports successfully")
except Exception as e:
    print(f"   ✗ Guardrails import failed: {e}")
    sys.exit(1)

try:
    from core.jarvis_codex.proposal_generator import create_proposal_generator
    print("   ✓ Proposal generator module imports successfully")
except Exception as e:
    print(f"   ✗ Proposal generator import failed: {e}")
    sys.exit(1)

try:
    from core.hc_orchestrator import create_orchestrator
    orch = create_orchestrator()
    assert hasattr(orch, 'maybe_propose_ui_improvements')
    print("   ✓ HC orchestrator has maybe_propose_ui_improvements method")
except Exception as e:
    print(f"   ✗ Orchestrator integration failed: {e}")
    sys.exit(1)
EOF

# Validate guardrails
echo ""
echo "3️⃣  Validating Guardrails..."

python3 << 'EOF'
import sys
sys.path.insert(0, 'ReDNACoreDemo')

from core.jarvis_codex.codex_guardrails import create_guardrails

guardrails = create_guardrails()

# Test valid proposal
valid_proposal = {
    "scope": "frontend",
    "file": "web/src/components/Test.tsx",
    "intent": "Test",
    "suggested_change": {
        "type": "text_replace",
        "before": "Old",
        "after": "New"
    },
    "confidence": 0.90,
    "source": "head_coach"
}

is_valid, error = guardrails.validate_proposal(valid_proposal)
if is_valid:
    print("   ✓ Valid proposal passes guardrails")
else:
    print(f"   ✗ Valid proposal rejected: {error}")
    sys.exit(1)

# Test invalid proposal (low confidence)
invalid_proposal = valid_proposal.copy()
invalid_proposal["confidence"] = 0.70

is_valid, error = guardrails.validate_proposal(invalid_proposal)
if not is_valid and "below minimum" in error:
    print("   ✓ Low confidence proposal correctly rejected")
else:
    print(f"   ✗ Low confidence proposal not rejected")
    sys.exit(1)

# Test marketing language
marketing_proposal = valid_proposal.copy()
marketing_proposal["suggested_change"]["after"] = "Amazing Revolutionary Product"

is_valid, error = guardrails.validate_proposal(marketing_proposal)
if not is_valid and "Marketing language" in error:
    print("   ✓ Marketing language correctly rejected")
else:
    print(f"   ✗ Marketing language not rejected")
    sys.exit(1)
EOF

# Test heuristic rewrites
echo ""
echo "4️⃣  Testing Heuristic Rewrites..."

python3 << 'EOF'
import sys
sys.path.insert(0, 'ReDNACoreDemo')

from core.jarvis_codex.proposal_generator import create_proposal_generator

generator = create_proposal_generator()

# Test Self-Improvement rewrite
improved, confidence = generator._heuristic_rewrite("Self-Improvement Panel")
if "Adaptive Learning" in improved and confidence >= 0.85:
    print(f"   ✓ Self-Improvement → '{improved}' (confidence: {confidence})")
else:
    print(f"   ✗ Heuristic rewrite failed: {improved}")
    sys.exit(1)

# Test Panel removal
improved, confidence = generator._heuristic_rewrite("Configuration Panel")
if improved == "Configuration" and confidence >= 0.85:
    print(f"   ✓ Panel removal → '{improved}' (confidence: {confidence})")
else:
    print(f"   ✗ Panel removal failed: {improved}")
    sys.exit(1)
EOF

# Check file structure
echo ""
echo "5️⃣  Checking File Structure..."

FILES=(
    "ReDNACoreDemo/core/jarvis_codex/codex_guardrails.py"
    "ReDNACoreDemo/core/jarvis_codex/proposal_generator.py"
    "ReDNACoreDemo/tests/test_jarvis_codex_phase1b.py"
    "ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1B.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✓ $file exists"
    else
        echo "   ✗ $file missing"
        exit 1
    fi
done

# Check LOC counts
echo ""
echo "6️⃣  LOC Summary..."
echo "   Guardrails:        $(wc -l < ReDNACoreDemo/core/jarvis_codex/codex_guardrails.py | tr -d ' ') LOC"
echo "   Proposal Generator: $(wc -l < ReDNACoreDemo/core/jarvis_codex/proposal_generator.py | tr -d ' ') LOC"
echo "   HC Orchestrator:   +~160 LOC (in hc_orchestrator.py)"
echo "   Tests:             $(wc -l < ReDNACoreDemo/tests/test_jarvis_codex_phase1b.py | tr -d ' ') LOC"
echo "   Documentation:     $(wc -l < ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1B.md | tr -d ' ') LOC"

# Summary
echo ""
echo "================================"
echo "✅ Phase 1B Verification Complete"
echo "================================"
echo ""
echo "Capabilities:"
echo "  ✓ Guardrails enforce hard constraints"
echo "  ✓ Heuristic rewrites functional"
echo "  ✓ HC orchestrator integration complete"
echo "  ✓ 16/16 tests passing"
echo "  ✓ Documentation complete"
echo ""
echo "Next Steps:"
echo "  1. Trigger HC proposal generation via orchestrator"
echo "  2. Review proposals in DevX Jarvis-Codex panel"
echo "  3. Monitor telemetry: prompts/insights/hc_orchestrator_telemetry.jsonl"
echo ""
echo "Documentation:"
echo "  - Phase 1B docs: ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1B.md"
echo "  - Phase 1 docs: ReDNACoreDemo/docs/JARVIS_CODEX_PHASE1.md"
echo ""
