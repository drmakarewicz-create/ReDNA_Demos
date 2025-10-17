"""Example usage of Plan Composer for generating 3-step game plans."""

from core import plan_composer

def example_compose_plan():
    """Generate a new plan for a test user."""
    print("\n=== Plan Composer Example ===\n")

    user_id = "test_user"

    # Compose a new plan
    print("Generating 3-step game plan...")
    plan = plan_composer.compose_plan(user_id)

    print(f"\n📊 Plan ID: {plan.id}")
    print(f"🎯 Focus Area: {plan.focus_area}")
    print(f"📈 Curiosity Score: {plan.curiosity_score:.2f}")
    print(f"🎬 Goal: {plan.goal}")
    print(f"📅 Created: {plan.created_at}")
    print(f"⚡ Status: {plan.status}\n")

    for step in plan.steps:
        print(f"\n{'='*60}")
        print(f"Step {step.number}: {step.action}")
        print(f"{'='*60}")
        print(f"Rationale: {step.rationale}")
        print(f"Effort: {step.effort.upper()} ({step.estimated_minutes} min)")
        print(f"Impact: {step.impact.upper()}")
        if step.coach_delegation:
            print(f"Coach: {step.coach_delegation}")
        print(f"Status: {step.status}")

    print("\n" + "="*60)
    print(f"\n✅ Plan saved to: data/users/{user_id}/plans/\n")

    return plan


def example_plan_history():
    """Load plan history for a user."""
    print("\n=== Plan History Example ===\n")

    user_id = "test_user"

    plans = plan_composer.get_plan_history(user_id, limit=5)

    if not plans:
        print(f"No plans found for user '{user_id}'")
        return

    print(f"Found {len(plans)} plan(s) for user '{user_id}':\n")

    for i, plan in enumerate(plans, 1):
        print(f"{i}. {plan.focus_area}")
        print(f"   Created: {plan.created_at}")
        print(f"   Status: {plan.status}")
        print(f"   Curiosity: {plan.curiosity_score:.2f}")
        print(f"   Steps: {len(plan.steps)}")
        print()


def example_update_step():
    """Mark a step as completed."""
    print("\n=== Update Step Status Example ===\n")

    user_id = "test_user"

    # Get most recent plan
    plans = plan_composer.get_plan_history(user_id, limit=1)
    if not plans:
        print("No plans found. Generate one first.")
        return

    plan = plans[0]
    print(f"Updating step 1 of plan: {plan.id}")

    # Mark step 1 as completed
    updated_plan = plan_composer.update_step_status(
        user_id=user_id,
        plan_id=plan.id,
        step_number=1,
        status="completed",
    )

    if updated_plan:
        step1 = updated_plan.steps[0]
        print(f"✅ Step 1 marked as: {step1.status}")
        print(f"   Action: {step1.action}")

        # Check overall plan status
        print(f"\n📊 Plan Status: {updated_plan.status}")

        all_completed = all(s.status == "completed" for s in updated_plan.steps)
        if all_completed:
            print("🎉 All steps completed! Plan auto-marked as complete.")
    else:
        print("❌ Failed to update step")


def example_with_focus_override():
    """Generate plan with specific focus area."""
    print("\n=== Focus Override Example ===\n")

    user_id = "test_user"
    focus_trait = "PaDNA.RelationshipDNA.Communication"

    print(f"Generating plan for specific focus: {focus_trait}\n")

    plan = plan_composer.compose_plan(
        user_id=user_id,
        focus_override=focus_trait,
    )

    print(f"🎯 Focus: {plan.focus_area}")
    print(f"🎬 Goal: {plan.goal}")
    print(f"\nSteps:")
    for step in plan.steps:
        print(f"  {step.number}. {step.action} ({step.effort} effort, {step.impact} impact)")


if __name__ == "__main__":
    # Run examples
    plan = example_compose_plan()

    # Show history
    example_plan_history()

    # Update step
    example_update_step()

    # Override focus
    example_with_focus_override()

    print("\n✨ Done! Check data/users/test_user/plans/ for saved plans.\n")
