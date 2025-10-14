"""
Unit tests for Coach Delegation System
"""
import json
import tempfile
from pathlib import Path

import pytest

from core.coach_delegation import (
    CoachRegistry,
    DelegationManager,
    DelegationResult,
    DelegationStatus
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_registry(temp_data_dir):
    """Create test coach registry."""
    registry_path = temp_data_dir / "coach_registry.yaml"
    registry_content = """
coaches:
  photo_coach:
    display_name: "Photo Coach"
    id: "photo_coach"
    description: "Analyzes photos"
    primary_namespaces:
      - PaDNA
    capabilities:
      - PaDNA.HairDNA
      - PaDNA.FaceDNA
      - PaDNA.EyeDNA
    delegation_context: "photo analysis"
    natural_domains:
      - "facial features"
    suitable_for_types:
      - trait
      - missing

  relationship_coach:
    display_name: "Relationship Coach"
    id: "relationship_coach"
    description: "Explores relationships"
    primary_namespaces:
      - ReDNA
    capabilities:
      - ReDNA.*
    delegation_context: "relationship dynamics"
    natural_domains:
      - "attachment styles"
    suitable_for_types:
      - trait
      - container
      - missing

  head_coach:
    display_name: "Head Coach"
    id: "head_coach"
    description: "General conversation"
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
  max_concurrent_delegations: 2
  min_items_per_delegation: 1

availability:
  photo_coach: true
  relationship_coach: true
  head_coach: true
"""
    registry_path.write_text(registry_content)
    return CoachRegistry(registry_path)


def test_coach_registry_loading(test_registry):
    """Test coach registry loads correctly."""
    assert test_registry.config is not None
    coaches = test_registry.config.get("coaches", {})
    assert "photo_coach" in coaches
    assert "relationship_coach" in coaches
    assert "head_coach" in coaches


def test_get_coach_for_namespace(test_registry):
    """Test namespace-to-coach mapping."""
    assert test_registry.get_coach_for_namespace("PaDNA") == "photo_coach"
    assert test_registry.get_coach_for_namespace("ReDNA") == "relationship_coach"
    assert test_registry.get_coach_for_namespace("CogDNA") == "head_coach"

    # Unknown namespace should return default coach
    assert test_registry.get_coach_for_namespace("UnknownDNA") == "head_coach"


def test_get_coach_for_path(test_registry):
    """Test path-to-coach mapping."""
    assert test_registry.get_coach_for_path("PaDNA.HairDNA.Color") == "photo_coach"
    assert test_registry.get_coach_for_path("ReDNA.AttachmentStyleDNA") == "relationship_coach"

    # Wildcard match for ReDNA
    assert test_registry.get_coach_for_path("ReDNA.ConflictResolutionDNA") == "relationship_coach"


def test_can_delegate_to(test_registry, temp_data_dir):
    """Test coach availability check."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    assert manager.registry.can_delegate_to("photo_coach", "test_user") is True
    assert manager.registry.can_delegate_to("relationship_coach", "test_user") is True

    # TODO: Add tests for unavailable coaches once implemented


def test_should_delegate_high_tolerance(temp_data_dir, test_registry):
    """Test delegation decision with high user tolerance."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    curiosity_items = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 75, "rr": 25}
    ]

    # High tolerance (0.9) should allow delegation
    assert manager.should_delegate(curiosity_items, user_tolerance=0.9) is True


def test_should_delegate_low_tolerance(temp_data_dir, test_registry):
    """Test delegation decision with low user tolerance."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    curiosity_items = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 75, "rr": 25}
    ]

    # Low tolerance (0.3) should block delegation
    assert manager.should_delegate(curiosity_items, user_tolerance=0.3) is False


def test_should_delegate_low_curiosity(temp_data_dir, test_registry):
    """Test delegation decision with low curiosity items."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    curiosity_items = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 30, "rr": 70}
    ]

    # High tolerance but low curiosity should block delegation
    assert manager.should_delegate(curiosity_items, user_tolerance=0.9) is False


def test_delegate_to_coach_success(temp_data_dir, test_registry):
    """Test successful delegation creation."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    # Create user directory
    user_dir = temp_data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    result = manager.delegate_to_coach(
        coach_id="photo_coach",
        user_id="test_user",
        curiosity_targets=["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
        context={"delegation_reason": "high_curiosity"}
    )

    assert result.success is True
    assert result.coach == "photo_coach"
    assert result.delegation_id != ""
    assert len(result.curiosity_targets) == 2

    # Check delegation record was created
    delegation_file = temp_data_dir / "users" / "test_user" / "delegations" / f"{result.delegation_id}.json"
    assert delegation_file.exists()

    record = json.loads(delegation_file.read_text())
    assert record["coach"] == "photo_coach"
    assert record["status"] == "pending"
    assert len(record["curiosity_targets"]) == 2


def test_check_delegation_status(temp_data_dir, test_registry):
    """Test delegation status check."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    # Create user directory
    user_dir = temp_data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create delegation
    result = manager.delegate_to_coach(
        coach_id="photo_coach",
        user_id="test_user",
        curiosity_targets=["PaDNA.HairDNA.Color"]
    )

    # Check status
    status = manager.check_delegation_status(result.delegation_id, "test_user")

    assert status is not None
    assert status.delegation_id == result.delegation_id
    assert status.coach == "photo_coach"
    assert status.status == "pending"
    assert len(status.traits_collected) == 0


def test_complete_delegation(temp_data_dir, test_registry):
    """Test delegation completion."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    # Create user directory
    user_dir = temp_data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create delegation
    result = manager.delegate_to_coach(
        coach_id="photo_coach",
        user_id="test_user",
        curiosity_targets=["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"]
    )

    # Complete delegation
    success = manager.complete_delegation(
        delegation_id=result.delegation_id,
        user_id="test_user",
        traits_collected=["PaDNA.HairDNA.Color", "PaDNA.EyeDNA.Color"],
        curiosity_before={"PaDNA.HairDNA.Color": 75, "PaDNA.EyeDNA.Color": 68},
        curiosity_after={"PaDNA.HairDNA.Color": 12, "PaDNA.EyeDNA.Color": 15},
        notes="Photo analysis completed"
    )

    assert success is True

    # Check status updated
    status = manager.check_delegation_status(result.delegation_id, "test_user")
    assert status.status == "completed"
    assert len(status.traits_collected) == 2
    assert status.curiosity_satisfied > 0.8  # High satisfaction
    assert status.notes == "Photo analysis completed"


def test_get_active_delegations(temp_data_dir, test_registry):
    """Test getting active delegations."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    # Create user directory
    user_dir = temp_data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Create two delegations
    result1 = manager.delegate_to_coach(
        coach_id="photo_coach",
        user_id="test_user",
        curiosity_targets=["PaDNA.HairDNA.Color"]
    )

    result2 = manager.delegate_to_coach(
        coach_id="relationship_coach",
        user_id="test_user",
        curiosity_targets=["ReDNA.AttachmentStyleDNA"]
    )

    # Get active delegations
    active = manager.get_active_delegations("test_user")
    assert len(active) == 2

    # Complete one delegation
    manager.complete_delegation(
        delegation_id=result1.delegation_id,
        user_id="test_user",
        traits_collected=["PaDNA.HairDNA.Color"],
        curiosity_before={"PaDNA.HairDNA.Color": 75},
        curiosity_after={"PaDNA.HairDNA.Color": 12}
    )

    # Should only have 1 active now
    active = manager.get_active_delegations("test_user")
    assert len(active) == 1
    assert active[0].coach == "relationship_coach"


def test_group_curiosity_by_coach(temp_data_dir, test_registry):
    """Test grouping curiosity items by coach."""
    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = test_registry

    curiosity_items = [
        {"path": "PaDNA.HairDNA.Color", "curiosity": 75, "rr": 25},
        {"path": "PaDNA.EyeDNA.Color", "curiosity": 68, "rr": 32},
        {"path": "ReDNA.AttachmentStyleDNA", "curiosity": 82, "rr": 18},
        {"path": "ReDNA.ConflictResolutionDNA", "curiosity": 70, "rr": 30},
        {"path": "CogDNA.LearningStyleDNA", "curiosity": 65, "rr": 35}
    ]

    by_coach = manager.group_curiosity_by_coach(curiosity_items)

    assert "photo_coach" in by_coach
    assert "relationship_coach" in by_coach
    assert "head_coach" in by_coach

    assert len(by_coach["photo_coach"]) == 2  # 2 PaDNA items
    assert len(by_coach["relationship_coach"]) == 2  # 2 ReDNA items
    assert len(by_coach["head_coach"]) == 1  # 1 CogDNA item


def test_delegation_with_unavailable_coach(temp_data_dir):
    """Test delegation when coach is unavailable."""
    # Create registry with unavailable coach
    registry_path = temp_data_dir / "coach_registry.yaml"
    registry_content = """
coaches:
  photo_coach:
    display_name: "Photo Coach"
    id: "photo_coach"
    primary_namespaces:
      - PaDNA
    capabilities:
      - PaDNA.*
    delegation_context: "photo analysis"

availability:
  photo_coach: false
"""
    registry_path.write_text(registry_content)

    manager = DelegationManager(data_dir=temp_data_dir)
    manager.registry = CoachRegistry(registry_path)

    # Create user directory
    user_dir = temp_data_dir / "users" / "test_user"
    user_dir.mkdir(parents=True, exist_ok=True)

    result = manager.delegate_to_coach(
        coach_id="photo_coach",
        user_id="test_user",
        curiosity_targets=["PaDNA.HairDNA.Color"]
    )

    assert result.success is False
    assert result.error == "coach_unavailable"
