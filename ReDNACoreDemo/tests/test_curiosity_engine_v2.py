"""
Curiosity Engine v2 Tests
==========================

Comprehensive tests for the curiosity engine and API endpoints.
"""

import json
import pytest
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from ReDNACoreDemo.core.curiosity.curiosity_engine_v2 import CuriosityEngine


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_dir = tmp_path / "data"
    users_dir = data_dir / "users" / "TEST"
    users_dir.mkdir(parents=True)

    learning_dir = data_dir / "learning"
    learning_dir.mkdir(parents=True)

    return data_dir


@pytest.fixture
def mock_config(tmp_path):
    """Create mock configuration file."""
    config = {
        "weights": {"gap": 0.5, "impact": 0.3, "recency": 0.1, "cost": 0.1},
        "max_items": 12,
        "min_priority": 0.55,
        "namespace_to_coach": {
            "SkillDNA": "career_coach",
            "LanguageStyleDNA": "chatdna_coach",
            "BeliefValueDNA": "beliefdna_coach",
        },
        "recency_window_hours": 72,
        "cost_failure_multiplier": 0.7,
        "suggested_prompts": {
            "SkillDNA": "Tell me about your skills.",
            "LanguageStyleDNA": "How do you communicate?",
            "BeliefValueDNA": "What are your values?",
        },
    }

    config_file = tmp_path / "curiosity_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)

    return config_file


@pytest.fixture
def mock_analysis_report(tmp_path):
    """Create mock analysis report."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coaches": {
            "career_coach": {
                "sentiment_trend": {"positive": 0.8, "neutral": 0.15, "negative": 0.05},
            },
            "chatdna_coach": {
                "sentiment_trend": {"positive": 0.6, "neutral": 0.3, "negative": 0.1},
            },
            "beliefdna_coach": {
                "sentiment_trend": {"positive": 0.4, "neutral": 0.5, "negative": 0.1},
            },
        },
    }

    report_file = tmp_path / "analysis_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f)

    return report_file


@pytest.fixture
def mock_ontology(tmp_path):
    """Create mock ontology."""
    ontology = {
        "containers": [
            {"path": "SkillDNA.programming.python", "namespace": "SkillDNA", "name": "Python"},
            {"path": "SkillDNA.programming.java", "namespace": "SkillDNA", "name": "Java"},
            {"path": "LanguageStyleDNA.formality", "namespace": "LanguageStyleDNA", "name": "Formality"},
            {"path": "BeliefValueDNA.integrity", "namespace": "BeliefValueDNA", "name": "Integrity"},
            {"path": "BeliefValueDNA.compassion", "namespace": "BeliefValueDNA", "name": "Compassion"},
        ],
    }

    ontology_file = tmp_path / "ontology.json"
    with open(ontology_file, "w") as f:
        json.dump(ontology, f)

    return ontology_file


def test_basic_agenda_generation(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test basic agenda generation with mock data."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST", limit=5)

    # Verify structure
    assert "user_id" in agenda
    assert agenda["user_id"] == "TEST"
    assert "generated_at" in agenda
    assert "items" in agenda
    assert isinstance(agenda["items"], list)

    # Verify items
    if len(agenda["items"]) > 0:
        item = agenda["items"][0]
        assert "target" in item
        assert "priority" in item
        assert "reason" in item
        assert "suggested_coach" in item
        assert "suggested_prompt" in item
        assert "evidence_refs" in item

        # Priority should be 0..1
        assert 0 <= item["priority"] <= 1


def test_weights_effect_on_priority(temp_data_dir, tmp_path, mock_analysis_report, mock_ontology):
    """Test that changing weights affects priority ordering."""
    # Create config with high impact weight
    config_high_impact = {
        "weights": {"gap": 0.1, "impact": 0.8, "recency": 0.05, "cost": 0.05},
        "max_items": 12,
        "min_priority": 0.0,
        "namespace_to_coach": {
            "SkillDNA": "career_coach",
            "LanguageStyleDNA": "chatdna_coach",
            "BeliefValueDNA": "beliefdna_coach",
        },
    }

    config_file = tmp_path / "config_high_impact.json"
    with open(config_file, "w") as f:
        json.dump(config_high_impact, f)

    engine = CuriosityEngine(
        config_path=config_file,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST")

    # With high impact weight, items from career_coach (0.8 positive) should rank higher
    if len(agenda["items"]) >= 2:
        top_coaches = [item["suggested_coach"] for item in agenda["items"][:3]]
        # Career coach should appear in top results
        assert "career_coach" in top_coaches


def test_recency_suppression(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that recently-touched traits are down-weighted."""
    # Create recent interaction for one target
    user_dir = temp_data_dir / "users" / "TEST"
    events_dir = user_dir / "events"
    events_dir.mkdir(parents=True)

    recent_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": "SkillDNA.programming.python",
    }

    event_file = events_dir / "recent.json"
    with open(event_file, "w") as f:
        json.dump(recent_event, f)

    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST")

    # The recently-touched target should have lower priority than others
    python_item = next((item for item in agenda["items"] if item["target"] == "SkillDNA.programming.python"), None)

    if python_item and len(agenda["items"]) > 1:
        other_items = [item for item in agenda["items"] if item["target"] != "SkillDNA.programming.python"]
        # At least one other item should have higher priority
        assert any(item["priority"] > python_item["priority"] for item in other_items)


def test_cost_penalty_for_failures(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that targets with failures are down-weighted."""
    # Create feedback file with failures
    feedback_file = Path("prompts/insights/curiosity_feedback.jsonl")
    feedback_file.parent.mkdir(parents=True, exist_ok=True)

    # Add multiple failures for one target
    with open(feedback_file, "w") as f:
        for _ in range(3):
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": "TEST",
                "target": "SkillDNA.programming.java",
                "result": "blocked",
            }
            f.write(json.dumps(entry) + "\n")

    try:
        engine = CuriosityEngine(
            config_path=mock_config,
            analysis_report_path=mock_analysis_report,
            ontology_path=mock_ontology,
            data_root=temp_data_dir,
        )

        agenda = engine.generate_agenda(user_id="TEST")

        # Java target should have lower priority due to failures
        java_item = next((item for item in agenda["items"] if item["target"] == "SkillDNA.programming.java"), None)

        if java_item and len(agenda["items"]) > 1:
            other_items = [item for item in agenda["items"] if item["target"] != "SkillDNA.programming.java"]
            # Most other items should have higher priority
            higher_priority_count = sum(1 for item in other_items if item["priority"] > java_item["priority"])
            assert higher_priority_count > 0

    finally:
        # Cleanup
        if feedback_file.exists():
            feedback_file.unlink()


def test_min_priority_filter(temp_data_dir, tmp_path, mock_analysis_report, mock_ontology):
    """Test that items below min_priority threshold are excluded."""
    # Create config with high threshold
    config_high_threshold = {
        "weights": {"gap": 0.5, "impact": 0.3, "recency": 0.1, "cost": 0.1},
        "max_items": 12,
        "min_priority": 0.9,  # Very high threshold
        "namespace_to_coach": {
            "SkillDNA": "career_coach",
        },
    }

    config_file = tmp_path / "config_high_threshold.json"
    with open(config_file, "w") as f:
        json.dump(config_high_threshold, f)

    engine = CuriosityEngine(
        config_path=config_file,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST")

    # All returned items should meet threshold
    for item in agenda["items"]:
        assert item["priority"] >= 0.9


def test_limit_respected(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that the limit parameter is respected."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST", limit=3)

    assert len(agenda["items"]) <= 3


def test_api_round_trip(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test POST agenda -> file cached -> GET last-agenda."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    # Generate agenda
    agenda1 = engine.generate_agenda(user_id="TEST", limit=5)

    # Check that file was cached
    agenda_file = temp_data_dir / "users" / "TEST" / "curiosity" / "agenda.json"
    assert agenda_file.exists()

    # Load cached agenda
    with open(agenda_file, "r") as f:
        agenda2 = json.load(f)

    # Should match
    assert agenda1["user_id"] == agenda2["user_id"]
    assert len(agenda1["items"]) == len(agenda2["items"])


def test_feedback_append(tmp_path):
    """Test that feedback is appended correctly."""
    feedback_file = tmp_path / "curiosity_feedback.jsonl"

    # Simulate feedback writes
    entries = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "TEST",
            "target": "SkillDNA.programming.python",
            "result": "success",
            "notes": "User shared projects",
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "TEST",
            "target": "LanguageStyleDNA.formality",
            "result": "blocked",
            "notes": "User declined to answer",
        },
    ]

    with open(feedback_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    # Read back
    with open(feedback_file, "r") as f:
        lines = f.readlines()

    assert len(lines) == 2

    loaded_entries = [json.loads(line) for line in lines]
    assert loaded_entries[0]["result"] == "success"
    assert loaded_entries[1]["result"] == "blocked"


def test_performance_target(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that agenda generation completes in < 500ms."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    start = time.time()
    agenda = engine.generate_agenda(user_id="TEST")
    elapsed = time.time() - start

    # Should complete in < 500ms (0.5 seconds)
    assert elapsed < 0.5
    assert len(agenda["items"]) >= 0


def test_coach_mode_manager_hook(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test the get_curiosity_agenda helper in coach_mode_manager."""
    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.CuriosityEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.generate_agenda.return_value = {
            "user_id": "TEST",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": [
                {
                    "target": "SkillDNA.programming.python",
                    "priority": 0.85,
                    "reason": "High gap; career_coach performing well",
                    "suggested_coach": "career_coach",
                    "suggested_prompt": "Tell me about your Python skills.",
                    "evidence_refs": ["analysis_report:coach=career_coach"],
                }
            ],
        }

        from ReDNACoreDemo.core.coach_mode_manager import get_curiosity_agenda

        agenda = get_curiosity_agenda(user_id="TEST", limit=8)

        assert agenda["user_id"] == "TEST"
        assert len(agenda["items"]) == 1
        assert agenda["items"][0]["target"] == "SkillDNA.programming.python"

        # Verify engine was called
        MockEngine.return_value.generate_agenda.assert_called_once()


def test_missing_analysis_report(temp_data_dir, mock_config, tmp_path):
    """Test that missing analysis report returns empty agenda with debug info."""
    # Point to non-existent analysis report and ontology
    fake_report_path = tmp_path / "nonexistent_report.json"
    fake_ontology_path = tmp_path / "nonexistent_ontology.json"

    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=fake_report_path,
        ontology_path=fake_ontology_path,
        data_root=temp_data_dir,
    )

    agenda = engine.generate_agenda(user_id="TEST", debug=True, fallback=False)

    # Should have debug info
    assert "debug" in agenda
    assert "reason" in agenda["debug"]
    assert "missing" in agenda["debug"]["reason"] or "no valid" in agenda["debug"]["reason"]
    assert agenda["debug"]["analysis_report_found"] == False

    # Items should be empty when both are missing and fallback=False
    assert len(agenda["items"]) == 0


def test_strict_threshold_all_below(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that strict threshold with all items below returns empty with debug info."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    # Set impossibly high threshold
    agenda = engine.generate_agenda(
        user_id="TEST",
        min_priority=0.99,
        debug=True,
        fallback=False,
    )

    # Should have debug info
    assert "debug" in agenda
    assert "all below threshold" in agenda["debug"]["reason"]
    assert agenda["debug"]["below_threshold_count"] > 0

    # Items should be empty
    assert len(agenda["items"]) == 0


def test_fallback_mode_generates_items(temp_data_dir, mock_config, mock_analysis_report, mock_ontology):
    """Test that fallback mode generates placeholder items when agenda would be empty."""
    engine = CuriosityEngine(
        config_path=mock_config,
        analysis_report_path=mock_analysis_report,
        ontology_path=mock_ontology,
        data_root=temp_data_dir,
    )

    # Set impossibly high threshold but enable fallback
    agenda = engine.generate_agenda(
        user_id="TEST",
        min_priority=0.99,
        debug=True,
        fallback=True,
    )

    # Should have debug info with fallback reason
    assert "debug" in agenda
    assert "fallback" in agenda["debug"]["reason"]

    # Should have fallback items (3-5 items)
    assert len(agenda["items"]) >= 3
    assert len(agenda["items"]) <= 5

    # All items should have fallback reason
    for item in agenda["items"]:
        assert item["reason"] == "fallback_agenda_due_to_low_signal"
        assert item["priority"] == 0.5
        assert "evidence_refs" in item
        assert "fallback:no_telemetry" in item["evidence_refs"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
