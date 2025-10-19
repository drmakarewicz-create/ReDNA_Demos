#!/usr/bin/env python3
"""
Simple test for Head Coach awareness engine with ontology integration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.head_coach.situational_awareness import get_awareness_snapshot, build_awareness_context


def test_awareness_snapshot():
    """Test awareness snapshot building for TEST user."""
    print("=" * 60)
    print("Testing Head Coach Awareness Engine")
    print("=" * 60)

    user_id = "TEST"

    print(f"\n1. Building awareness snapshot for {user_id}...")
    snapshot = get_awareness_snapshot(user_id, force_refresh=True)

    # Verify structure
    assert "user_core_state" in snapshot
    assert "goal_task_layer" in snapshot
    assert "context_layer" in snapshot
    assert "memory_layer" in snapshot
    assert "ttl_hints" in snapshot
    assert "policy" in snapshot
    assert "summary" in snapshot

    print(f"   ✅ Snapshot structure valid")

    # Verify core state
    core = snapshot["user_core_state"]
    assert core["user_id"] == user_id
    assert core["emotional_tone"] in ["positive", "neutral", "negative", "frustrated", "curious"]
    print(f"   ✅ Core state: {core['active_coach']}, tone: {core['emotional_tone']}")

    # Verify memory layer
    memory = snapshot["memory_layer"]
    traits_summary = memory["traits_summary"]
    print(f"   ✅ Overall RR: {traits_summary['overall_rr']:.1f}/100")

    if traits_summary.get("high_rr_domains"):
        print(f"   ✅ High RR domains: {', '.join(traits_summary['high_rr_domains'][:3])}")

    # Verify ontology context
    onto_ctx = memory.get("ontology_context", {})
    if onto_ctx:
        print(f"   ✅ Ontology context found:")
        print(f"      - High RR concepts: {len(onto_ctx.get('high_rr_concepts', []))}")
        print(f"      - Low RR concepts: {len(onto_ctx.get('low_rr_concepts', []))}")
        print(f"      - Related concepts: {len(onto_ctx.get('related_concepts', []))}")
        print(f"      - Coverage score: {onto_ctx.get('coverage_score', 0.0):.2%}")
    else:
        print(f"   ⚠️  No ontology context (may be empty user)")

    # Verify performance
    build_ms = snapshot["policy"]["build_ms"]
    print(f"   ✅ Build time: {build_ms:.2f}ms")

    if build_ms > 100:
        print(f"   ⚠️  WARNING: Build time exceeds 100ms SLA")

    print("\n2. Building awareness context string...")
    context_str = build_awareness_context(user_id)

    assert len(context_str) > 0
    assert "User Context" in context_str
    print(f"   ✅ Context string built ({len(context_str)} chars)")
    print("\n" + "-" * 60)
    print("Preview:")
    print("-" * 60)
    print(context_str[:500] + "..." if len(context_str) > 500 else context_str)
    print("-" * 60)

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_awareness_snapshot())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
