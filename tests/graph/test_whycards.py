"""
Tests for Why-Card generation and storage (Phase 8 Stage 4).

Acceptance Criteria:
- AC1: After ingest_evidence, edge has non-null why_card_id
- AC2: GET /core/graph/user/{id} returns Why-Card with what/why/next, RR, UCN
"""

from __future__ import annotations
import pytest

from ReDNACoreDemo.core.graph.belief import on_trait_promotion
from ReDNACoreDemo.core.graph.storage import FileGraphStorage
from ReDNACoreDemo.core.graph.schemas import WhyCard


def test_why_card_generated_on_promotion(tmp_path, monkeypatch):
    """
    AC1: After trait promotion, graph edge has non-null why_card_id.
    """
    # Patch storage to use tmp_path
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    # Promote a trait
    result = on_trait_promotion(
        user_id="whycard_test_user",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=720.0,
        ucn={"u": 0.3, "c": 0.6, "n": 0.7},
        observation_text="I wake up at 6am naturally every morning",
        observation_source="test",
    )

    # Verify Why-Card was created
    assert result["status"] == "ok"
    assert "why_card_id" in result
    assert result["why_card_id"] is not None
    assert result["why_card_id"].startswith("wc_")

    # Load graph and verify edge has why_card_id
    storage = FileGraphStorage(tmp_path)
    graph = storage.load_user_graph("whycard_test_user")

    edges = [e for e in graph.edges if e.edge_type == "evidence_for"]
    assert len(edges) == 1

    edge = edges[0]
    assert edge.why_card_id is not None
    assert edge.why_card_id == result["why_card_id"]


def test_why_card_storage_and_retrieval(tmp_path, monkeypatch):
    """
    AC2: Why-Card can be stored and retrieved with full 3-part template.
    """
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    # Promote a trait
    result = on_trait_promotion(
        user_id="whycard_retrieval_test",
        trait_id="PaDNA.EyeDNA.IrisColor",
        value={"enum": "blue"},
        rr_score=850.0,
        ucn={"u": 0.2, "c": 0.8, "n": 0.5},
        observation_text="My eyes are blue",
        observation_source="photo",
    )

    why_card_id = result["why_card_id"]

    # Retrieve Why-Card from storage
    storage = FileGraphStorage(tmp_path)
    card = storage.get_why_card_by_id("whycard_retrieval_test", why_card_id)

    # Verify structure (AC2: 3-part template)
    assert card is not None
    assert card.id == why_card_id
    assert card.user_id == "whycard_retrieval_test"
    assert card.trait_id == "PaDNA.EyeDNA.IrisColor"

    # Verify 3-part template
    assert card.what  # What was observed
    assert card.why   # Why it was promoted
    assert card.next  # What would increase confidence

    # Verify metrics (AC2: includes RR, UCN)
    assert card.rr == 850.0
    assert card.ucn == {"u": 0.2, "c": 0.8, "n": 0.5}

    # Verify evidence provenance
    assert len(card.evidence_node_ids) == 1


def test_why_card_template_quality(tmp_path, monkeypatch):
    """
    Test that Why-Card templates produce sensible output.
    """
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    # Promote with high RR score
    result = on_trait_promotion(
        user_id="template_test",
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=750.0,
        ucn={"u": 0.25, "c": 0.75, "n": 0.6},
        observation_text="I always wake up at 5:30am without an alarm",
        observation_source="chat",
    )

    storage = FileGraphStorage(tmp_path)
    card = storage.get_why_card_by_id("template_test", result["why_card_id"])

    # Check template quality
    assert "You said:" in card.what or "mentioned" in card.what.lower()
    assert "Chronotype" in card.why or "chronotype" in card.why.lower()
    assert str(750) in card.why or "strong" in card.why.lower()  # Should mention signal strength
    assert "confidence" in card.next.lower() or "increase" in card.next.lower()


def test_multiple_why_cards_per_user(tmp_path, monkeypatch):
    """
    Test that users can have multiple Why-Cards (one per trait promotion).
    """
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    user_id = "multi_whycard_user"

    # Promote first trait
    result1 = on_trait_promotion(
        user_id=user_id,
        trait_id="PaDNA.Chronotype",
        value="Morning Lark",
        rr_score=700.0,
        ucn={"u": 0.3, "c": 0.6, "n": 0.5},
        observation_text="I wake up early",
        observation_source="chat",
    )

    # Promote second trait
    result2 = on_trait_promotion(
        user_id=user_id,
        trait_id="BehaviorDNA.Exercise.Frequency",
        value={"range": {"min": 3, "max": 5}},
        rr_score=600.0,
        ucn={"u": 0.4, "c": 0.5, "n": 0.6},
        observation_text="I exercise 3-5 times per week",
        observation_source="chat",
    )

    # Load all Why-Cards
    storage = FileGraphStorage(tmp_path)
    all_cards = storage.load_why_cards(user_id)

    assert len(all_cards) == 2
    assert result1["why_card_id"] in [c.id for c in all_cards]
    assert result2["why_card_id"] in [c.id for c in all_cards]

    # Filter by trait_id
    chrono_cards = storage.load_why_cards(user_id, trait_id="PaDNA.Chronotype")
    assert len(chrono_cards) == 1
    assert chrono_cards[0].trait_id == "PaDNA.Chronotype"


def test_why_card_persists_after_restart(tmp_path, monkeypatch):
    """
    Test that Why-Cards persist to JSONL and survive restart.
    """
    def mock_get_storage():
        return FileGraphStorage(tmp_path)

    monkeypatch.setattr("ReDNACoreDemo.core.graph.belief.get_graph_storage", mock_get_storage)

    # Create Why-Card
    result = on_trait_promotion(
        user_id="persist_test",
        trait_id="PaDNA.Height",
        value={"int": 175},
        rr_score=900.0,
        ucn={"u": 0.1, "c": 0.9, "n": 0.8},
        observation_text="I am 175cm tall",
        observation_source="onboarding",
    )

    why_card_id = result["why_card_id"]

    # Verify file exists
    why_cards_path = tmp_path / "users" / "persist_test" / "why_cards.jsonl"
    assert why_cards_path.exists()

    # Simulate restart: create NEW storage instance
    fresh_storage = FileGraphStorage(tmp_path)

    # Load Why-Card after "restart"
    card = fresh_storage.get_why_card_by_id("persist_test", why_card_id)

    assert card is not None
    assert card.id == why_card_id
    assert card.trait_id == "PaDNA.Height"
    assert card.rr == 900.0
