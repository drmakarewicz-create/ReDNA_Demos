"""
Tests for Shape Harmonizer (Phase 9).

Verifies that incoming payloads are normalized to prevent field/namespace drift.
Tests dry-run mode (no mutations) and mutate mode (canonical normalization).
"""

import pytest
import os
from pathlib import Path
from copy import deepcopy

from ReDNACoreDemo.core.graph.shape_harmonizer import (
    normalize,
    normalize_evidence_batch,
    is_harmonizer_enabled,
    is_dryrun_mode,
    should_mutate,
)


# ============================================================================
# UNIT TESTS - normalize() function
# ============================================================================


def test_evidence_field_aliasing():
    """Test that traitId is aliased to trait_id."""
    payload = {
        "traitId": "PaDNA.Chronotype",
        "value": {"enum": "morning"}
    }

    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    assert "trait_id" in normalized
    assert normalized["trait_id"] == "PaDNA.Chronotype"
    assert "traitId" not in normalized
    assert "traitId→trait_id" in audit["changed_keys"]
    assert "traitId" in audit["alias_hits"]


def test_namespace_normalization():
    """Test that BehaviorDNA.Sleep.Chronotype is normalized to PaDNA.Chronotype."""
    payload = {
        "trait_id": "BehaviorDNA.Sleep.Chronotype",
        "value": {"enum": "morning"}
    }

    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    assert normalized["trait_id"] == "PaDNA.Chronotype"
    assert audit["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"


def test_combined_aliasing_and_namespace():
    """Test both field aliasing and namespace normalization together."""
    payload = {
        "traitId": "BehaviorDNA.Sleep.Chronotype",
        "value": {"enum": "morning"}
    }

    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    # Field aliasing
    assert "trait_id" in normalized
    assert "traitId" not in normalized

    # Namespace normalization
    assert normalized["trait_id"] == "PaDNA.Chronotype"

    # Audit
    assert "traitId→trait_id" in audit["changed_keys"]
    assert audit["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"


def test_dry_run_no_mutation():
    """AC1: Dry-run mode does not mutate payloads but records proposed changes."""
    payload = {
        "traitId": "BehaviorDNA.Sleep.Chronotype",
        "value": {"enum": "morning"}
    }
    original = deepcopy(payload)

    normalized, audit = normalize(payload, "evidence", mutate=False, audit=True)

    # Payload unchanged
    assert normalized == original
    assert "traitId" in normalized  # Still has old key
    assert normalized["traitId"] == "BehaviorDNA.Sleep.Chronotype"  # Unchanged namespace

    # But audit records what would change
    assert "traitId→trait_id" in audit["changed_keys"]
    assert audit["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"


def test_default_filling():
    """Test that missing timestamp and provenance.source are filled."""
    payload = {
        "trait_id": "PaDNA.Chronotype",
        "value": {"enum": "morning"}
    }

    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    # Defaults added
    assert "timestamp" in normalized
    assert "provenance" in normalized
    assert normalized["provenance"]["source"] == "unknown"

    # Audit records defaults
    assert "timestamp" in audit["defaults_added"]
    assert "provenance.source" in audit["defaults_added"]


def test_edge_field_aliasing():
    """Test edge-specific field aliases."""
    payload = {
        "source": "node1",  # Should become "from"
        "target": "node2",  # Should become "to"
        "type": "correlates_with"  # Should become "edge_type"
    }

    normalized, audit = normalize(payload, "edge", mutate=True, audit=True)

    assert normalized["from"] == "node1"
    assert normalized["to"] == "node2"
    assert normalized["edge_type"] == "correlates_with"

    assert "source" not in normalized
    assert "target" not in normalized
    assert "type" not in normalized

    assert "source→from" in audit["changed_keys"]
    assert "target→to" in audit["changed_keys"]
    assert "type→edge_type" in audit["changed_keys"]


def test_node_field_aliasing():
    """Test node-specific field aliases."""
    payload = {
        "kind": "trait_belief",  # Should become "node_type"
        "traitId": "PaDNA.Chronotype"  # Should become "trait_id"
    }

    normalized, audit = normalize(payload, "node", mutate=True, audit=True)

    assert normalized["node_type"] == "trait_belief"
    assert normalized["trait_id"] == "PaDNA.Chronotype"

    assert "kind" not in normalized
    assert "traitId" not in normalized


def test_no_changes_needed():
    """Test payload that is already canonical (no changes)."""
    payload = {
        "trait_id": "PaDNA.Chronotype",
        "value": {"enum": "morning"},
        "timestamp": "2025-01-01T00:00:00Z",
        "provenance": {"source": "chat"}
    }

    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    # No changes
    assert normalized["trait_id"] == "PaDNA.Chronotype"
    assert audit["changed_keys"] == []
    assert audit["alias_hits"] == []
    assert audit["namespace"] is None
    assert audit["defaults_added"] == []


# ============================================================================
# BATCH TESTS
# ============================================================================


def test_batch_normalization():
    """Test normalizing a batch of evidence items."""
    items = [
        {"traitId": "BehaviorDNA.Sleep.Chronotype", "value": {"enum": "morning"}},
        {"trait_id": "PaDNA.EyeColor", "value": {"enum": "blue"}},
        {"traitId": "PaDNA.Height", "value": {"number": 175}}
    ]

    normalized, audits = normalize_evidence_batch(items, mutate=True, audit=True)

    # First item normalized
    assert normalized[0]["trait_id"] == "PaDNA.Chronotype"
    assert audits[0]["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"

    # Second item unchanged (already canonical)
    assert normalized[1]["trait_id"] == "PaDNA.EyeColor"

    # Third item field aliased
    assert normalized[2]["trait_id"] == "PaDNA.Height"
    assert "traitId→trait_id" in audits[2]["changed_keys"]


# ============================================================================
# FLAG TESTS
# ============================================================================


def test_harmonizer_enabled_flag(monkeypatch):
    """Test SHAPE_HARMONIZER flag."""
    monkeypatch.setenv("SHAPE_HARMONIZER", "on")
    assert is_harmonizer_enabled() is True

    monkeypatch.setenv("SHAPE_HARMONIZER", "off")
    assert is_harmonizer_enabled() is False

    monkeypatch.setenv("SHAPE_HARMONIZER", "true")
    assert is_harmonizer_enabled() is True


def test_dryrun_mode_flag(monkeypatch):
    """Test SHAPE_HARMONIZER_DRYRUN flag."""
    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "on")
    assert is_dryrun_mode() is True

    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "off")
    assert is_dryrun_mode() is False


def test_should_mutate_logic(monkeypatch):
    """Test that should_mutate requires both flags."""
    # Harmonizer off, dryrun on -> no mutate
    monkeypatch.setenv("SHAPE_HARMONIZER", "off")
    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "on")
    assert should_mutate() is False

    # Harmonizer on, dryrun on -> no mutate (dry-run)
    monkeypatch.setenv("SHAPE_HARMONIZER", "on")
    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "on")
    assert should_mutate() is False

    # Harmonizer on, dryrun off -> mutate
    monkeypatch.setenv("SHAPE_HARMONIZER", "on")
    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "off")
    assert should_mutate() is True

    # Harmonizer off, dryrun off -> no mutate (harmonizer disabled)
    monkeypatch.setenv("SHAPE_HARMONIZER", "off")
    monkeypatch.setenv("SHAPE_HARMONIZER_DRYRUN", "off")
    assert should_mutate() is False


# ============================================================================
# ACCEPTANCE CRITERIA TESTS
# ============================================================================


def test_ac1_dry_run_no_behavior_change():
    """
    AC1: With DRYRUN=on, ingesting differently-shaped payloads does not change behavior.
    Audit lines are written showing proposed normalizations.
    """
    # Three differently-shaped payloads
    payloads = [
        {"trait_id": "PaDNA.Chronotype", "value": {"enum": "morning"}},
        {"traitId": "BehaviorDNA.Sleep.Chronotype", "value": {"enum": "morning"}},
        {"trait_id": "PaDNA.Chronotype", "value": {"enum": "morning"}, "provenance": {"source": "chat"}}
    ]

    # Dry-run mode (mutate=False)
    results = []
    audits = []
    for p in payloads:
        normalized, audit = normalize(p, "evidence", mutate=False, audit=True)
        results.append(normalized)
        audits.append(audit)

    # Payloads unchanged
    assert results[0] == payloads[0]
    assert results[1] == payloads[1]  # traitId still there
    assert results[2] == payloads[2]

    # But audits show what would change
    assert audits[1]["changed_keys"] == ["traitId→trait_id"]
    assert audits[1]["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"


def test_ac2_mutate_mode_identical_result():
    """
    AC2: With DRYRUN=off, ingesting differently-shaped payloads results in identical
    normalized payloads (same trait_id, same structure).
    """
    # Three differently-shaped payloads representing the same trait
    payloads = [
        {"trait_id": "PaDNA.Chronotype", "value": {"enum": "morning"}},
        {"traitId": "BehaviorDNA.Sleep.Chronotype", "value": {"enum": "morning"}},
        {"trait_id": "PaDNA.Chronotype", "value": {"enum": "morning"}, "provenance": {"source": "chat"}}
    ]

    # Mutate mode
    results = []
    for p in payloads:
        normalized, _ = normalize(p, "evidence", mutate=True, audit=False)
        results.append(normalized)

    # All should have same trait_id (canonical form)
    assert results[0]["trait_id"] == "PaDNA.Chronotype"
    assert results[1]["trait_id"] == "PaDNA.Chronotype"
    assert results[2]["trait_id"] == "PaDNA.Chronotype"

    # All should have "trait_id" key (not "traitId")
    for r in results:
        assert "trait_id" in r
        assert "traitId" not in r


def test_ac3_namespace_normalization_with_aliases():
    """
    AC3: BehaviorDNA Chronotype evidence is normalized to PaDNA.Chronotype in stored ops,
    while Why-Cards/aliases continue to resolve (read-time aliasing still works).
    """
    # Ingress normalization (write-time)
    payload = {"trait_id": "BehaviorDNA.Sleep.Chronotype", "value": {"enum": "morning"}}
    normalized, audit = normalize(payload, "evidence", mutate=True, audit=True)

    # Stored as PaDNA
    assert normalized["trait_id"] == "PaDNA.Chronotype"
    assert audit["namespace"] == "BehaviorDNA.Sleep.Chronotype→PaDNA.Chronotype"

    # Read-time aliasing (from aliases.py) still works
    from ReDNACoreDemo.core.graph.aliases import get_all_aliases

    # Both forms resolve to each other
    pada_aliases = get_all_aliases("PaDNA.Chronotype")
    behavior_aliases = get_all_aliases("BehaviorDNA.Sleep.Chronotype")

    assert "BehaviorDNA.Sleep.Chronotype" in pada_aliases
    assert "PaDNA.Chronotype" in behavior_aliases
