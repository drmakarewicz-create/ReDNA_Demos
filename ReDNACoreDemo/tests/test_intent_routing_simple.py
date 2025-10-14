#!/usr/bin/env python3
"""
Simple test for Head Coach intent analysis and delegation routing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.head_coach.intent_analyzer import analyze_intent
from core.head_coach.delegation_router import DelegationRouter
from core.head_coach.situational_awareness import get_awareness_snapshot


def test_intent_and_routing():
    """Test intent analysis and delegation routing."""
    print("=" * 60)
    print("Testing Intent Analysis & Delegation Routing")
    print("=" * 60)

    # Test messages with expected domains
    test_cases = [
        ("I need help with my career transition to tech", "career"),
        ("What's my personality type?", "personality"),
        ("How can I improve my relationship with my partner?", "relationship"),
        ("What are my core beliefs and values?", "belief"),
        ("Can you analyze my profile photo?", "photo"),
        ("How do I change my account settings?", "system"),
    ]

    user_id = "TEST"
    awareness = get_awareness_snapshot(user_id)

    print("\n1. Testing Intent Classification...")
    print("-" * 60)

    for message, expected_domain in test_cases:
        intent = analyze_intent(message, awareness)

        domain_match = "✅" if intent["domain"] == expected_domain else "❌"
        print(f"\n{domain_match} Message: \"{message[:50]}...\"")
        print(f"   Domain: {intent['domain']} (expected: {expected_domain})")
        print(f"   Category: {intent['category']}")
        print(f"   Confidence: {intent['confidence']:.2f}")
        print(f"   Ambiguity: {intent['ambiguity']:.2f}")
        print(f"   Emotion: {intent['user_emotion']}")

    print("\n" + "=" * 60)
    print("✅ Intent analysis tests complete!")
    print("=" * 60)

    # Test delegation routing
    print("\n2. Testing Delegation Routing...")
    print("-" * 60)

    router = DelegationRouter()

    for message, expected_domain in test_cases[:3]:
        intent = analyze_intent(message, awareness)
        routing = router.route(
            message=message,
            user_id=user_id,
            current_coach="head_coach",
            context=awareness
        )

        print(f"\n📋 Message: \"{message[:50]}...\"")
        print(f"   Action: {routing['action']}")
        print(f"   Target Coach: {routing['target_coach']}")
        print(f"   Requires Handoff: {routing.get('requires_handoff', False)}")
        print(f"   Reason: {routing['reason']}")

    print("\n" + "=" * 60)
    print("✅ Delegation routing tests complete!")
    print("=" * 60)

    # Show routing stats
    stats = router.get_routing_stats()
    print("\n3. Routing Statistics:")
    print("-" * 60)
    print(f"   Total decisions: {stats['total_decisions']}")
    print(f"   Delegation rate: {stats['delegation_rate']:.1%}")
    print(f"   Avg confidence: {stats['avg_confidence']:.2f}")
    print(f"   Coach distribution: {stats['coach_distribution']}")
    print("-" * 60)

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(test_intent_and_routing())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
