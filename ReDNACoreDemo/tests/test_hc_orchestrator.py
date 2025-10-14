"""
Test HC Orchestrator — Jarvis Functionality Phase 1

Tests autonomous Head Coach orchestration including:
1. Curiosity-driven nudges
2. Learning-influenced behavior context
3. Permission gating for sensitive namespaces
4. Telemetry logging
5. Performance requirements
"""

import json
import pytest
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from ReDNACoreDemo.core.hc_orchestrator import HCOrchestrator, Nudge, create_orchestrator
from ReDNACoreDemo.core import coach_mode_manager


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    # Create learning directory
    learning_dir = data_root / "learning"
    learning_dir.mkdir()

    # Create users directory
    users_dir = data_root / "users"
    users_dir.mkdir()
    test_user_dir = users_dir / "TEST"
    test_user_dir.mkdir()

    return data_root


@pytest.fixture
def mock_config(tmp_path):
    """Create mock orchestrator config."""
    config = {
        "min_nudge_priority": 0.65,
        "idle_seconds": 90,
        "learning_influence": {
            "tone_weight": 0.3,
            "creativity_weight": 0.2
        },
        "respect_consent": True,
        "max_nudges_per_turn": 1,
        "sensitive_namespaces": ["PaDNA", "Photo"]
    }

    config_path = tmp_path / "test_orchestrator_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


@pytest.fixture
def mock_learning_report(temp_data_dir):
    """Create mock learning analysis report."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": 168,
        "coaches": {
            "head_coach": {
                "total_turns": 150,
                "positive_rate": 0.75,
                "avg_latency_ms": 1200,
                "suggestions": []
            },
            "career_coach": {
                "total_turns": 80,
                "positive_rate": 0.82,
                "avg_latency_ms": 900,
                "suggestions": []
            },
            "beliefdna_coach": {
                "total_turns": 60,
                "positive_rate": 0.68,
                "avg_latency_ms": 1500,
                "suggestions": []
            }
        }
    }

    report_path = temp_data_dir / "learning" / "analysis_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f)

    return report_path


@pytest.fixture
def mock_curiosity_agenda():
    """Mock curiosity agenda for testing."""
    return {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "target": "SkillDNA.programming.python_fluency",
                "priority": 0.86,
                "reason": "High impact + low coverage",
                "suggested_coach": "career_coach",
                "suggested_prompt": "Tell me about your recent Python projects and your comfort level with async programming.",
                "evidence_refs": ["gap:SkillDNA.programming"]
            },
            {
                "target": "BeliefValueDNA.work_ethic",
                "priority": 0.72,
                "reason": "Moderate gap, high recency",
                "suggested_coach": "beliefdna_coach",
                "suggested_prompt": "What values guide your approach to work?",
                "evidence_refs": ["gap:BeliefValueDNA"]
            }
        ],
        "total_candidates": 2000,
        "above_threshold": 2
    }


@pytest.fixture
def mock_curiosity_agenda_pa_dna():
    """Mock curiosity agenda with sensitive PaDNA target."""
    return {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "target": "PaDNA.relationship_values",
                "priority": 0.78,
                "reason": "High impact + low coverage",
                "suggested_coach": "padna_coach",
                "suggested_prompt": "Tell me about your relationship values.",
                "evidence_refs": ["gap:PaDNA"]
            }
        ],
        "total_candidates": 2000,
        "above_threshold": 1
    }


# Test 1: What-next query triggers nudge
def test_what_next_triggers_nudge(temp_data_dir, mock_config, mock_learning_report, mock_curiosity_agenda):
    """Test that 'what next?' query triggers nudge with top agenda item."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = mock_curiosity_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what next?",
            idle_flag=False,
            developer_mode=True
        )

        assert nudge is not None
        assert nudge.kind == "curiosity_nudge"
        assert nudge.coach_id == "career_coach"
        assert nudge.priority == 0.86
        assert nudge.target == "SkillDNA.programming.python_fluency"
        assert "Python projects" in nudge.prompt
        assert nudge.requires_consent == False


# Test 2: Idle flag triggers nudge
def test_idle_triggers_nudge(temp_data_dir, mock_config, mock_learning_report, mock_curiosity_agenda):
    """Test that idle flag triggers nudge."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = mock_curiosity_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="",
            idle_flag=True,
            developer_mode=False
        )

        assert nudge is not None
        assert nudge.priority >= 0.65  # Above minimum threshold


# Test 3: PaDNA requires consent
def test_padna_requires_consent(temp_data_dir, mock_config, mock_learning_report, mock_curiosity_agenda_pa_dna):
    """Test that PaDNA targets are flagged as requiring consent."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = mock_curiosity_agenda_pa_dna

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what should we do?",
            idle_flag=False
        )

        assert nudge is not None
        assert nudge.requires_consent == True
        assert nudge.target.startswith("PaDNA")


# Test 4: Learning influences behavior context
def test_learning_influences_tone(temp_data_dir, mock_config, mock_learning_report):
    """Test that learning report influences tone hints in behavior context."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    behavior_context = {}
    enriched_context = orchestrator.on_turn_start(
        user_id="TEST",
        text="Hello",
        meta={"developer_mode": False},
        behavior_context=behavior_context
    )

    # Learning report has avg positive_rate of 0.75 (empathetic range)
    assert "tone_hint" in enriched_context
    assert enriched_context["tone_hint"] in ["empathetic", "balanced", "concise"]
    assert "tone_bias" in enriched_context
    assert "creativity_bias" in enriched_context


# Test 5: No agenda returns None
def test_no_agenda_returns_none(temp_data_dir, mock_config, mock_learning_report):
    """Test that empty curiosity agenda returns no nudge."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    empty_agenda = {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
        "total_candidates": 0,
        "above_threshold": 0
    }

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = empty_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what next?",
            idle_flag=False
        )

        assert nudge is None


# Test 6: Telemetry logged for nudge shown
def test_nudge_telemetry_logged(temp_data_dir, mock_config, mock_learning_report, mock_curiosity_agenda):
    """Test that nudge_shown events are logged to telemetry."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    telemetry_path = temp_data_dir / "learning" / "nudge_telemetry.jsonl"

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = mock_curiosity_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what should we explore?",
            idle_flag=False
        )

        assert nudge is not None

        # Check telemetry was logged
        assert telemetry_path.exists()

        with open(telemetry_path, "r") as f:
            lines = f.readlines()
            assert len(lines) >= 1

            entry = json.loads(lines[-1])
            assert entry["event"] == "nudge_shown"
            assert entry["user_id"] == "TEST"
            assert entry["nudge"]["target"] == "SkillDNA.programming.python_fluency"


# Test 7: Performance target (<200ms with cached data)
def test_performance_target(temp_data_dir, mock_config, mock_learning_report, mock_curiosity_agenda):
    """Test that orchestration completes in <200ms with cached data."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    # Warm up cache
    orchestrator._get_learning_report()

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = mock_curiosity_agenda

        # Measure orchestration time
        start = time.time()

        for _ in range(3):  # Run 3 times to ensure consistency
            orchestrator.on_turn_start(
                user_id="TEST",
                text="Hello",
                meta={"developer_mode": False},
                behavior_context={}
            )

            orchestrator.maybe_nudge(
                user_id="TEST",
                text="what next?",
                idle_flag=False
            )

        elapsed_ms = (time.time() - start) / 3 * 1000

        # Should be well under 200ms with mocked generate_agenda
        assert elapsed_ms < 200, f"Orchestration took {elapsed_ms:.2f}ms (target: <200ms)"


# Test 8: What-next classifier detects patterns
def test_what_next_classifier():
    """Test that is_what_next_query correctly identifies queries."""
    assert coach_mode_manager.is_what_next_query("what next?") == True
    assert coach_mode_manager.is_what_next_query("What should we do now?") == True
    assert coach_mode_manager.is_what_next_query("any ideas?") == True
    assert coach_mode_manager.is_what_next_query("where should we start") == True
    assert coach_mode_manager.is_what_next_query("what else?") == True
    assert coach_mode_manager.is_what_next_query("suggest something") == True

    # Negative cases
    assert coach_mode_manager.is_what_next_query("I like pizza") == False
    assert coach_mode_manager.is_what_next_query("Tell me about your day") == False
    assert coach_mode_manager.is_what_next_query("") == False


# Test 9: Below threshold suppressed
def test_below_threshold_suppressed(temp_data_dir, mock_config, mock_learning_report):
    """Test that nudges below min_priority are suppressed."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    low_priority_agenda = {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "target": "SomeDNA.low_priority",
                "priority": 0.45,  # Below 0.65 threshold
                "reason": "Low priority",
                "suggested_coach": "head_coach",
                "suggested_prompt": "Tell me more.",
                "evidence_refs": []
            }
        ],
        "total_candidates": 1,
        "above_threshold": 0
    }

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = low_priority_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what next?",
            idle_flag=False
        )

        assert nudge is None  # Suppressed due to low priority


# Test 10: Nudge to_dict serialization
def test_nudge_to_dict():
    """Test that Nudge objects serialize correctly to dict."""
    nudge = Nudge(
        kind="curiosity_nudge",
        title="Test Nudge",
        coach_id="career_coach",
        prompt="Tell me about your skills",
        priority=0.85,
        reason="High impact",
        requires_consent=False,
        target="SkillDNA.test",
        evidence_refs=["ref1", "ref2"]
    )

    nudge_dict = nudge.to_dict()

    assert nudge_dict["kind"] == "curiosity_nudge"
    assert nudge_dict["title"] == "Test Nudge"
    assert nudge_dict["coach_id"] == "career_coach"
    assert nudge_dict["prompt"] == "Tell me about your skills"
    assert nudge_dict["priority"] == 0.85
    assert nudge_dict["reason"] == "High impact"
    assert nudge_dict["requires_consent"] == False
    assert nudge_dict["target"] == "SkillDNA.test"
    assert nudge_dict["evidence_refs"] == ["ref1", "ref2"]


# Test 11: Developer mode includes learning summary
def test_developer_mode_learning_summary(temp_data_dir, mock_config, mock_learning_report):
    """Test that developer mode includes learning summary in context."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    enriched_context = orchestrator.on_turn_start(
        user_id="TEST",
        text="Hello",
        meta={"developer_mode": True},
        behavior_context={}
    )

    assert "learning_summary" in enriched_context
    assert enriched_context["learning_summary"]["total_turns_analyzed"] == 290  # 150+80+60
    assert enriched_context["learning_summary"]["coaches_analyzed"] == 3


# Test 12: Photo namespace requires consent
def test_photo_namespace_requires_consent(temp_data_dir, mock_config, mock_learning_report):
    """Test that Photo namespace targets require consent."""
    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    photo_agenda = {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "target": "Photo.vacation_memories",
                "priority": 0.80,
                "reason": "High impact",
                "suggested_coach": "photo_coach",
                "suggested_prompt": "Share your vacation photos.",
                "evidence_refs": []
            }
        ],
        "total_candidates": 1,
        "above_threshold": 1
    }

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = photo_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what next?",
            idle_flag=False
        )

        assert nudge is not None
        assert nudge.requires_consent == True
        assert nudge.target.startswith("Photo")


# Test 13: Fallback agenda generates nudge
def test_fallback_agenda_generates_nudge(temp_data_dir, mock_config, mock_learning_report):
    """Test that fallback agenda (priority ~0.5) still generates nudge if above threshold."""
    # Lower threshold to accept fallback priority
    config = json.load(open(mock_config))
    config["min_nudge_priority"] = 0.4
    with open(mock_config, "w") as f:
        json.dump(config, f)

    orchestrator = HCOrchestrator(config_path=mock_config, data_root=temp_data_dir)

    fallback_agenda = {
        "user_id": "TEST",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "target": "SkillDNA.general_exploration",
                "priority": 0.5,
                "reason": "fallback_agenda_due_to_low_signal",
                "suggested_coach": "career_coach",
                "suggested_prompt": "Tell me about your recent work experience and skills.",
                "evidence_refs": ["fallback:no_telemetry"]
            }
        ],
        "total_candidates": 2000,
        "above_threshold": 0,
        "debug": {
            "reason": "low telemetry signal; fallback agenda generated"
        }
    }

    with patch("ReDNACoreDemo.core.curiosity.curiosity_engine_v2.generate_agenda") as mock_generate:
        mock_generate.return_value = fallback_agenda

        nudge = orchestrator.maybe_nudge(
            user_id="TEST",
            text="what next?",
            idle_flag=False
        )

        assert nudge is not None
        assert nudge.priority == 0.5
        assert nudge.reason == "fallback_agenda_due_to_low_signal"
        assert "fallback" in nudge.evidence_refs[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
