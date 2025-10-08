"""
Unit tests for Head Coach v2 Situational Awareness Engine.

Tests the 4-layer awareness model, TTL caching, emotional tone detection,
privacy guarantees, and Workshop compatibility.

Coverage target: ≥95%
"""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from jsonschema import validate, ValidationError

from ReDNACoreDemo.core.head_coach.situational_awareness import AwarenessEngine


@pytest.fixture
def awareness_engine():
    """Create AwarenessEngine instance."""
    return AwarenessEngine()


@pytest.fixture
def custom_tone_engine():
    """Create AwarenessEngine with custom tone extractor."""
    def mock_tone_extractor(messages):
        return ("positive", 0.95)
    return AwarenessEngine(tone_extractor=mock_tone_extractor)


@pytest.fixture
def schema():
    """Load the hc_awareness JSON schema."""
    schema_path = Path(__file__).parents[1] / "schemas" / "hc_awareness.schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def mock_user_data():
    """Mock user data structures."""
    return {
        "user_json": {
            "coach_mode": "head_coach",
            "active_goals": [{"goal": "Improve presentation skills", "priority": 8}],
            "pending_tasks": [{"task": "Practice pitch deck", "due": "2025-10-10"}]
        },
        "hc_runtime_state": {
            "delegation_state": "idle",
            "last_active_coach": "career_coach"
        },
        "observations": [
            {"trait": "SkillDNA.PresentationDNA", "value": 65, "timestamp": "2025-10-07T00:00:00Z"},
            {"trait": "BeliefDNA.GrowthMindset", "value": 80, "timestamp": "2025-10-07T00:00:00Z"}
        ],
        "resolved": {
            "CareerDNA": {"overall": 72},
            "RelationshipDNA": {"overall": 68},
            "PersonalityDNA": {"overall": 75}
        },
        "chat_history": [
            {"role": "user", "content": "I'm frustrated with my progress", "timestamp": "2025-10-07T01:00:00Z"},
            {"role": "assistant", "content": "Let's work through this together", "timestamp": "2025-10-07T01:01:00Z"}
        ]
    }


class TestAwarenessSnapshotBuild:
    """Test snapshot building for existing users."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.curiosity_engine')
    def test_snapshot_builds_successfully(self, mock_curiosity, mock_load_json, mock_load_info,
                                         awareness_engine, mock_user_data, schema):
        """Test that snapshot builds successfully for existing user."""
        # Mock data loading
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.side_effect = lambda path: {
            "hc_runtime_state.json": mock_user_data["hc_runtime_state"],
            "observations.json": mock_user_data["observations"],
            "resolved.json": mock_user_data["resolved"]
        }.get(Path(path).name, {})

        mock_curiosity.get_top_hotspots.return_value = ["SkillDNA.PresentationDNA", "BeliefDNA.GrowthMindset"]

        # Build snapshot
        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=False)

        # Validate structure
        assert "core" in snapshot
        assert "goal_task" in snapshot
        assert "context" in snapshot
        assert "memory" in snapshot
        assert "emotional_tone" in snapshot
        assert "emotion_confidence" in snapshot
        assert "ttl_hints" in snapshot
        assert "policy" in snapshot
        assert "summary" in snapshot

        # Validate against JSON schema
        validate(instance=snapshot, schema=schema)

        # Validate core layer
        assert snapshot["core"]["active_coach"] == "head_coach"
        assert "SkillDNA.PresentationDNA" in snapshot["core"]["curiosity_hotspots"]

        # Validate goal/task layer
        assert len(snapshot["goal_task"]["active_goals"]) == 1
        assert snapshot["goal_task"]["active_goals"][0]["goal"] == "Improve presentation skills"

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    def test_missing_user_raises_error(self, mock_load_info, awareness_engine):
        """Test that missing user raises FileNotFoundError."""
        mock_load_info.side_effect = FileNotFoundError("User not found")

        with pytest.raises(FileNotFoundError):
            awareness_engine.get_snapshot("NONEXISTENT")


class TestEmotionalToneDetection:
    """Test emotional tone extraction."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_frustrated_tone_detected(self, mock_load_json, mock_load_info, awareness_engine, mock_user_data):
        """Test that frustrated tone is detected from messages."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        # Mock chat history with frustrated messages
        with patch.object(awareness_engine, '_load_recent_messages') as mock_messages:
            mock_messages.return_value = [
                {"role": "user", "content": "I'm so frustrated with this"},
                {"role": "user", "content": "This is stupid and annoying"}
            ]

            snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        assert snapshot["emotional_tone"] == "frustrated"
        assert snapshot["emotion_confidence"] > 0.5

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_positive_tone_detected(self, mock_load_json, mock_load_info, awareness_engine, mock_user_data):
        """Test that positive tone is detected from messages."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        with patch.object(awareness_engine, '_load_recent_messages') as mock_messages:
            mock_messages.return_value = [
                {"role": "user", "content": "This is great! Thanks so much!"},
                {"role": "user", "content": "I love how this is working"}
            ]

            snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        assert snapshot["emotional_tone"] == "positive"

    def test_custom_tone_extractor_used(self, custom_tone_engine, mock_user_data):
        """Test that custom tone extractor is used when provided."""
        with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info') as mock_load_info:
            with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json') as mock_load_json:
                mock_load_info.return_value = mock_user_data["user_json"]
                mock_load_json.return_value = {}

                snapshot = custom_tone_engine.get_snapshot("TEST", force_refresh=True)

        # Custom extractor always returns positive with 0.95 confidence
        assert snapshot["emotional_tone"] == "positive"
        assert snapshot["emotion_confidence"] == 0.95


class TestTTLCaching:
    """Test TTL-based caching for each layer."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.curiosity_engine')
    def test_core_layer_never_cached(self, mock_curiosity, mock_load_json, mock_load_info,
                                    awareness_engine, mock_user_data):
        """Test that core layer is always fresh (TTL = 0)."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}
        mock_curiosity.get_top_hotspots.return_value = ["Trait1"]

        # First call
        snapshot1 = awareness_engine.get_snapshot("TEST", force_refresh=False)

        # Change active coach
        mock_user_data["user_json"]["coach_mode"] = "career_coach"

        # Second call (should not use cache for core)
        snapshot2 = awareness_engine.get_snapshot("TEST", force_refresh=False)

        # Core should reflect new data (no cache)
        assert snapshot1["core"]["active_coach"] == "head_coach"
        assert snapshot2["core"]["active_coach"] == "career_coach"

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_goal_task_layer_cached_5min(self, mock_load_json, mock_load_info,
                                         awareness_engine, mock_user_data):
        """Test that goal/task layer is cached for 5 minutes."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        # First call
        snapshot1 = awareness_engine.get_snapshot("TEST", force_refresh=False)
        original_goals = snapshot1["goal_task"]["active_goals"]

        # Change goals
        mock_user_data["user_json"]["active_goals"] = [{"goal": "New goal", "priority": 9}]

        # Second call immediately (should use cache)
        snapshot2 = awareness_engine.get_snapshot("TEST", force_refresh=False)

        # Should return cached goals (not new ones)
        assert snapshot2["goal_task"]["active_goals"] == original_goals

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_force_refresh_clears_cache(self, mock_load_json, mock_load_info,
                                        awareness_engine, mock_user_data):
        """Test that force_refresh=True bypasses all caches."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        # First call
        snapshot1 = awareness_engine.get_snapshot("TEST", force_refresh=False)

        # Change data
        mock_user_data["user_json"]["active_goals"] = [{"goal": "Forced refresh goal", "priority": 10}]

        # Force refresh
        snapshot2 = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Should get new data
        assert snapshot2["goal_task"]["active_goals"][0]["goal"] == "Forced refresh goal"

    def test_ttl_hints_present(self, awareness_engine, mock_user_data):
        """Test that TTL hints are included in snapshot."""
        with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info') as mock_load_info:
            with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json') as mock_load_json:
                mock_load_info.return_value = mock_user_data["user_json"]
                mock_load_json.return_value = {}

                snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Validate TTL hints structure
        assert "ttl_hints" in snapshot
        assert snapshot["ttl_hints"]["core"] == "live"
        assert snapshot["ttl_hints"]["goal_task"] == "<=5m"
        assert snapshot["ttl_hints"]["context"] == "<=1h"
        assert snapshot["ttl_hints"]["memory"] == "<=24h"


class TestPrivacyGuarantees:
    """Test that no raw message text is included."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_no_raw_messages_in_snapshot(self, mock_load_json, mock_load_info,
                                         awareness_engine, mock_user_data):
        """Test that snapshot never includes raw message text."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Convert to JSON string and check for message content
        snapshot_str = json.dumps(snapshot)

        # Should not contain raw message text
        assert "I'm frustrated with my progress" not in snapshot_str
        assert "Let's work through this together" not in snapshot_str

        # Policy should indicate redacted fields
        assert "redacted_fields" in snapshot["policy"]
        assert "raw_messages" in snapshot["policy"]["redacted_fields"]


class TestWorkshopCompatibility:
    """Test Workshop UI compatibility features."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.curiosity_engine')
    def test_summary_block_present(self, mock_curiosity, mock_load_json, mock_load_info,
                                   awareness_engine, mock_user_data):
        """Test that summary block is present for Workshop UI."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}
        mock_curiosity.get_top_hotspots.return_value = ["SkillDNA.PresentationDNA", "BeliefDNA.GrowthMindset"]

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Validate summary structure
        assert "summary" in snapshot
        assert "active_goal_count" in snapshot["summary"]
        assert "pending_tasks" in snapshot["summary"]
        assert "top_curiosity" in snapshot["summary"]
        assert "emotional_state" in snapshot["summary"]

        # Validate summary values
        assert snapshot["summary"]["active_goal_count"] == 1
        assert snapshot["summary"]["pending_tasks"] == 1
        assert len(snapshot["summary"]["top_curiosity"]) <= 5

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_emotional_state_mapping(self, mock_load_json, mock_load_info,
                                     awareness_engine, mock_user_data):
        """Test that emotional_tone maps to readable emotional_state."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        with patch.object(awareness_engine, '_load_recent_messages') as mock_messages:
            mock_messages.return_value = [
                {"role": "user", "content": "This is great!"}
            ]

            snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Should have readable emotional state
        assert snapshot["summary"]["emotional_state"] in [
            "Positive and engaged",
            "Neutral and focused",
            "Experiencing challenges",
            "Frustrated but working through it",
            "Curious and engaged"
        ]


class TestPolicyMetadata:
    """Test audit/provenance policy metadata."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_policy_block_present(self, mock_load_json, mock_load_info,
                                  awareness_engine, mock_user_data):
        """Test that policy block is present with required fields."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Validate policy structure
        assert "policy" in snapshot
        assert "awareness_version" in snapshot["policy"]
        assert "schema" in snapshot["policy"]
        assert "build_ms" in snapshot["policy"]
        assert "redacted_fields" in snapshot["policy"]

        # Validate policy values
        assert snapshot["policy"]["awareness_version"] == "v1"
        assert snapshot["policy"]["schema"] == "hc_awareness.schema.json@v1"
        assert isinstance(snapshot["policy"]["build_ms"], (int, float))
        assert snapshot["policy"]["build_ms"] >= 0

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_build_time_recorded(self, mock_load_json, mock_load_info,
                                 awareness_engine, mock_user_data):
        """Test that build time is recorded in milliseconds."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Build time should be reasonable (< 100ms for unit test)
        assert snapshot["policy"]["build_ms"] < 100


class TestCuriosityIntegration:
    """Test integration with curiosity engine."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.curiosity_engine')
    def test_curiosity_hotspots_populated(self, mock_curiosity, mock_load_json, mock_load_info,
                                          awareness_engine, mock_user_data):
        """Test that curiosity hotspots are populated from curiosity engine."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}

        # Mock curiosity engine response
        mock_curiosity.get_top_hotspots.return_value = [
            "SkillDNA.PresentationDNA",
            "BeliefDNA.GrowthMindset",
            "RelationshipDNA.Networking"
        ]

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Should have curiosity hotspots
        assert len(snapshot["core"]["curiosity_hotspots"]) == 3
        assert "SkillDNA.PresentationDNA" in snapshot["core"]["curiosity_hotspots"]

        # Summary should have top 5 (or fewer)
        assert len(snapshot["summary"]["top_curiosity"]) <= 5


class TestSchemaCompliance:
    """Test compliance with JSON schema."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.curiosity_engine')
    def test_snapshot_validates_against_schema(self, mock_curiosity, mock_load_json, mock_load_info,
                                               awareness_engine, mock_user_data, schema):
        """Test that generated snapshot validates against JSON schema."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.return_value = {}
        mock_curiosity.get_top_hotspots.return_value = ["SkillDNA.PresentationDNA"]

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Should validate without errors
        validate(instance=snapshot, schema=schema)

    def test_emotional_tone_enum_valid(self, awareness_engine, mock_user_data, schema):
        """Test that emotional_tone uses valid enum values."""
        with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info') as mock_load_info:
            with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json') as mock_load_json:
                mock_load_info.return_value = mock_user_data["user_json"]
                mock_load_json.return_value = {}

                snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # emotional_tone must be one of the enum values
        valid_tones = ["positive", "neutral", "negative", "frustrated", "curious"]
        assert snapshot["emotional_tone"] in valid_tones

    def test_emotion_confidence_range_valid(self, awareness_engine, mock_user_data):
        """Test that emotion_confidence is between 0.0 and 1.0."""
        with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info') as mock_load_info:
            with patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json') as mock_load_json:
                mock_load_info.return_value = mock_user_data["user_json"]
                mock_load_json.return_value = {}

                snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # emotion_confidence must be 0.0 to 1.0
        assert 0.0 <= snapshot["emotion_confidence"] <= 1.0


class TestMemoryLayer:
    """Test memory layer (24h TTL) with RR aggregation."""

    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_user_info')
    @patch('ReDNACoreDemo.core.head_coach.situational_awareness.load_json')
    def test_rr_by_domain_populated(self, mock_load_json, mock_load_info,
                                    awareness_engine, mock_user_data):
        """Test that RR by domain is populated in memory layer."""
        mock_load_info.return_value = mock_user_data["user_json"]
        mock_load_json.side_effect = lambda path: {
            "resolved.json": mock_user_data["resolved"]
        }.get(Path(path).name, {})

        snapshot = awareness_engine.get_snapshot("TEST", force_refresh=True)

        # Should have RR by domain
        assert "rr_by_domain" in snapshot["memory"]
        assert "CareerDNA" in snapshot["memory"]["rr_by_domain"]
        assert snapshot["memory"]["rr_by_domain"]["CareerDNA"] == 72
