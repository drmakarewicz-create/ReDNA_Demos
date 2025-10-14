"""
Test suite for Narrator Mode (Benchmark 4.A2)

Tests transparent reasoning traces for HC decisions:
- Coach switches, tone shifts, curiosity triggers, Codex actions
- API endpoints, filtering, export
- Performance requirements
"""

import json
import pytest
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from ReDNACoreDemo.core.hc_narrator import (
    NarratorEngine,
    NarratorTrace,
    get_narrator,
    TRACE_FILE,
)


@pytest.fixture
def temp_trace_file(tmp_path):
    """Create a temporary trace file for testing."""
    trace_file = tmp_path / "narrator_traces.jsonl"
    return trace_file


@pytest.fixture
def narrator(temp_trace_file):
    """Create narrator engine with temp file."""
    return NarratorEngine(trace_file=temp_trace_file)


@pytest.fixture
def sample_traces(narrator):
    """Create sample traces for testing."""
    traces = []

    # Coach switch trace
    trace1 = narrator.record_coach_switch(
        user_id="TEST",
        from_coach="head_coach",
        to_coach="career_coach",
        reasoning_factors=[
            "SkillDNA curiosity priority 0.87",
            "Career Coach historically >80% positive sentiment",
        ],
        confidence=0.82,
        context_version=42,
        session_id="session_1"
    )
    traces.append(trace1)

    # Tone shift trace
    trace2 = narrator.record_tone_shift(
        user_id="TEST",
        tone_change="More encouraging",
        reasoning=["User expressed frustration", "Confidence boost recommended"],
        confidence=0.75,
        context_version=43,
        session_id="session_1"
    )
    traces.append(trace2)

    # Curiosity trigger
    trace3 = narrator.record_curiosity_trigger(
        user_id="TEST",
        trait_container="SkillDNA.Technical_Skills.Programming",
        priority=0.90,
        reasoning=["Gap detected in programming skills", "User mentioned coding interest"],
        confidence=0.88,
        context_version=44,
        session_id="session_1"
    )
    traces.append(trace3)

    # Codex action
    trace4 = narrator.record_codex_action(
        user_id="TEST",
        action="Propose trait refinement for Empathy",
        reasoning=["Low confidence in Empathy (0.45)", "Multiple conflicting signals"],
        confidence=0.79,
        impact="high",
        context_version=45,
        session_id="session_2"
    )
    traces.append(trace4)

    # Delegation
    trace5 = narrator.record_delegation_decision(
        user_id="TEST",
        target_coach="relationship_coach",
        reasoning=["User explicitly asked about dating", "Relationship Coach best fit"],
        confidence=0.92,
        context_version=46,
        session_id="session_2"
    )
    traces.append(trace5)

    return traces


class TestNarratorEngine:
    """Test narrator engine core functionality."""

    def test_record_trace(self, narrator):
        """Test basic trace recording."""
        trace = narrator.record_trace(
            user_id="TEST",
            decision="Test decision",
            reasoning=["Reason 1", "Reason 2"],
            confidence=0.85,
            impact="medium",
            context_version=1,
            session_id="test_session"
        )

        assert isinstance(trace, NarratorTrace)
        assert trace.user_id == "TEST"
        assert trace.decision == "Test decision"
        assert len(trace.reasoning) == 2
        assert trace.confidence == 0.85
        assert trace.impact == "medium"
        assert trace.context_version == 1
        assert trace.session_id == "test_session"

    def test_record_coach_switch(self, narrator):
        """Test coach switch trace recording."""
        trace = narrator.record_coach_switch(
            user_id="TEST",
            from_coach="head_coach",
            to_coach="photo_coach",
            reasoning_factors=["User mentioned appearance", "Photo Coach available"],
            confidence=0.80,
            context_version=10
        )

        assert trace.decision == "Switch from head_coach to photo_coach"
        assert trace.metadata["type"] == "coach_switch"
        assert trace.metadata["from_coach"] == "head_coach"
        assert trace.metadata["to_coach"] == "photo_coach"
        assert trace.impact == "high"

    def test_record_tone_shift(self, narrator):
        """Test tone shift trace recording."""
        trace = narrator.record_tone_shift(
            user_id="TEST",
            tone_change="More empathetic",
            reasoning=["User seems distressed", "Empathy increase recommended"],
            confidence=0.77,
            context_version=15
        )

        assert "Tone shift" in trace.decision
        assert trace.metadata["type"] == "tone_shift"
        assert trace.impact == "medium"

    def test_record_curiosity_trigger(self, narrator):
        """Test curiosity trigger trace recording."""
        trace = narrator.record_curiosity_trigger(
            user_id="TEST",
            trait_container="RelationshipDNA.Communication.Active_Listening",
            priority=0.85,
            reasoning=["Low confidence in Active_Listening", "Recent conversation gap"],
            confidence=0.83,
            context_version=20
        )

        assert "curiosity" in trace.decision.lower()
        assert trace.metadata["type"] == "curiosity_trigger"
        assert trace.metadata["trait_container"] == "RelationshipDNA.Communication.Active_Listening"
        assert trace.metadata["priority"] == 0.85

    def test_record_codex_action(self, narrator):
        """Test Codex action trace recording."""
        trace = narrator.record_codex_action(
            user_id="TEST",
            action="Generate refinement proposal",
            reasoning=["Multiple conflicts detected", "User approved refinement mode"],
            confidence=0.81,
            impact="high",
            context_version=25
        )

        assert "Codex action" in trace.decision
        assert trace.metadata["type"] == "codex_action"
        assert trace.impact == "high"

    def test_get_traces(self, narrator, sample_traces):
        """Test retrieving traces."""
        traces = narrator.get_traces(user_id="TEST", limit=10)

        assert len(traces) == 5
        # Should be newest first
        assert traces[0]["decision"].startswith("Delegate")

    def test_filter_by_decision_type(self, narrator, sample_traces):
        """Test filtering by decision type."""
        # Filter for coach switches only
        traces = narrator.get_traces(
            user_id="TEST",
            decision_type="coach_switch",
            limit=10
        )

        assert len(traces) == 1
        assert traces[0]["metadata"]["type"] == "coach_switch"

    def test_filter_by_session(self, narrator, sample_traces):
        """Test filtering by session ID."""
        traces = narrator.get_traces(
            user_id="TEST",
            session_id="session_1",
            limit=10
        )

        assert len(traces) == 3
        for trace in traces:
            assert trace["session_id"] == "session_1"

    def test_filter_by_confidence(self, narrator, sample_traces):
        """Test filtering by minimum confidence."""
        traces = narrator.get_traces(
            user_id="TEST",
            min_confidence=0.85,
            limit=10
        )

        # Should get traces with confidence >= 0.85
        assert all(t["confidence"] >= 0.85 for t in traces)

    def test_build_narrative(self, narrator, sample_traces):
        """Test building narrative from traces."""
        narrative = narrator.build_narrative(user_id="TEST", limit=10)

        assert narrative["user_id"] == "TEST"
        assert narrative["total_traces"] == 5
        assert narrative["session_count"] == 2
        assert "session_1" in narrative["sessions"]
        assert "session_2" in narrative["sessions"]
        assert len(narrative["sessions"]["session_1"]) == 3
        assert len(narrative["sessions"]["session_2"]) == 2
        assert narrative["avg_confidence"] > 0
        assert "coach_switch" in narrative["decision_types"]

    def test_export_json(self, narrator, sample_traces):
        """Test JSON export."""
        export = narrator.export_narrative(
            user_id="TEST",
            format="json",
            limit=10
        )

        data = json.loads(export)
        assert data["user_id"] == "TEST"
        assert data["total_traces"] == 5
        assert "sessions" in data

    def test_export_markdown(self, narrator, sample_traces):
        """Test Markdown export."""
        export = narrator.export_narrative(
            user_id="TEST",
            format="markdown",
            limit=10
        )

        assert "# Narrator Timeline" in export
        assert "TEST" in export
        assert "## Decision Types" in export
        assert "## Timeline" in export
        assert "Session:" in export

    def test_trace_persistence(self, narrator):
        """Test that traces are persisted to file."""
        narrator.record_trace(
            user_id="TEST",
            decision="Persistent trace",
            reasoning=["Test persistence"],
            confidence=0.90,
            impact="low",
            context_version=100
        )

        # Create new narrator instance with same file
        narrator2 = NarratorEngine(trace_file=narrator.trace_file)
        traces = narrator2.get_traces(user_id="TEST", limit=10)

        assert any(t["decision"] == "Persistent trace" for t in traces)

    def test_invalid_trace_lines(self, narrator, temp_trace_file):
        """Test handling of invalid trace lines."""
        # Write some invalid JSON
        with open(temp_trace_file, "w") as f:
            f.write('{"valid": "trace", "user_id": "TEST"}\n')
            f.write('INVALID JSON LINE\n')
            f.write('{"another": "valid", "user_id": "TEST"}\n')

        traces = narrator.get_traces(user_id="TEST", limit=10)
        # Should skip invalid line
        assert len(traces) == 2


class TestNarratorAPI:
    """Test narrator API endpoints."""

    def test_get_narrator_traces_endpoint(self, client):
        """Test GET /coach/narrator endpoint."""
        # First create some traces
        narrator = get_narrator()
        narrator.record_coach_switch(
            user_id="TEST",
            from_coach="head_coach",
            to_coach="career_coach",
            reasoning_factors=["Test reason"],
            confidence=0.85,
            context_version=50
        )

        response = client.get("/coach/narrator?user_id=TEST&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert "traces" in data
        assert "narrative" in data
        assert "duration_ms" in data
        assert data["duration_ms"] < 200  # Performance requirement

    def test_narrator_filters(self, client):
        """Test narrator API filters."""
        narrator = get_narrator()
        narrator.record_coach_switch(
            user_id="TEST",
            from_coach="head_coach",
            to_coach="photo_coach",
            reasoning_factors=["Filter test"],
            confidence=0.90,
            context_version=60
        )

        # Filter by decision type
        response = client.get(
            "/coach/narrator?user_id=TEST&decision_type=coach_switch&limit=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True

    def test_export_json_endpoint(self, client):
        """Test GET /coach/narrator/export with JSON format."""
        response = client.get(
            "/coach/narrator/export?user_id=TEST&format=json&limit=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data

    def test_export_markdown_endpoint(self, client):
        """Test GET /coach/narrator/export with Markdown format."""
        response = client.get(
            "/coach/narrator/export?user_id=TEST&format=markdown&limit=10"
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "# Narrator Timeline" in content

    def test_annotate_trace(self, client):
        """Test POST /coach/narrator/annotate endpoint."""
        narrator = get_narrator()
        trace = narrator.record_trace(
            user_id="TEST",
            decision="Annotate test",
            reasoning=["Test annotation"],
            confidence=0.88,
            impact="low",
            context_version=70
        )

        payload = {
            "user_id": "TEST",
            "trace_ts": trace.ts,
            "annotation": "This is a test annotation",
            "annotator": "test_user"
        }

        response = client.post("/coach/narrator/annotate", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["ok"] is True
        assert data["annotation"]["annotation"] == "This is a test annotation"


class TestNarratorPerformance:
    """Test narrator performance requirements."""

    def test_api_response_time(self, client):
        """Test API returns within 200ms for 20 traces."""
        narrator = get_narrator()

        # Create 20 traces
        for i in range(20):
            narrator.record_trace(
                user_id="PERF_TEST",
                decision=f"Decision {i}",
                reasoning=[f"Reason {i}"],
                confidence=0.80,
                impact="medium",
                context_version=i
            )

        start = time.perf_counter()
        response = client.get("/coach/narrator?user_id=PERF_TEST&limit=20")
        duration_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < 200

    def test_large_trace_set_performance(self, narrator):
        """Test performance with 100+ traces."""
        # Create 150 traces
        for i in range(150):
            narrator.record_trace(
                user_id="LARGE_TEST",
                decision=f"Decision {i}",
                reasoning=[f"Reason {i}"],
                confidence=0.75,
                impact="low",
                context_version=i,
                session_id=f"session_{i // 10}"
            )

        start = time.perf_counter()
        narrative = narrator.build_narrative(user_id="LARGE_TEST", limit=100)
        duration_ms = (time.perf_counter() - start) * 1000

        assert narrative["total_traces"] == 100
        assert duration_ms < 300  # Allow 300ms for 100 traces


class TestNarratorIntegration:
    """Test narrator integration with HC decisions."""

    def test_coach_switch_creates_trace(self, client):
        """Test that coach switch creates narrator trace."""
        # Switch coach
        response = client.post(
            "/users/TEST/coach-mode",
            json={"target_mode": "career_coach"}
        )
        assert response.status_code == 200

        # Check narrator trace
        narrator_response = client.get("/coach/narrator?user_id=TEST&limit=5")
        data = narrator_response.json()

        # Should have at least one trace (may not be immediate depending on implementation)
        # This is a placeholder - actual integration depends on HC orchestrator setup

    def test_session_integrity(self, narrator):
        """Test that traces maintain session integrity."""
        # Record traces across multiple sessions
        for session_num in range(3):
            for i in range(5):
                narrator.record_trace(
                    user_id="SESSION_TEST",
                    decision=f"Session {session_num} decision {i}",
                    reasoning=[f"Reason {i}"],
                    confidence=0.80,
                    impact="medium",
                    context_version=session_num * 10 + i,
                    session_id=f"session_{session_num}"
                )

        narrative = narrator.build_narrative(user_id="SESSION_TEST", limit=20)

        # Check session grouping
        assert narrative["session_count"] == 3
        for session_id, traces in narrative["sessions"].items():
            # All traces in session should have matching session_id
            assert all(t["session_id"] == session_id for t in traces)


@pytest.fixture
def client():
    """Create test client for API testing."""
    from fastapi.testclient import TestClient
    from ReDNACoreDemo.core.api import build_app

    app = build_app()
    return TestClient(app)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
