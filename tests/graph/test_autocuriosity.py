"""
Tests for LLM-powered auto-curiosity (Phase 10.1).

Tests:
1. Deterministic fallback when WHYCARD_USE_LLM=false
2. Non-empty question_text when LLM enabled
3. Presence of source metadata (via rationale)
4. LLM timeout → fallback path works
5. Cache hit behavior
6. Cache miss behavior
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from ReDNACoreDemo.core.graph.curiosity import (
    choose_next_question,
    generate_llm_question,
    _check_question_cache,
    _cache_question,
)


@pytest.fixture
def mock_user_graph():
    """Mock BeliefGraph with some trait nodes."""
    from ReDNACoreDemo.core.graph.schemas import BeliefGraph, BeliefNode

    nodes = [
        BeliefNode(
            node_id="node_1",
            node_type="trait",
            trait_id="PaDNA.Chronotype",
            label="Chronotype",
            rr=30,
            curiosity=70,
            ucn={"u": 0.7, "c": 0.5, "n": 0.3},
        ),
        BeliefNode(
            node_id="node_2",
            node_type="trait",
            trait_id="PaDNA.Height",
            label="Height",
            rr=85,
            curiosity=15,
            ucn={"u": 0.15, "c": 0.9, "n": 0.85},
        ),
    ]

    return BeliefGraph(nodes=nodes, edges=[])


@pytest.fixture
def mock_ontology():
    """Mock OntologyGraph."""
    from ReDNACoreDemo.core.graph.schemas import OntologyGraph, OntologyNode, OntologyEdge

    nodes = [
        OntologyNode(
            node_id="ont_chronotype",
            node_type="trait",
            trait_id="PaDNA.Chronotype",
            label="Chronotype",
        ),
        OntologyNode(
            node_id="ont_exercise",
            node_type="trait",
            trait_id="BehaviorDNA.Exercise.Frequency",
            label="Exercise Frequency",
        ),
    ]

    edges = [
        OntologyEdge(
            edge_id="edge_1",
            from_node="ont_chronotype",
            to_node="ont_exercise",
            edge_type="suggests_question",
            weight=0.7,
            confidence=0.9,
            source="seed",
        )
    ]

    return OntologyGraph(nodes=nodes, edges=edges)


class TestDeterministicFallback:
    """Test deterministic question generation when LLM disabled."""

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "false"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_deterministic_when_disabled(self, mock_storage, mock_user_graph, mock_ontology):
        """Verify deterministic templates when WHYCARD_USE_LLM=false."""
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        result = choose_next_question("test_user", strategy="depth")

        assert result.question_text
        assert result.target_trait_id
        assert result.rationale
        # Deterministic should use template like "Can you tell me more about..."
        assert "chronotype" in result.question_text.lower() or "height" in result.question_text.lower()


class TestLLMQuestionGeneration:
    """Test LLM-powered question generation."""

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_llm_generates_non_empty_question(self, mock_storage, mock_llm_client, mock_user_graph, mock_ontology):
        """Verify non-empty question_text when LLM enabled and working."""
        # Mock storage
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        # Mock LLM client
        mock_client_instance = Mock()
        mock_client_instance.health.return_value = True
        mock_client_instance.chat.return_value = {
            "message": {
                "content": "What time of day do you feel most alert and productive?"
            }
        }
        mock_llm_client.return_value = mock_client_instance

        result = choose_next_question("test_user", strategy="depth")

        assert result.question_text
        assert len(result.question_text) > 0
        assert result.target_trait_id
        assert result.rationale

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_llm_source_in_rationale(self, mock_storage, mock_llm_client, mock_user_graph, mock_ontology):
        """Verify presence of source:LLM metadata (via rationale)."""
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        mock_client_instance = Mock()
        mock_client_instance.health.return_value = True
        mock_client_instance.chat.return_value = {
            "message": {
                "content": "What time of day do you feel most alert?"
            }
        }
        mock_llm_client.return_value = mock_client_instance

        result = choose_next_question("test_user", strategy="depth")

        # Rationale should indicate LLM generation
        assert "LLM-generated" in result.rationale or "llm" in result.rationale.lower()


class TestLLMTimeout:
    """Test fallback behavior when LLM times out or fails."""

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_llm_timeout_fallback(self, mock_storage, mock_llm_client, mock_user_graph, mock_ontology):
        """Simulate LLM timeout and verify fallback to deterministic."""
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        # Mock LLM client to raise timeout
        mock_client_instance = Mock()
        mock_client_instance.health.return_value = True
        mock_client_instance.chat.side_effect = Exception("Timeout")
        mock_llm_client.return_value = mock_client_instance

        result = choose_next_question("test_user", strategy="depth")

        # Should still return a valid question (deterministic fallback)
        assert result.question_text
        assert result.target_trait_id
        assert result.rationale

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_llm_health_check_failed(self, mock_storage, mock_llm_client, mock_user_graph, mock_ontology):
        """Verify fallback when Ollama not accessible."""
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        # Mock LLM client health check to fail
        mock_client_instance = Mock()
        mock_client_instance.health.return_value = False
        mock_llm_client.return_value = mock_client_instance

        result = choose_next_question("test_user", strategy="depth")

        # Should still return valid question (deterministic)
        assert result.question_text
        assert result.target_trait_id

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    def test_llm_empty_response_fallback(self, mock_llm_client):
        """Verify fallback when LLM returns empty response."""
        mock_client_instance = Mock()
        mock_client_instance.health.return_value = True
        mock_client_instance.chat.return_value = {
            "message": {
                "content": ""  # Empty content
            }
        }
        mock_llm_client.return_value = mock_client_instance

        graph_context = [
            {"trait_id": "PaDNA.Height", "rr": 85, "curiosity": 15}
        ]

        result = generate_llm_question("test_user", "PaDNA.Chronotype", graph_context)

        # Should return None (empty response)
        assert result is None


class TestQuestionCache:
    """Test question caching behavior."""

    def test_cache_miss(self, tmp_path, monkeypatch):
        """Verify cache miss when no cache exists."""
        # Mock ensure_dirs_for_user to use tmp_path
        def mock_ensure_dirs(user_id):
            user_dir = tmp_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            return {"udir": str(user_dir)}

        monkeypatch.setattr(
            "ReDNACoreDemo.core.graph.curiosity.ensure_dirs_for_user",
            mock_ensure_dirs
        )

        # Check cache (should be None)
        cached = _check_question_cache("test_user", "PaDNA.Chronotype")
        assert cached is None

    def test_cache_hit(self, tmp_path, monkeypatch):
        """Verify cache hit when question exists."""
        def mock_ensure_dirs(user_id):
            user_dir = tmp_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            return {"udir": str(user_dir)}

        monkeypatch.setattr(
            "ReDNACoreDemo.core.graph.curiosity.ensure_dirs_for_user",
            mock_ensure_dirs
        )

        # Cache a question
        llm_result = {
            "question_text": "What time of day do you feel most alert?",
            "rationale": "LLM-generated question for Chronotype",
            "source": "LLM",
            "model": "llama3:8b",
            "timestamp": "2025-10-20T12:00:00Z",
        }

        _cache_question("test_user", "PaDNA.Chronotype", llm_result)

        # Check cache (should return cached question)
        cached = _check_question_cache("test_user", "PaDNA.Chronotype")

        assert cached is not None
        assert cached["question_text"] == llm_result["question_text"]
        assert cached["target_trait_id"] == "PaDNA.Chronotype"
        assert cached["source"] == "LLM"

    def test_cache_different_trait(self, tmp_path, monkeypatch):
        """Verify cache miss when checking different trait."""
        def mock_ensure_dirs(user_id):
            user_dir = tmp_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            return {"udir": str(user_dir)}

        monkeypatch.setattr(
            "ReDNACoreDemo.core.graph.curiosity.ensure_dirs_for_user",
            mock_ensure_dirs
        )

        # Cache for Chronotype
        llm_result = {
            "question_text": "What time of day do you feel most alert?",
            "rationale": "LLM-generated question for Chronotype",
            "source": "LLM",
            "model": "llama3:8b",
            "timestamp": "2025-10-20T12:00:00Z",
        }

        _cache_question("test_user", "PaDNA.Chronotype", llm_result)

        # Check cache for different trait (should be None)
        cached = _check_question_cache("test_user", "PaDNA.Height")
        assert cached is None


class TestEndToEnd:
    """End-to-end integration tests."""

    @patch.dict(os.environ, {"WHYCARD_USE_LLM": "true"}, clear=False)
    @patch("ReDNACoreDemo.core.graph.curiosity.LLMClient")
    @patch("ReDNACoreDemo.core.graph.curiosity.get_graph_storage")
    def test_full_llm_flow_with_cache(self, mock_storage, mock_llm_client, mock_user_graph, mock_ontology, tmp_path, monkeypatch):
        """Test full flow: LLM generation → cache → cache hit."""
        # Mock storage
        mock_storage.return_value.load_user_graph.return_value = mock_user_graph
        mock_storage.return_value.load_ontology.return_value = mock_ontology

        # Mock LLM client
        mock_client_instance = Mock()
        mock_client_instance.health.return_value = True
        mock_client_instance.chat.return_value = {
            "message": {
                "content": "What time of day do you feel most alert and productive?"
            }
        }
        mock_llm_client.return_value = mock_client_instance

        # Mock ensure_dirs_for_user
        def mock_ensure_dirs(user_id):
            user_dir = tmp_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            return {"udir": str(user_dir)}

        monkeypatch.setattr(
            "ReDNACoreDemo.core.graph.curiosity.ensure_dirs_for_user",
            mock_ensure_dirs
        )

        # First call (cache miss, should call LLM)
        result1 = choose_next_question("test_user", strategy="depth")
        assert result1.question_text
        assert "LLM-generated" in result1.rationale

        # Verify cache file exists
        cache_path = tmp_path / "test_user" / "question_cache" / "llm_questions.jsonl"
        assert cache_path.exists()

        # Verify cache content
        cache_lines = cache_path.read_text().strip().split("\n")
        assert len(cache_lines) >= 1
        cache_entry = json.loads(cache_lines[-1])
        assert cache_entry["source"] == "LLM"

        # Second call (cache hit, should NOT call LLM again)
        # Reset mock to verify it's not called
        mock_client_instance.chat.reset_mock()

        result2 = choose_next_question("test_user", strategy="depth")
        assert result2.question_text
        assert "(cached)" in result2.rationale.lower()

        # Verify LLM was not called on second request
        mock_client_instance.chat.assert_not_called()
