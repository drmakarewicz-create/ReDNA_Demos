"""
Test Suite — Trait Refinement Depth Phase 1

Tests the refinement resolver's corroboration/contradiction logic,
UCN/RR calibration, API endpoints, and HC integration.

Scenarios:
1. Pure corroboration (3 consistent proposals)
2. Direct contradiction (2 opposing proposals)
3. Mixed signals (2 consistent + 1 conflicting)
4. Recency decay (older proposals weighted less)
5. Caps and gains (max_gain_per_turn enforcement)
6. API round-trip (resolve endpoint)
7. HC hook integration (post-turn refinement)
8. Performance (100 proposals in <500ms)
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List


@pytest.fixture
def temp_data_root(tmp_path):
    """Create temporary data directory structure."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    # Create users directory
    users_dir = data_root / "users" / "TEST"
    users_dir.mkdir(parents=True)

    # Create resolved.json with baseline
    resolved = {
        "python_fluency": {"value": 0.70, "ucn": 0.60, "rr": 75}
    }
    (users_dir / "resolved.json").write_text(json.dumps(resolved, indent=2))

    return data_root


@pytest.fixture
def refinement_config(tmp_path):
    """Create test refinement config."""
    config_path = tmp_path / "refinement_config.json"
    config = {
        "accept_threshold": 0.7,
        "investigate_threshold": 0.55,
        "decay_lambda": 0.015,
        "corroboration_gain": 0.15,
        "contradiction_penalty": 0.2,
        "max_gain_per_turn": 0.2,
        "source_weights": {"default": 1.0}
    }
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def test_pure_corroboration(temp_data_root, refinement_config):
    """Test 3 consistent proposals boost confidence and UCN."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Three consistent proposals
    proposals = [
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.75,
            "source": "chatdna_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        },
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.70,
            "source": "career_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        },
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.72,
            "source": "head_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        }
    ]

    outcomes = resolver.resolve_proposals("TEST", proposals)

    assert len(outcomes) == 1
    outcome = outcomes[0]

    # Check corroboration effect
    assert outcome.trait == "python_fluency"
    assert outcome.action in ("accept", "hold")  # Depends on effective_conf
    assert outcome.resolved["value"] == 0.85
    assert outcome.resolved["ucn"] > outcome.prior["ucn"]  # UCN increased
    assert outcome.proposal_summary["consistent"] == 3
    assert outcome.proposal_summary["conflicting"] == 0


def test_direct_contradiction(temp_data_root, refinement_config):
    """Test 2 opposing proposals create conflict."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Two contradicting proposals
    proposals = [
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.75,
            "source": "chatdna_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        },
        {
            "trait": "python_fluency",
            "value": 0.50,
            "confidence": 0.70,
            "source": "career_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        }
    ]

    outcomes = resolver.resolve_proposals("TEST", proposals)

    assert len(outcomes) == 1
    outcome = outcomes[0]

    # Check contradiction handling
    assert outcome.trait == "python_fluency"
    assert outcome.proposal_summary["consistent"] == 1
    assert outcome.proposal_summary["conflicting"] == 1

    # Effective confidence should be reduced by contradiction penalty
    assert outcome.proposal_summary["effective_conf"] < 0.75

    # Conflicts should be recorded
    assert len(outcome.conflicts) >= 1


def test_mixed_signals(temp_data_root, refinement_config):
    """Test 2 consistent + 1 conflicting proposal."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Mixed proposals
    proposals = [
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.75,
            "source": "chatdna_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        },
        {
            "trait": "python_fluency",
            "value": 0.85,
            "confidence": 0.72,
            "source": "head_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        },
        {
            "trait": "python_fluency",
            "value": 0.60,
            "confidence": 0.68,
            "source": "career_coach",
            "ts": datetime.now(timezone.utc).isoformat()
        }
    ]

    outcomes = resolver.resolve_proposals("TEST", proposals)

    assert len(outcomes) == 1
    outcome = outcomes[0]

    # Dominant value should be 0.85 (2 consistent votes)
    assert outcome.resolved["value"] == 0.85
    assert outcome.proposal_summary["consistent"] == 2
    assert outcome.proposal_summary["conflicting"] == 1

    # UCN should still increase but less than pure corroboration
    assert outcome.resolved["ucn"] > outcome.prior["ucn"]


def test_recency_decay(temp_data_root, refinement_config):
    """Test that older proposals are weighted less."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Proposals with different ages
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=30)).isoformat()
    recent_ts = now.isoformat()

    proposals = [
        {
            "trait": "python_fluency",
            "value": 0.50,  # Old low value
            "confidence": 0.80,
            "source": "chatdna_coach",
            "ts": old_ts
        },
        {
            "trait": "python_fluency",
            "value": 0.85,  # Recent high value
            "confidence": 0.75,
            "source": "career_coach",
            "ts": recent_ts
        }
    ]

    outcomes = resolver.resolve_proposals("TEST", proposals)

    assert len(outcomes) == 1
    outcome = outcomes[0]

    # Recent proposal should dominate due to recency decay
    assert outcome.resolved["value"] == 0.85


def test_caps_and_gains(temp_data_root, refinement_config):
    """Test max_gain_per_turn cap enforcement."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Many high-confidence proposals (would normally boost UCN significantly)
    proposals = [
        {
            "trait": "python_fluency",
            "value": 0.95,
            "confidence": 0.95,
            "source": f"coach_{i}",
            "ts": datetime.now(timezone.utc).isoformat()
        }
        for i in range(5)
    ]

    outcomes = resolver.resolve_proposals("TEST", proposals)

    assert len(outcomes) == 1
    outcome = outcomes[0]

    prior_ucn = outcome.prior["ucn"]
    resolved_ucn = outcome.resolved["ucn"]

    # UCN gain should be capped at max_gain_per_turn (0.2)
    assert resolved_ucn - prior_ucn <= 0.2 + 0.01  # +0.01 tolerance for rounding


def test_api_round_trip(temp_data_root, refinement_config, monkeypatch):
    """Test /refinement/resolve API endpoint."""
    from ReDNACoreDemo.core.api import build_app
    from fastapi.testclient import TestClient

    # Monkeypatch CORE_DATA_ROOT to use temp directory
    monkeypatch.setenv("REDNA_DATA_ROOT", str(temp_data_root))

    # Create API instance
    app = build_app()
    client = TestClient(app)

    # Prepare request payload
    payload = {
        "user_id": "TEST",
        "proposals": [
            {
                "trait": "python_fluency",
                "value": 0.85,
                "confidence": 0.75,
                "source": "chatdna_coach",
                "ts": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    # Call API
    response = client.post("/refinement/resolve", json=payload)

    assert response.status_code == 200
    result = response.json()

    assert result["ok"] is True
    assert result["user_id"] == "TEST"
    assert len(result["outcomes"]) == 1
    assert "time_ms" in result

    outcome = result["outcomes"][0]
    assert outcome["trait"] == "python_fluency"
    assert outcome["action"] in ("accept", "hold", "conflict")


def test_hc_hook_integration(temp_data_root, refinement_config, monkeypatch):
    """Test HC post-turn refinement hook."""
    from ReDNACoreDemo.core.hc_llm_agent import _run_post_turn_refinement

    # Mock response with proposed refinements
    response = {
        "content": "Great work on Python!",
        "proposed_refinements": [
            {
                "trait": "python_fluency",
                "value": 0.85,
                "confidence": 0.75,
                "source": "head_coach",
                "ts": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    meta = {"developer_mode": True}

    # Monkeypatch the data root
    monkeypatch.setenv("REDNA_DATA_ROOT", str(temp_data_root))

    # Run post-turn refinement
    _run_post_turn_refinement("TEST", response, meta)

    # Check that refinement outcomes were added to response
    assert "refinement_outcomes" in response
    assert len(response["refinement_outcomes"]) == 1

    # Check developer trace
    assert "_narrator" in response
    assert any("HC-Refinement" in line for line in response["_narrator"])


def test_performance_100_proposals(temp_data_root, refinement_config):
    """Test that 100 proposals resolve in <500ms."""
    from ReDNACoreDemo.core.refinement.refinement_resolver import create_refinement_resolver

    resolver = create_refinement_resolver(
        config_path=refinement_config,
        data_root=temp_data_root
    )

    # Generate 100 proposals across 10 traits
    proposals = []
    for i in range(100):
        trait_idx = i % 10
        proposals.append({
            "trait": f"trait_{trait_idx}",
            "value": 0.70 + (i % 20) * 0.01,
            "confidence": 0.60 + (i % 30) * 0.01,
            "source": f"coach_{i % 5}",
            "ts": datetime.now(timezone.utc).isoformat()
        })

    # Time resolution
    start = time.time()
    outcomes = resolver.resolve_proposals("TEST", proposals)
    elapsed_ms = (time.time() - start) * 1000

    # Check performance
    assert elapsed_ms < 500, f"Resolution took {elapsed_ms:.1f}ms (expected <500ms)"

    # Check correctness
    assert len(outcomes) == 10  # 10 unique traits


def test_get_conflicts_api(temp_data_root, refinement_config, monkeypatch):
    """Test GET /refinement/conflicts endpoint."""
    from ReDNACoreDemo.core.api import build_app
    from fastapi.testclient import TestClient

    # Monkeypatch CORE_DATA_ROOT to use temp directory
    monkeypatch.setenv("REDNA_DATA_ROOT", str(temp_data_root))

    app = build_app()
    client = TestClient(app)

    # First create a conflict by resolving contradicting proposals
    payload = {
        "user_id": "TEST",
        "proposals": [
            {
                "trait": "python_fluency",
                "value": 0.85,
                "confidence": 0.75,
                "source": "chatdna_coach",
                "ts": datetime.now(timezone.utc).isoformat()
            },
            {
                "trait": "python_fluency",
                "value": 0.50,
                "confidence": 0.70,
                "source": "career_coach",
                "ts": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    client.post("/refinement/resolve", json=payload)

    # Now query conflicts
    response = client.get("/refinement/conflicts?user_id=TEST&limit=10")

    assert response.status_code == 200
    result = response.json()

    assert result["ok"] is True
    assert result["user_id"] == "TEST"
    assert "conflicts" in result


def test_get_state_api(temp_data_root, refinement_config, monkeypatch):
    """Test GET /refinement/state endpoint."""
    from ReDNACoreDemo.core.api import build_app
    from fastapi.testclient import TestClient

    # Monkeypatch CORE_DATA_ROOT to use temp directory
    monkeypatch.setenv("REDNA_DATA_ROOT", str(temp_data_root))

    app = build_app()
    client = TestClient(app)

    # Query trait state
    response = client.get("/refinement/state?user_id=TEST&trait=python_fluency")

    assert response.status_code == 200
    result = response.json()

    assert result["ok"] is True
    assert result["user_id"] == "TEST"
    assert result["trait"] == "python_fluency"
    assert "state" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
