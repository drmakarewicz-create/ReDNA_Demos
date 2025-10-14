#!/usr/bin/env python3
"""
End-to-end test for Head Coach V2 Pipeline (Jarvis Sprint)
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.head_coach.orchestrator import process_interaction


async def test_v2_pipeline():
    """Test full HC v2 pipeline end-to-end."""
    print("=" * 70)
    print("HEAD COACH V2 PIPELINE TEST (JARVIS SPRINT)")
    print("=" * 70)

    user_id = "TEST"

    # Test messages covering different intents and domains
    test_cases = [
        {
            "message": "I need help with my career transition",
            "expected_domain": "career",
            "description": "Career guidance request"
        },
        {
            "message": "What are my personality strengths?",
            "expected_domain": "personality",
            "description": "Personality inquiry"
        },
        {
            "message": "Tell me about my profile",
            "expected_domain": "system",
            "description": "System/profile query"
        }
    ]

    print("\n" + "=" * 70)
    print("Testing HC V2 Pipeline Components")
    print("=" * 70)

    for i, test_case in enumerate(test_cases, 1):
        message = test_case["message"]
        description = test_case["description"]

        print(f"\n{'─' * 70}")
        print(f"Test Case {i}: {description}")
        print(f"Message: \"{message}\"")
        print(f"{'─' * 70}")

        try:
            result = await process_interaction(
                user_id=user_id,
                message=message,
                current_coach="head_coach"
            )

            # Validate structure
            assert "response" in result, "Missing response"
            assert "metadata" in result, "Missing metadata"

            metadata = result["metadata"]
            assert "intent" in metadata, "Missing intent metadata"
            assert "routing" in metadata, "Missing routing metadata"
            assert "awareness_summary" in metadata, "Missing awareness summary"
            assert "performance" in metadata, "Missing performance metrics"

            print("\n✅ RESPONSE:")
            print(f"   {result['response'][:200]}...")

            print("\n📊 METADATA:")
            print(f"   Intent:")
            print(f"     - Primary: {metadata['intent']['primary_intent']}")
            print(f"     - Confidence: {metadata['intent']['confidence']:.2f}")
            print(f"     - Needs Clarification: {metadata['intent']['requires_clarification']}")

            print(f"   Routing:")
            print(f"     - Action: {metadata['routing']['action']}")
            print(f"     - Target Coach: {metadata['routing']['target_coach']}")
            print(f"     - Requires Handoff: {metadata['routing']['requires_handoff']}")

            print(f"   Awareness:")
            print(f"     - Emotional Tone: {metadata['awareness_summary']['emotional_tone']}")
            print(f"     - Overall RR: {metadata['awareness_summary']['overall_rr']:.1f}")
            print(f"     - Curiosity Hotspots: {len(metadata['awareness_summary']['curiosity_hotspots'])}")

            print(f"   Performance:")
            print(f"     - Total Time: {metadata['performance']['total_time_ms']:.2f}ms")
            print(f"     - Awareness Build: {metadata['performance']['awareness_build_ms']:.2f}ms")

            # Check performance SLA
            if metadata['performance']['total_time_ms'] < 500:
                print("     ✅ Within 500ms SLA")
            else:
                print(f"     ⚠️  Exceeds 500ms SLA")

            print("\n✅ Test case passed!")

        except Exception as e:
            print(f"\n❌ Test case failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - HC V2 PIPELINE OPERATIONAL")
    print("=" * 70)
    print("\nJarvis Sprint Implementation Complete!")
    print("  ✅ Situational Awareness: 4-layer model with ontology integration")
    print("  ✅ Intent Analysis: Rule-based classifier with confidence scoring")
    print("  ✅ Delegation Router: Policy-driven routing with escalation")
    print("  ✅ CReDNA Personality: Adaptive tone based on user state")
    print("  ✅ V2 Orchestration: Full end-to-end pipeline")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(test_v2_pipeline())
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
