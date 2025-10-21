"""
Tests for relational insight generation (Phase 8 Stage 4 - MVP Benchmark #13).

Acceptance Criteria:
- AC4: With ≥10 traits, /user/{id}/insight returns text + cited_nodes
- Returns None if <10 traits
"""

from __future__ import annotations
import pytest

from ReDNACoreDemo.core.graph.insight import generate_insight
from ReDNACoreDemo.core.graph.belief import on_trait_promotion
from ReDNACoreDemo.core.graph.storage import FileGraphStorage
from ReDNACoreDemo.core.graph.schemas import OntologyGraph, OntologyNode


def test_insight_requires_ten_traits(tmp_path, monkeypatch):
    """
    AC4: Insight generation requires ≥10 traits.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.insight.get_graph_storage", mock_get_storage)

    user_id = "insight_test_user"

    # Promote only 5 traits
    for i in range(5):
        on_trait_promotion(
            user_id=user_id,
            trait_id=f"Trait{i}",
            value=f"Value{i}",
            rr_score=700.0,
            ucn={"u": 0.3, "c": 0.6, "n": 0.5},
            observation_text=f"Observation {i}",
            observation_source="test",
        )

    # Should return None (insufficient traits)
    insight = generate_insight(user_id)
    assert insight is None


def test_insight_generation_with_ten_traits(tmp_path, monkeypatch):
    """
    AC4: With ≥10 traits, insight is generated with cited nodes.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.insight.get_graph_storage", mock_get_storage)

    user_id = "ten_traits_user"

    # Promote exactly 10 traits
    for i in range(10):
        on_trait_promotion(
            user_id=user_id,
            trait_id=f"TestTrait{i}",
            value=f"Value{i}",
            rr_score=600.0 + (i * 10),  # Varying RR scores
            ucn={"u": 0.2 + (i * 0.01), "c": 0.7, "n": 0.5},
            observation_text=f"I have trait {i}",
            observation_source="test",
        )

    # Should generate insight
    insight = generate_insight(user_id)

    assert insight is not None
    assert insight.text
    assert len(insight.text) > 20  # Should be a real insight, not stub

    # AC4: Cited nodes must be present
    assert insight.cited_nodes
    assert len(insight.cited_nodes) > 0

    # Verify confidence is reasonable
    assert 0.0 <= insight.confidence <= 1.0


def test_insight_chronotype_pattern(tmp_path, monkeypatch):
    """
    Test that Chronotype + Exercise pattern is detected.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.insight.get_graph_storage", mock_get_storage)

    user_id = "chronotype_pattern_user"

    # Create base traits (8 generic + 2 specific for pattern)
    for i in range(8):
        on_trait_promotion(
            user_id=user_id,
            trait_id=f"FillTrait{i}",
            value=f"Value{i}",
            rr_score=600.0,
            ucn={"u": 0.3, "c": 0.6, "n": 0.5},
            observation_text=f"Generic trait {i}",
            observation_source="test",
        )

    # Add Chronotype = Morning Lark
    on_trait_promotion(
        user_id=user_id,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=800.0,
        ucn={"u": 0.2, "c": 0.8, "n": 0.7},
        observation_text="I wake up naturally at 6am",
        observation_source="chat",
    )

    # Add Exercise Frequency
    on_trait_promotion(
        user_id=user_id,
        trait_id="BehaviorDNA.Exercise.Frequency",
        value={"range": {"min": 4, "max": 6}},
        rr_score=750.0,
        ucn={"u": 0.25, "c": 0.75, "n": 0.6},
        observation_text="I exercise 4-6 times per week",
        observation_source="chat",
    )

    # Generate insight
    insight = generate_insight(user_id)

    assert insight is not None

    # Should mention morning/chronotype and exercise
    text_lower = insight.text.lower()
    assert "morning" in text_lower or "chronotype" in text_lower
    assert "exercise" in text_lower or "workout" in text_lower

    # Should cite both nodes
    assert len(insight.cited_nodes) >= 2


def test_insight_high_confidence_cluster(tmp_path, monkeypatch):
    """
    Test that high-confidence trait clusters are detected.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.insight.get_graph_storage", mock_get_storage)

    user_id = "high_conf_user"

    # Create 10 high-confidence traits
    for i in range(10):
        on_trait_promotion(
            user_id=user_id,
            trait_id=f"HighConfTrait{i}",
            value=f"Value{i}",
            rr_score=850.0,  # High RR
            ucn={"u": 0.15, "c": 0.85, "n": 0.8},  # Low uncertainty, high confidence
            observation_text=f"Very certain about trait {i}",
            observation_source="test",
        )

    insight = generate_insight(user_id)

    assert insight is not None

    # Should mention confidence or consistency
    text_lower = insight.text.lower()
    assert "confidence" in text_lower or "consistent" in text_lower or "stable" in text_lower

    # Should cite multiple high-confidence traits
    assert len(insight.cited_nodes) >= 3


def test_insight_returns_dict_format(tmp_path, monkeypatch):
    """
    Test that insight.to_dict() returns correct structure for API.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.insight.get_graph_storage", mock_get_storage)

    user_id = "dict_format_user"

    # Create 10 high-confidence traits (to trigger confidence cluster pattern)
    for i in range(10):
        on_trait_promotion(
            user_id=user_id,
            trait_id=f"Trait{i}",
            value=f"Value{i}",
            rr_score=850.0,  # High RR
            ucn={"u": 0.15, "c": 0.85, "n": 0.8},  # Low uncertainty, high confidence
            observation_text=f"Trait {i}",
            observation_source="test",
        )

    insight = generate_insight(user_id)
    assert insight is not None

    # Convert to dict
    data = insight.to_dict()

    # Verify keys
    assert "text" in data
    assert "cited_nodes" in data
    assert "confidence" in data
    assert "insight_type" in data
    assert "metadata" in data

    # Verify types
    assert isinstance(data["text"], str)
    assert isinstance(data["cited_nodes"], list)
    assert isinstance(data["confidence"], float)
