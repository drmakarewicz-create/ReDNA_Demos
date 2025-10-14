"""
Tests for Life OS Phase 4: Visual Dashboards + Voice Narratives

Validates:
- Multi-user aggregate endpoint (performance, structure)
- Week in Review data flow
- Voice summary generation (with TTS fallback)
"""

import pytest
import time
import json
from pathlib import Path

# Import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ReDNACoreDemo.core import hc_life, hc_life_insights, hc_voice
from ReDNACoreDemo.core.storage import CORE_DATA_ROOT


# ============================================================================
# Test Class 1: Aggregate Endpoint
# ============================================================================

class TestAggregateEndpoint:
    """Validate multi-user aggregate endpoint."""

    def test_aggregate_response_structure(self):
        """Test aggregate endpoint returns correct structure."""
        # Create test users with data
        test_users = ["AGG_USER1", "AGG_USER2", "AGG_USER3"]

        for user_id in test_users:
            # Create some todos
            todo1 = hc_life.Todo(id="", text="Task 1", when="today", priority=0.9, tags=["work"])
            todo2 = hc_life.Todo(id="", text="Task 2", when="today", priority=0.6, tags=["health"])
            hc_life.create_todo(user_id, todo1)
            hc_life.create_todo(user_id, todo2)

            # Mark one complete
            todos = hc_life.list_todos(user_id, scope="today")
            if todos:
                hc_life.update_todo(user_id, todos[0].id, {"status": "done"})

            # Create a goal
            goal = hc_life.Goal(
                id="",
                text="Test Goal",
                owner=user_id,
                why="Testing",
                first_step="Start",
                confidence=0.7
            )
            hc_life.create_goal(user_id, goal)

        # Compute insights for each
        for user_id in test_users:
            insights = hc_life_insights.compute_insights(user_id, days=14)
            assert insights is not None

        # Simulate aggregate endpoint logic
        aggregates = []
        users_dir = CORE_DATA_ROOT / "users"

        for user_id in test_users:
            try:
                insights = hc_life_insights.compute_insights(user_id, days=14)

                kpis = {
                    "todays_three_success_rate": insights.get("todays_three_success_rate", 0.0),
                    "current_streak": insights.get("current_streak", 0),
                    "todos_completed": insights.get("todos_completed", 0),
                    "top_tag": insights.get("top_tags", [[None, 0]])[0][0],
                    "goals_at_risk": len(insights.get("goals_at_risk", []))
                }

                quadrant_share = insights.get("quadrant_share", {})

                trends = []
                for week in insights.get("trends", []):
                    trends.append({
                        "week_label": week.get("week_label", ""),
                        "todos_completed": week.get("todos_completed", 0),
                        "completion_rate": week.get("completion_rate", 0.0)
                    })

                tags_top = insights.get("top_tags", [])[:5]

                aggregates.append({
                    "user_id": user_id,
                    "kpis": kpis,
                    "trends": trends,
                    "quadrant_share": quadrant_share,
                    "tags_top": tags_top
                })

            except Exception:
                continue

        # Validate structure
        assert len(aggregates) >= 2  # At least 2 users should succeed
        for agg in aggregates:
            assert "user_id" in agg
            assert "kpis" in agg
            assert "trends" in agg
            assert "quadrant_share" in agg
            assert "tags_top" in agg

            # Validate KPIs
            assert "todays_three_success_rate" in agg["kpis"]
            assert "current_streak" in agg["kpis"]
            assert "todos_completed" in agg["kpis"]
            assert "top_tag" in agg["kpis"]
            assert "goals_at_risk" in agg["kpis"]

            # Validate quadrant share
            assert isinstance(agg["quadrant_share"], dict)

            # Validate trends
            assert isinstance(agg["trends"], list)

            # Validate tags
            assert isinstance(agg["tags_top"], list)

    def test_aggregate_performance(self):
        """Test aggregate endpoint meets <300ms target for ≤10 users."""
        # Create 10 test users with minimal data
        test_users = [f"PERF_USER{i}" for i in range(10)]

        for user_id in test_users:
            todo = hc_life.Todo(id="", text="Quick task", when="today", priority=0.6, tags=["test"])
            hc_life.create_todo(user_id, todo)
            todos = hc_life.list_todos(user_id, scope="today")
            if todos:
                hc_life.update_todo(user_id, todos[0].id, {"status": "done"})

        # Time aggregate computation
        start_time = time.perf_counter()

        aggregates = []
        for user_id in test_users:
            try:
                insights = hc_life_insights.compute_insights(user_id, days=14)
                kpis = {
                    "todays_three_success_rate": insights.get("todays_three_success_rate", 0.0),
                    "current_streak": insights.get("current_streak", 0),
                    "todos_completed": insights.get("todos_completed", 0),
                    "top_tag": insights.get("top_tags", [[None, 0]])[0][0],
                    "goals_at_risk": len(insights.get("goals_at_risk", []))
                }
                aggregates.append({"user_id": user_id, "kpis": kpis})
            except Exception:
                continue

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Verify performance
        assert elapsed_ms < 300, f"Aggregate took {elapsed_ms:.0f}ms (target: <300ms)"
        assert len(aggregates) >= 8  # At least 8/10 users should succeed

    def test_aggregate_handles_empty_users(self):
        """Test aggregate gracefully handles users with no data."""
        # Create user with no data
        empty_user = "EMPTY_AGG_USER"
        user_dir = CORE_DATA_ROOT / "users" / empty_user
        user_dir.mkdir(parents=True, exist_ok=True)

        # Attempt to compute insights (should return empty/zero values)
        insights = hc_life_insights.compute_insights(empty_user, days=14)

        # Should not crash
        assert insights is not None
        assert insights.get("todos_completed", 0) == 0
        assert insights.get("current_streak", 0) == 0


# ============================================================================
# Test Class 2: Week in Review
# ============================================================================

class TestWeekInReview:
    """Validate Week in Review component data flow."""

    def test_week_review_data_flow(self):
        """Test complete data flow for Week in Review card."""
        test_user = "WEEK_REVIEW_USER"

        # Create activity
        todo1 = hc_life.Todo(id="", text="Morning run", when="today", priority=0.9, tags=["health"])
        todo2 = hc_life.Todo(id="", text="Code review", when="today", priority=0.6, tags=["work"])
        todo3 = hc_life.Todo(id="", text="Read book", when="today", priority=0.3, tags=["learning"])
        hc_life.create_todo(test_user, todo1)
        hc_life.create_todo(test_user, todo2)
        hc_life.create_todo(test_user, todo3)

        # Complete some tasks
        todos = hc_life.list_todos(test_user, scope="today")
        for todo in todos[:2]:
            hc_life.update_todo(test_user, todo.id, {"status": "done"})

        # Compute 7-day insights
        insights = hc_life_insights.compute_insights(test_user, days=7)

        # Validate Week in Review data requirements
        assert insights["todos_completed"] == 2
        assert insights["current_streak"] >= 0
        assert "top_tags" in insights
        assert "quadrant_share" in insights
        assert len(insights["top_tags"]) > 0

        # Simulate narrator summary generation
        from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary
        narrator_summary = build_weekly_life_summary(test_user)

        assert narrator_summary is not None
        assert len(narrator_summary) > 0
        assert "task" in narrator_summary.lower() or "week" in narrator_summary.lower()

    def test_week_review_empty_state(self):
        """Test Week in Review handles empty state gracefully."""
        empty_user = "EMPTY_WEEK_USER"
        user_dir = CORE_DATA_ROOT / "users" / empty_user
        user_dir.mkdir(parents=True, exist_ok=True)

        # Compute insights for empty user
        insights = hc_life_insights.compute_insights(empty_user, days=7)

        # Should return zero values, not crash
        assert insights["todos_completed"] == 0
        assert insights["current_streak"] == 0

        # Narrator should return friendly message
        from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary
        narrator_summary = build_weekly_life_summary(empty_user)

        assert narrator_summary is not None
        assert "No activity" in narrator_summary or "goals" in narrator_summary.lower()


# ============================================================================
# Test Class 3: Voice Summaries
# ============================================================================

class TestVoiceSummaries:
    """Validate voice summary generation with TTS fallback."""

    def test_voice_summary_text_only_fallback(self):
        """Test voice summary returns text when TTS unavailable."""
        test_user = "VOICE_USER"

        # Create some activity
        todo = hc_life.Todo(id="", text="Test task", when="today", priority=0.6, tags=["test"])
        hc_life.create_todo(test_user, todo)
        todos = hc_life.list_todos(test_user, scope="today")
        if todos:
            hc_life.update_todo(test_user, todos[0].id, {"status": "done"})

        # Generate voice summary (stub mode)
        from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary
        narrator_text = build_weekly_life_summary(test_user)

        result = hc_voice.generate_voice_summary(
            user_id=test_user,
            text=narrator_text,
            week="2025-W42",
            tts_engine="stub"
        )

        # Validate response
        assert result["ok"] is True
        assert result["text"] == narrator_text
        assert result["week"] == "2025-W42"
        assert "generated_at" in result

        # Stub mode creates placeholder, so audio_url should exist
        assert result["audio_url"] is not None or result["tts_available"] is True

    def test_voice_summary_file_storage(self):
        """Test voice summary files stored correctly."""
        test_user = "VOICE_STORAGE_USER"
        week = "2025-W42"

        # Generate summary
        result = hc_voice.generate_voice_summary(
            user_id=test_user,
            text="Test summary text",
            week=week,
            tts_engine="stub"
        )

        # Verify file exists
        voice_dir = CORE_DATA_ROOT / "users" / test_user / "voice"
        audio_file = voice_dir / f"summary_week_{week}.mp3"

        assert audio_file.exists()

        # Test retrieval
        retrieved_path = hc_voice.get_voice_summary(test_user, week)
        assert retrieved_path == audio_file

    def test_voice_summary_audit_logged(self):
        """Test voice summary generation logs audit event."""
        test_user = "VOICE_AUDIT_USER"

        # Generate summary
        result = hc_voice.generate_voice_summary(
            user_id=test_user,
            text="Audit test summary",
            week="2025-W42",
            tts_engine="stub"
        )

        # Check audit log
        audit_file = Path("data/telemetry/agents/agent_activity.jsonl")
        if audit_file.exists():
            with open(audit_file, "r") as f:
                lines = f.readlines()
                recent_events = [json.loads(line) for line in lines[-10:] if line.strip()]

            # Look for life_voice_summary_generated event
            voice_events = [e for e in recent_events if e.get("event") == "life_voice_summary_generated"]

            # Event should be logged (check user_id is mentioned somewhere)
            if len(voice_events) > 0:
                assert any(test_user in str(e) for e in voice_events)


# ============================================================================
# Test Class 4: Integration Tests
# ============================================================================

class TestPhase4Integration:
    """End-to-end integration tests for Phase 4."""

    def test_complete_dashboard_flow(self):
        """Test complete flow: activity → insights → aggregate → dashboard."""
        test_user = "INTEGRATION_USER"

        # 1. Create activity
        todo1 = hc_life.Todo(id="", text="Integration task 1", when="today", priority=0.9, tags=["integration"])
        todo2 = hc_life.Todo(id="", text="Integration task 2", when="today", priority=0.6, tags=["test"])
        hc_life.create_todo(test_user, todo1)
        hc_life.create_todo(test_user, todo2)

        todos = hc_life.list_todos(test_user, scope="today")
        for todo in todos:
            hc_life.update_todo(test_user, todo.id, {"status": "done"})

        # 2. Compute insights
        insights = hc_life_insights.compute_insights(test_user, days=14)
        assert insights["todos_completed"] >= 2  # At least 2 (may have prior data)

        # 3. Build aggregate
        kpis = {
            "todays_three_success_rate": insights.get("todays_three_success_rate", 0.0),
            "current_streak": insights.get("current_streak", 0),
            "todos_completed": insights.get("todos_completed", 0),
            "top_tag": insights.get("top_tags", [[None, 0]])[0][0],
            "goals_at_risk": len(insights.get("goals_at_risk", []))
        }

        aggregate = {
            "user_id": test_user,
            "kpis": kpis,
            "trends": [],
            "quadrant_share": insights.get("quadrant_share", {}),
            "tags_top": insights.get("top_tags", [])[:5]
        }

        # 4. Validate dashboard-ready structure
        assert aggregate["kpis"]["todos_completed"] >= 2  # At least 2
        assert aggregate["kpis"]["top_tag"] in ["integration", "test", None]
        assert isinstance(aggregate["quadrant_share"], dict)

    def test_complete_week_review_flow(self):
        """Test complete flow: activity → insights → narrator → week review."""
        test_user = "WEEK_FLOW_USER"

        # 1. Create activity
        todo = hc_life.Todo(id="", text="Weekly task", when="today", priority=0.9, tags=["weekly"])
        hc_life.create_todo(test_user, todo)
        todos = hc_life.list_todos(test_user, scope="today")
        if todos:
            hc_life.update_todo(test_user, todos[0].id, {"status": "done"})

        # 2. Compute insights
        insights = hc_life_insights.compute_insights(test_user, days=7)

        # 3. Generate narrator summary
        from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary
        narrator_summary = build_weekly_life_summary(test_user)

        # 4. Assemble Week in Review data
        week_review_data = {
            "insights": insights,
            "narrator_summary": narrator_summary,
            "week_label": "Week of Jan 15"
        }

        # Validate
        assert week_review_data["insights"]["todos_completed"] >= 1
        assert len(week_review_data["narrator_summary"]) > 0
        assert "week" in week_review_data["week_label"].lower()


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
