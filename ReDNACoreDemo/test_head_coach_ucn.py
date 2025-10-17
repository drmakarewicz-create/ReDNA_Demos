#!/usr/bin/env python3
"""
Test Head Coach UCN/RR Integration
===================================

This script tests the complete flow:
1. Load user observations (with UCN values)
2. UCN/RR engine calculates curiosity signals
3. Bridge converts signals to Core recommendations
4. Head Coach deliberates and makes decisions
5. Action plan is generated

Usage:
    python3 test_head_coach_ucn.py <user_id>

Example:
    python3 test_head_coach_ucn.py abtest
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.head_coach_ucn_bridge import create_ucn_bridge
from core.head_coach_decision import UserContext, AffectState


def test_head_coach_ucn(user_id: str):
    """Test Head Coach UCN/RR integration for a user"""

    print(f"\n{'=' * 70}")
    print(f"Testing Head Coach UCN/RR Integration for: {user_id}")
    print(f"{'=' * 70}\n")

    # Step 1: Load user observations
    print("Step 1: Loading user observations...")
    # Try multiple locations
    possible_paths = [
        project_root / "data" / "users" / user_id / f"{user_id}_observations.json",
        project_root.parent / "data" / "users" / user_id / f"{user_id}_observations.json"
    ]

    obs_file = None
    for path in possible_paths:
        if path.exists():
            obs_file = path
            break

    if obs_file is None:
        print(f"❌ Observations file not found in any of:")
        for path in possible_paths:
            print(f"   - {path}")
        print("Run calculate_ucn_for_user.py first to generate UCN values.")
        return

    with open(obs_file, 'r', encoding='utf-8') as f:
        obs_data = json.load(f)

    observations = obs_data.get('observations', [])
    print(f"✅ Loaded {len(observations)} observations")

    # Step 2: Extract UCN values (simulating what would come from resolved.json)
    print("\nStep 2: Extracting UCN values...")
    user_traits = {}

    for obs in observations:
        path = obs.get('path')
        # Mock UCN based on confidence (in real system, this comes from UCN calculator)
        confidence = obs.get('confidence', 0.5)
        mock_ucn = int(confidence * 1000)  # Convert 0-1 confidence to 0-1000 UCN
        user_traits[path] = mock_ucn

    print(f"✅ Extracted {len(user_traits)} traits with UCN values")
    print(f"   Sample: {list(user_traits.items())[:3]}")

    # Step 3: Create user context (simulating user state)
    print("\nStep 3: Creating user context...")
    affect_state = AffectState(
        stress_level=3,      # Low stress
        emotional_load=4,
        mood="neutral",
        energy_level=7,      # Good energy
        openness_to_change=8, # Very open
        receptivity_score=7
    )

    user_context = UserContext(
        user_id=user_id,
        affect_state=affect_state,
        preferred_name=user_id.capitalize(),
        tone_preference="warm",
        current_goals=["Complete PaDNA profile", "Improve photo quality"],
        proactive_nudges=True,
        explain_suggestions=True
    )

    print(f"✅ User context created")
    print(f"   Readiness: {affect_state.overall_readiness()}/10")
    print(f"   Goals: {user_context.current_goals}")

    # Step 4: Process curiosity signals through Head Coach
    print("\nStep 4: Processing curiosity signals...")
    bridge = create_ucn_bridge()

    try:
        plan = bridge.process_curiosity_signals(
            user_id=user_id,
            user_traits=user_traits,
            user_context=user_context,
            max_actions=10
        )

        print(f"✅ Action plan generated")
        print(f"\n{'─' * 70}")
        print(f"HEAD COACH ACTION PLAN")
        print(f"{'─' * 70}\n")

        # Display greeting
        print(f"💬 {plan.greeting}\n")

        if plan.priority_message:
            print(f"⚡ Priority: {plan.priority_message}\n")

        # Display accepted actions
        print(f"📋 Accepted Actions ({len(plan.accepted_actions)}):\n")
        for i, decision in enumerate(plan.accepted_actions, 1):
            print(f"{i}. [{decision.mode.value.upper()}] {decision.action_description}")
            print(f"   ⏱️  Est. time: {decision.estimated_time_mins} min")
            print(f"   🎯 Benefit: {decision.user_benefit}")
            print(f"   💡 Message: {decision.message_to_user}")
            print(f"   📊 Intervention: {decision.intervention_style.value}")
            print()

        # Display deferred actions
        if plan.deferred_actions:
            print(f"⏸️  Deferred Actions ({len(plan.deferred_actions)}):\n")
            for i, decision in enumerate(plan.deferred_actions[:5], 1):
                print(f"{i}. {decision.action_description}")
                print(f"   Reason: {decision.override_reason}")
                print()

        # Display stats
        print(f"{'─' * 70}")
        print(f"STATS")
        print(f"{'─' * 70}\n")
        print(f"Total Curiosity Signals: {plan.curiosity_signals_count}")
        print(f"Core Recommendations: {plan.core_recommendations_count}")
        print(f"Accepted: {len(plan.accepted_actions)}")
        print(f"Deferred: {len(plan.deferred_actions)}")
        print(f"Acceptance Rate: {plan.acceptance_rate * 100:.1f}%")
        print(f"Dominant Mode: {plan.dominant_mode.value}")
        print()

        # Display decision reasoning
        print(f"{'─' * 70}")
        print(f"DECISION REASONING (Sample)")
        print(f"{'─' * 70}\n")
        for decision in plan.accepted_actions[:3]:
            print(f"✅ {decision.action_description}")
            print(f"   {decision.decision_reasoning}")
            if decision.overridden:
                print(f"   ⚠️  Overridden: {decision.override_reason}")
            print()

    except Exception as e:
        print(f"❌ Error processing curiosity signals: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"{'=' * 70}")
    print(f"✅ Test completed successfully!")
    print(f"{'=' * 70}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_head_coach_ucn.py <user_id>")
        print("\nExample:")
        print("  python3 test_head_coach_ucn.py abtest")
        print("  python3 test_head_coach_ucn.py mrscoachtest")
        sys.exit(1)

    user_id = sys.argv[1]
    test_head_coach_ucn(user_id)


if __name__ == "__main__":
    main()
