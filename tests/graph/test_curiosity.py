"""
Tests for graph-aware curiosity question selection (Phase 8 Stage 4).

Acceptance Criteria:
- AC3: GET /user/{id}/next_question returns ≥1 candidate within 60s
- Question has trait_id, question_text, curiosity_score, rationale
"""

from __future__ import annotations
import pytest

from ReDNACoreDemo.core.graph.curiosity import choose_next_question
from ReDNACoreDemo.core.graph.belief import on_trait_promotion
from ReDNACoreDemo.core.graph.storage import FileGraphStorage
from ReDNACoreDemo.core.graph.schemas import OntologyGraph, OntologyNode, OntologyEdge


def test_curiosity_question_after_promotion(tmp_path, monkeypatch):
    """
    AC3: After promotion, next_question returns a valid candidate.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        # Seed minimal ontology
        ontology = OntologyGraph(
            nodes=[
                OntologyNode(
                    node_id="ont_chronotype",
                    node_type="trait",
                    trait_id="PaDNA.Chronotype",
                    label="Chronotype",
                    category="Behavioral"
                )
            ]
        )
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.curiosity.get_graph_storage", mock_get_storage)

    # Promote a trait with high uncertainty
    on_trait_promotion(
        user_id="curiosity_test",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=500.0,
        ucn={"u": 0.8, "c": 0.7, "n": 0.6},  # High uncertainty
        observation_text="I think I'm a morning person",
        observation_source="chat",
    )

    # Request next question
    response = choose_next_question("curiosity_test", strategy="auto")

    # Verify response structure (AC3)
    assert response.question_text
    assert len(response.question_text) > 0
    assert response.target_trait_id
    assert response.rationale
    assert 0.0 <= response.confidence <= 1.0


def test_curiosity_depth_strategy(tmp_path, monkeypatch):
    """
    Test depth strategy: refines existing high-uncertainty traits.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph(nodes=[
            OntologyNode(
                node_id="ont_chrono",
                node_type="trait",
                trait_id="PaDNA.Chronotype",
                label="Chronotype",
                category="Behavioral"
            )
        ])
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.curiosity.get_graph_storage", mock_get_storage)

    # Promote trait with high uncertainty
    on_trait_promotion(
        user_id="depth_test",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=450.0,
        ucn={"u": 0.75, "c": 0.6, "n": 0.5},
        observation_text="I wake up early sometimes",
        observation_source="chat",
    )

    # Request depth question
    response = choose_next_question("depth_test", strategy="depth")

    # Should ask follow-up about Chronotype
    assert "PaDNA.Chronotype" in response.target_trait_id or "chronotype" in response.question_text.lower()
    assert "uncertainty" in response.rationale.lower() or "trait" in response.rationale.lower()


def test_curiosity_breadth_strategy(tmp_path, monkeypatch):
    """
    Test breadth strategy: explores ontology neighbors.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)

        # Create ontology with suggests_question edge
        ontology = OntologyGraph(
            nodes=[
                OntologyNode(
                    node_id="ont_chrono",
                    node_type="trait",
                    trait_id="PaDNA.Chronotype",
                    label="Chronotype",
                    category="Behavioral"
                ),
                OntologyNode(
                    node_id="ont_exercise",
                    node_type="trait",
                    trait_id="BehaviorDNA.Exercise.Timing",
                    label="Exercise Timing",
                    category="Behavioral"
                )
            ],
            edges=[
                OntologyEdge(
                    edge_id="edge_chrono_exercise",
                    from_node="ont_chrono",
                    to_node="ont_exercise",
                    edge_type="suggests_question",
                    weight=0.8,
                    confidence=0.9,
                    source="seed",
                    rationale="Chronotype influences optimal exercise timing"
                )
            ]
        )
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.curiosity.get_graph_storage", mock_get_storage)

    # User has Chronotype but not Exercise Timing
    on_trait_promotion(
        user_id="breadth_test",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=800.0,
        ucn={"u": 0.2, "c": 0.8, "n": 0.7},
        observation_text="I'm definitely a morning person",
        observation_source="chat",
    )

    # Request breadth question
    response = choose_next_question("breadth_test", strategy="breadth")

    # Should suggest Exercise Timing (ontology neighbor)
    assert response.target_trait_id == "BehaviorDNA.Exercise.Timing" or "exercise" in response.question_text.lower()


def test_curiosity_fallback_for_new_user(tmp_path, monkeypatch):
    """
    Test fallback: new user with no traits gets generic question.
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph()  # Empty ontology
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.curiosity.get_graph_storage", mock_get_storage)

    # New user, no traits
    response = choose_next_question("brand_new_user", strategy="auto")

    # Should return generic fallback question
    assert response.question_text
    assert len(response.question_text) > 0
    assert response.confidence > 0  # Even fallback has some confidence


def test_curiosity_question_non_empty_rationale(tmp_path, monkeypatch):
    """
    Test that all questions include a rationale (AC3).
    """
    def mock_get_storage():
        storage = FileGraphStorage(tmp_path)
        ontology = OntologyGraph(nodes=[
            OntologyNode(
                node_id="ont_height",
                node_type="trait",
                trait_id="PaDNA.Height",
                label="Height",
                category="Physical"
            )
        ])
        storage.save_ontology(ontology)
        return storage

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)
    monkeypatch.setattr("ReDNACoreDemo.core.graph.curiosity.get_graph_storage", mock_get_storage)

    # Create user with one trait
    on_trait_promotion(
        user_id="rationale_test",
        trait_id="PaDNA.Height",
        value={"int": 180},
        rr_score=950.0,
        ucn={"u": 0.05, "c": 0.95, "n": 0.9},
        observation_text="I am 180cm tall",
        observation_source="onboarding",
    )

    response = choose_next_question("rationale_test", strategy="auto")

    # Verify rationale is non-empty and descriptive
    assert response.rationale
    assert len(response.rationale) > 10  # Should be a real sentence
