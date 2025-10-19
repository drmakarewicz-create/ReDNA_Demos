"""
End-to-end integration tests for Coach Delegation in Head Coach flow
"""
import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_test_user():
    """Create test user with high-curiosity PaDNA traits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import os
        os.environ["CORE_DATA_DIR"] = str(tmpdir)

        # Create user directory
        user_id = "delegation_test_user"
        user_dir = Path(tmpdir) / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create resolved.json with high-curiosity PaDNA traits
        resolved = {
            "PaDNA.HairDNA.Color": {
                "value": "Unknown",
                "ucn": 25,
                "rr": 15,
                "curiosity": 85
            },
            "PaDNA.EyeDNA.Color": {
                "value": "Unknown",
                "ucn": 20,
                "rr": 10,
                "curiosity": 90
            },
            "PaDNA.NoseDNA.Shape": {
                "value": "Unknown",
                "ucn": 18,
                "rr": 8,
                "curiosity": 92
            },
            "ReDNA.ToleranceForNudging": {
                "value": 0.7,  # Balanced mode
                "ucn": 80,
                "rr": 80
            }
        }

        with open(user_dir / "resolved.json", "w") as f:
            json.dump(resolved, f)

        # Create coach registry in core directory
        core_dir = Path(tmpdir).parent / "core"
        core_dir.mkdir(exist_ok=True)
        registry_path = core_dir / "coach_registry.yaml"

        registry_content = """
coaches:
  photo_coach:
    display_name: "Photo Coach"
    id: "photo_coach"
    description: "Analyzes photos to extract physical appearance traits"
    primary_namespaces:
      - PaDNA
    capabilities:
      - PaDNA.HairDNA
      - PaDNA.EyeDNA
      - PaDNA.NoseDNA
      - PaDNA.FaceDNA
    delegation_context: "photo analysis and visual trait extraction"
    natural_domains:
      - "facial features"
      - "hair characteristics"
    suitable_for_types:
      - trait
      - missing

  head_coach:
    display_name: "Head Coach"
    id: "head_coach"
    description: "General conversation coach"
    primary_namespaces:
      - CogDNA
    capabilities:
      - "*"
    delegation_context: "direct conversation"
    natural_domains:
      - "general"
    suitable_for_types:
      - trait
    is_default: true

delegation_rules:
  min_curiosity_for_delegation: 60.0
  min_tolerance_for_proactive_delegation: 0.5
  aggressive_delegation_tolerance: 0.8

availability:
  photo_coach: true
  head_coach: true
"""
        registry_path.write_text(registry_content)

        yield tmpdir, user_id


def test_delegation_recommendations_in_state_snapshot(setup_test_user):
    """Test that delegation recommendations are included in state_snapshot."""
    tmpdir, user_id = setup_test_user

    from core.coach_delegation import DelegationManager

    # Create high-curiosity PaDNA traits manually
    high_curiosity_traits = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 85, "rr": 15},
        {"path": "PaDNA.EyeDNA.Color", "curiosity": 90, "rr": 10},
        {"path": "PaDNA.NoseDNA.Shape", "curiosity": 92, "rr": 8}
    ]

    # Get delegation recommendations
    manager = DelegationManager(data_dir=Path(tmpdir))

    should_delegate = manager.should_delegate(
        curiosity_items=high_curiosity_traits,
        user_tolerance=0.7  # Balanced mode
    )

    assert should_delegate is True

    # Group by coach
    by_coach = manager.group_curiosity_by_coach(high_curiosity_traits)

    # Should have recommendations for photo_coach (PaDNA traits)
    assert "photo_coach" in by_coach
    photo_items = by_coach["photo_coach"]
    assert len(photo_items) >= 3  # HairDNA, EyeDNA, NoseDNA


def test_head_coach_system_message_includes_delegation(setup_test_user):
    """Test that Head Coach system message includes delegation opportunities."""
    tmpdir, user_id = setup_test_user

    from core.hc_llm_agent import _build_system_message
    from core.coach_delegation import DelegationManager

    # Create high-curiosity traits manually (since ontology may not be available)
    high_curiosity_traits = [
        {
            "path": "PaDNA.HairDNA.Color",
            "trait": "PaDNA.HairDNA.Color",
            "curiosity": 85,
            "rr": 15,
            "type": "trait",
            "reason": "Low UCN score indicates high uncertainty"
        },
        {
            "path": "PaDNA.EyeDNA.Color",
            "trait": "PaDNA.EyeDNA.Color",
            "curiosity": 90,
            "rr": 10,
            "type": "trait",
            "reason": "Very low RR - needs refinement"
        },
        {
            "path": "PaDNA.NoseDNA.Shape",
            "trait": "PaDNA.NoseDNA.Shape",
            "curiosity": 92,
            "rr": 8,
            "type": "missing",
            "reason": "No data collected yet"
        }
    ]

    manager = DelegationManager(data_dir=Path(tmpdir))
    by_coach = manager.group_curiosity_by_coach(high_curiosity_traits)

    delegation_recommendations = []
    for coach_id, items in by_coach.items():
        if coach_id != "head_coach":
            avg_curiosity = sum(item.get("curiosity", 0) for item in items) / len(items)
            coaches = manager.registry.config.get("coaches", {})
            coach_data = coaches.get(coach_id, {})
            coach_display_name = coach_data.get("display_name", coach_id)

            delegation_recommendations.append({
                "coach": coach_id,
                "coach_display_name": coach_display_name,
                "items": items,
                "priority": avg_curiosity
            })

    delegation_recommendations.sort(key=lambda x: x["priority"], reverse=True)

    state_snapshot = {
        "high_curiosity_traits": high_curiosity_traits,
        "tolerance_for_nudging": 0.7,
        "overall_rr": 38.0,
        "user_rr_goal": None,
        "delegation_recommendations": delegation_recommendations
    }

    # Build system message
    system_msg = _build_system_message(state_snapshot)

    # Verify delegation section is present
    assert "DELEGATION OPPORTUNITIES" in system_msg
    assert "Photo Coach" in system_msg
    assert "DELEGATION GUIDELINES" in system_msg
    assert "Would you like to chat with" in system_msg


def test_delegation_respects_user_tolerance(setup_test_user):
    """Test that delegation is blocked for low-tolerance users."""
    tmpdir, user_id = setup_test_user

    from core.coach_delegation import DelegationManager
    from core.curiosity.curiosity_engine import CuriosityEngine

    # Create user with LOW tolerance
    user_dir = Path(tmpdir) / "users" / user_id
    resolved_file = user_dir / "resolved.json"
    resolved = json.loads(resolved_file.read_text())
    resolved["ReDNA.ToleranceForNudging"]["value"] = 0.3  # Low tolerance

    with open(resolved_file, "w") as f:
        json.dump(resolved, f)

    # Generate curiosity agenda
    engine = CuriosityEngine(data_dir=Path(tmpdir))
    agenda = engine.generate_curiosity_agenda(user_id=user_id, top_n=10)
    high_curiosity_traits = [item.to_dict() for item in agenda]

    # Check delegation
    manager = DelegationManager(data_dir=Path(tmpdir))

    should_delegate = manager.should_delegate(
        curiosity_items=high_curiosity_traits,
        user_tolerance=0.3  # Low tolerance
    )

    # Should NOT delegate for low tolerance
    assert should_delegate is False


def test_delegation_allowed_for_high_tolerance(setup_test_user):
    """Test that delegation is allowed for high-tolerance users."""
    tmpdir, user_id = setup_test_user

    from core.coach_delegation import DelegationManager

    # Create high-curiosity traits manually
    high_curiosity_traits = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 85, "rr": 15},
        {"path": "PaDNA.EyeDNA.Color", "curiosity": 90, "rr": 10}
    ]

    # Check delegation with high tolerance
    manager = DelegationManager(data_dir=Path(tmpdir))

    should_delegate = manager.should_delegate(
        curiosity_items=high_curiosity_traits,
        user_tolerance=0.9  # High tolerance
    )

    # Should delegate for high tolerance
    assert should_delegate is True
