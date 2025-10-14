#!/bin/bash
# Smoke test for Head Coach Session Integrity System
# Tests basic functionality without full pytest suite

set -e

echo "🧪 Session Integrity Smoke Test"
echo "================================"
echo ""

export PYTHONPATH="$PWD:$PWD/ReDNACoreDemo:$PYTHONPATH"

echo "✓ Testing SessionManager import..."
python3 -c "from ReDNACoreDemo.core.head_coach.session_manager import SessionManager, SessionState; print('  Import successful')"

echo "✓ Testing session state serialization..."
python3 << 'EOF'
from ReDNACoreDemo.core.head_coach.session_manager import SessionState

state = SessionState(
    active_coach_id="photo_coach",
    context_version=42,
    merged_hash="abc123",
    cancel_token="test-token"
)

data = state.to_dict()
restored = SessionState.from_dict(data)

assert restored.active_coach_id == "photo_coach"
assert restored.context_version == 42
assert restored.merged_hash == "abc123"
print("  Serialization roundtrip successful")
EOF

echo "✓ Testing cancel token validation..."
python3 << 'EOF'
import tempfile
from pathlib import Path
from ReDNACoreDemo.core.head_coach.session_manager import SessionManager

# Create temp dir
with tempfile.TemporaryDirectory() as tmpdir:
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()

    # Create prompts
    prompts_dir = Path(tmpdir) / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "head_coach_ai.md").write_text("# Test Head Coach")

    # Create session manager
    mgr = SessionManager(data_dir)

    # Create user dirs
    user_dir = data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    # Build context
    ctx1 = mgr.build_context("test_user", "head_coach")
    token1 = ctx1["cancel_token"]

    # Validate token
    assert mgr.validate_token("test_user", token1) == True

    # Build new context (invalidates old token)
    ctx2 = mgr.build_context("test_user", "head_coach", force_rebuild=True)
    token2 = ctx2["cancel_token"]

    # Old token should be invalid
    assert mgr.validate_token("test_user", token1) == False
    assert mgr.validate_token("test_user", token2) == True

    print("  Cancel token validation successful")
EOF

echo "✓ Testing context version incrementing..."
python3 << 'EOF'
import tempfile
from pathlib import Path
from ReDNACoreDemo.core.head_coach.session_manager import SessionManager

with tempfile.TemporaryDirectory() as tmpdir:
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()

    prompts_dir = Path(tmpdir) / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "head_coach_ai.md").write_text("# Test HC")

    mgr = SessionManager(data_dir)

    user_dir = data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True)
    (user_dir / "feature_state").mkdir()

    ctx1 = mgr.build_context("test_user", "head_coach")
    ctx2 = mgr.build_context("test_user", "head_coach", force_rebuild=True)
    ctx3 = mgr.build_context("test_user", "head_coach", force_rebuild=True)

    assert ctx1["context_version"] == 1
    assert ctx2["context_version"] == 2
    assert ctx3["context_version"] == 3

    print("  Context versioning successful")
EOF

echo ""
echo "✅ All smoke tests passed!"
echo ""
echo "Next steps:"
echo "  1. Run full pytest suite: pytest ReDNACoreDemo/tests/test_session_integrity.py"
echo "  2. Start services: ./scripts/start_all_services.sh"
echo "  3. Test rapid mode switching in UI"
