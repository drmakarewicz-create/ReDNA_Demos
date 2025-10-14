"""
Tests for Life OS Phase 3: Insights & Analytics

Tests the insights computation engine, API endpoints, and narrator summaries.
"""

import pytest
from datetime import datetime, timedelta, timezone
from ReDNACoreDemo.core.hc_life_insights import (
    compute_insights,
    compute_trends,
    _parse_iso_date,
    _compute_streaks
)
from ReDNACoreDemo.core.hc_narrator import build_weekly_life_summary


class TestInsightsComputation:
    """Test insights computation functions."""

    def test_compute_insights_empty_data(self):
        """Test insights computation with no data."""
        insights = compute_insights("EMPTY_USER", days=14)

        assert insights['goals_total'] == 0
        assert insights['goals_active'] == 0
        assert insights['todos_completed'] == 0
        assert insights['current_streak'] == 0
        assert len(insights['top_tags']) == 0
        assert insights['window_days'] == 14
        assert 'computed_at' in insights

    def test_compute_insights_with_data(self):
        """Test insights computation with existing data."""
        insights = compute_insights("USER1", days=14)

        # Should have structure
        assert 'goals_total' in insights
        assert 'todos_completed' in insights
        assert 'quadrant_share' in insights
        assert 'current_streak' in insights
        assert 'top_tags' in insights
        assert 'goals_at_risk' in insights
        assert 'projects_at_risk' in insights

        # Quadrant share should sum to ~100% (or 0 if no data)
        quadrant_sum = sum(insights['quadrant_share'].values())
        assert 0 <= quadrant_sum <= 100.1  # Allow small floating point error

    def test_compute_insights_windows(self):
        """Test insights with different time windows."""
        insights_7d = compute_insights("USER1", days=7)
        insights_30d = compute_insights("USER1", days=30)

        assert insights_7d['window_days'] == 7
        assert insights_30d['window_days'] == 30

        # 30-day window should have >= data from 7-day window
        assert insights_30d['goals_total'] >= insights_7d['goals_total']

    def test_compute_trends_empty_data(self):
        """Test trends computation with no data."""
        trends = compute_trends("EMPTY_USER", weeks=8)

        assert trends['weeks'] == 8
        assert len(trends['data']) == 8
        assert 'start_date' in trends
        assert 'end_date' in trends
        assert 'computed_at' in trends

        # Each week should have correct structure
        for week in trends['data']:
            assert 'week_start' in week
            assert 'week_label' in week
            assert 'todos_completed' in week
            assert 'goals_progressed' in week
            assert 'avg_confidence' in week
            assert 'quadrant_share' in week

    def test_compute_trends_weekly_bins(self):
        """Test trends creates correct weekly bins."""
        trends = compute_trends("USER1", weeks=4)

        assert trends['weeks'] == 4
        assert len(trends['data']) == 4

        # Weeks should be sequential Mondays
        for i in range(len(trends['data']) - 1):
            week1 = datetime.fromisoformat(trends['data'][i]['week_start'])
            week2 = datetime.fromisoformat(trends['data'][i + 1]['week_start'])
            assert (week2 - week1).days == 7

    def test_parse_iso_date(self):
        """Test ISO date parsing utility."""
        # Standard ISO format
        dt1 = _parse_iso_date("2025-10-11T01:23:45Z")
        assert dt1.year == 2025
        assert dt1.month == 10
        assert dt1.day == 11

        # ISO format with timezone
        dt2 = _parse_iso_date("2025-10-11T01:23:45+00:00")
        assert dt2.year == 2025

        # Handle malformed gracefully
        dt3 = _parse_iso_date("")
        assert isinstance(dt3, datetime)

    def test_compute_streaks(self):
        """Test streak computation logic."""
        # This requires actual todo data
        current_streak, longest_streak, streak_days = _compute_streaks("USER1", days=30)

        assert isinstance(current_streak, int)
        assert isinstance(longest_streak, int)
        assert isinstance(streak_days, list)
        assert current_streak <= longest_streak
        assert longest_streak <= len(streak_days)


class TestInsightsAPI:
    """Test insights API endpoints."""

    def test_insights_endpoint_structure(self, client):
        """Test insights endpoint returns correct structure."""
        response = client.get("/ui/hc/life/USER1/insights?days=14")

        assert response.status_code == 200
        data = response.json()

        assert data['ok'] is True
        assert 'insights' in data
        assert 'duration_ms' in data

        insights = data['insights']
        assert 'goals_total' in insights
        assert 'todos_completed' in insights
        assert 'current_streak' in insights
        assert 'quadrant_share' in insights
        assert 'top_tags' in insights

    def test_insights_performance(self, client):
        """Test insights endpoint meets performance target."""
        response = client.get("/ui/hc/life/USER1/insights?days=14")

        assert response.status_code == 200
        data = response.json()

        # Should be < 150ms on typical data
        assert data['duration_ms'] < 150

    def test_trends_endpoint_structure(self, client):
        """Test trends endpoint returns correct structure."""
        response = client.get("/ui/hc/life/USER1/trends?weeks=8")

        assert response.status_code == 200
        data = response.json()

        assert data['ok'] is True
        assert 'trends' in data
        assert 'duration_ms' in data

        trends = data['trends']
        assert trends['weeks'] == 8
        assert len(trends['data']) == 8
        assert 'start_date' in trends
        assert 'end_date' in trends

    def test_trends_performance(self, client):
        """Test trends endpoint meets performance target."""
        response = client.get("/ui/hc/life/USER1/trends?weeks=8")

        assert response.status_code == 200
        data = response.json()

        # Should be < 300ms on typical data
        assert data['duration_ms'] < 300

    def test_insights_window_validation(self, client):
        """Test insights endpoint validates window parameter."""
        # Valid windows
        response = client.get("/ui/hc/life/USER1/insights?days=7")
        assert response.status_code == 200

        response = client.get("/ui/hc/life/USER1/insights?days=90")
        assert response.status_code == 200

        # Invalid window (too large) - should be rejected
        response = client.get("/ui/hc/life/USER1/insights?days=365")
        assert response.status_code == 422

    def test_trends_week_validation(self, client):
        """Test trends endpoint validates weeks parameter."""
        # Valid weeks
        response = client.get("/ui/hc/life/USER1/trends?weeks=4")
        assert response.status_code == 200

        response = client.get("/ui/hc/life/USER1/trends?weeks=52")
        assert response.status_code == 200

        # Invalid weeks (too large) - should be rejected
        response = client.get("/ui/hc/life/USER1/trends?weeks=100")
        assert response.status_code == 422

    def test_recompute_endpoint(self, client):
        """Test insights recompute endpoint."""
        response = client.post("/ui/hc/life/USER1/insights/recompute")

        assert response.status_code == 200
        data = response.json()

        assert data['ok'] is True
        assert data['recomputed'] is True
        assert 'insights' in data
        assert 'duration_ms' in data


class TestNarratorSummary:
    """Test narrator weekly summary."""

    def test_weekly_summary_generation(self):
        """Test weekly summary generation."""
        summary = build_weekly_life_summary("USER1")

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_weekly_summary_empty_data(self):
        """Test weekly summary with no data."""
        summary = build_weekly_life_summary("EMPTY_USER")

        assert isinstance(summary, str)
        assert "No activity" in summary or "week ahead" in summary

    def test_weekly_summary_creates_trace(self):
        """Test weekly summary creates narrator trace."""
        from ReDNACoreDemo.core.hc_narrator import get_narrator

        narrator = get_narrator()
        initial_count = len(narrator.get_recent_traces("TEST_NARRATOR", limit=100))

        # Generate summary
        build_weekly_life_summary("TEST_NARRATOR")

        # Should have created new trace
        new_count = len(narrator.get_recent_traces("TEST_NARRATOR", limit=100))
        assert new_count > initial_count


class TestEmptyStateBehavior:
    """Test empty state handling."""

    def test_insights_safe_with_no_goals(self):
        """Test insights don't crash with no goals."""
        insights = compute_insights("EMPTY_USER", days=14)

        assert insights['goals_total'] == 0
        assert insights['goal_completion_rate'] == 0.0
        assert insights['goal_velocity'] == 0.0
        assert len(insights['goals_at_risk']) == 0

    def test_insights_safe_with_no_todos(self):
        """Test insights don't crash with no todos."""
        insights = compute_insights("EMPTY_USER", days=14)

        assert insights['todos_completed'] == 0
        assert insights['todos_completion_rate'] == 0.0
        assert insights['current_streak'] == 0
        assert insights['longest_streak'] == 0

    def test_trends_safe_with_no_data(self):
        """Test trends don't crash with no data."""
        trends = compute_trends("EMPTY_USER", weeks=8)

        assert len(trends['data']) == 8
        for week in trends['data']:
            assert week['todos_completed'] == 0
            assert week['goals_progressed'] == 0


class TestQuadrantMath:
    """Test quadrant distribution calculations."""

    def test_quadrant_share_sums_correctly(self):
        """Test quadrant percentages sum to 100% or 0%."""
        insights = compute_insights("USER1", days=14)

        quadrant_sum = sum(insights['quadrant_share'].values())
        # Should be 0 (no data) or 100 (with data), allowing floating point error
        assert quadrant_sum < 0.1 or (99.9 <= quadrant_sum <= 100.1)

    def test_quadrant_all_keys_present(self):
        """Test all quadrant keys are present."""
        insights = compute_insights("USER1", days=14)

        assert 'important_urgent' in insights['quadrant_share']
        assert 'important_not_urgent' in insights['quadrant_share']
        assert 'not_important_urgent' in insights['quadrant_share']
        assert 'neither' in insights['quadrant_share']


class TestStreakLogic:
    """Test streak computation logic."""

    def test_current_streak_never_exceeds_longest(self):
        """Test current streak is always <= longest streak."""
        insights = compute_insights("USER1", days=30)

        assert insights['current_streak'] <= insights['longest_streak']

    def test_streak_days_match_counts(self):
        """Test streak days list matches computed counts."""
        insights = compute_insights("USER1", days=30)

        # If there's a longest streak, there should be streak days
        if insights['longest_streak'] > 0:
            assert len(insights['streak_days']) >= insights['longest_streak']


@pytest.fixture
def client():
    """Create test client for API tests."""
    from ReDNACoreDemo.core.api import app
    from fastapi.testclient import TestClient

    return TestClient(app)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
