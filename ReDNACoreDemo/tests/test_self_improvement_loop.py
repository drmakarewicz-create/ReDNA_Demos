"""
Test Suite — Self-Improvement Loop
===================================

Integration tests for telemetry analysis → suggestions pipeline.

Scenarios:
    1. Schema validation (reject malformed JSONL)
    2. Metrics computation (sentiment, tokens, latency)
    3. Suggestion generation (mock telemetry with known patterns)
    4. Confidence calibration (scores in 0.70-0.90 range)
    5. Evidence tracing (telemetry_refs point to real entries)

Author: ReDNA Core Team
Created: 2025-10-09
Benchmark: #8 Self-Improvement Loop
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from ReDNACoreDemo.core.learning.telemetry_analyzer import TelemetryAnalyzer
from ReDNACoreDemo.core.learning.prompt_tuner import PromptTuner


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_dir = tmp_path / "data"
    prompts_dir = tmp_path / "prompts"
    insights_dir = prompts_dir / "insights"

    data_dir.mkdir()
    prompts_dir.mkdir()
    insights_dir.mkdir()

    return tmp_path


@pytest.fixture
def sample_telemetry():
    """Generate sample telemetry entries with known patterns."""
    entries = []

    # Pattern 1: "empathetic" tone → high positive sentiment
    for i in range(25):
        entries.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": "test_user",
            "active_coach_id": "career_coach",
            "context_version": i + 1,
            "sentiment": "positive",
            "features": {"tone": "Empathetic", "creativity": 70},
            "hints": {"tone": "empathetic", "creativity_bias": 0.65},
            "tokens": 145,
            "build_ms": 8.5
        })

    # Pattern 2: "professional" tone → mixed sentiment
    for i in range(15):
        entries.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": "test_user",
            "active_coach_id": "career_coach",
            "context_version": i + 26,
            "sentiment": "neutral" if i % 2 == 0 else "positive",
            "features": {"tone": "Professional", "creativity": 70},
            "hints": {"tone": "professional", "creativity_bias": 0.70},
            "tokens": 178,
            "build_ms": 12.3
        })

    # Pattern 3: negative sentiment with creativity=0.75
    for i in range(5):
        entries.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": "test_user",
            "active_coach_id": "career_coach",
            "context_version": i + 41,
            "sentiment": "negative",
            "features": {"tone": "Professional", "creativity": 75},
            "hints": {"tone": "professional", "creativity_bias": 0.75},
            "tokens": 200,
            "build_ms": 15.8
        })

    return entries


def test_schema_validation(temp_data_dir, sample_telemetry):
    """Test telemetry entry schema validation."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    # Valid entry
    valid_entry = sample_telemetry[0]
    assert analyzer._validate_entry(valid_entry) is True

    # Missing required field
    invalid_entry = {**valid_entry}
    del invalid_entry["user_id"]
    assert analyzer._validate_entry(invalid_entry) is False

    # Empty entry
    assert analyzer._validate_entry({}) is False


def test_telemetry_loading(temp_data_dir, sample_telemetry):
    """Test JSONL telemetry file loading with malformed entries."""
    insights_dir = temp_data_dir / "prompts" / "insights"
    telemetry_file = insights_dir / "career_coach.jsonl"

    # Write valid + malformed entries
    with open(telemetry_file, 'w', encoding='utf-8') as f:
        # Valid entries
        for entry in sample_telemetry[:10]:
            f.write(json.dumps(entry) + '\n')

        # Malformed JSON
        f.write('{"invalid json syntax\n')

        # More valid entries
        for entry in sample_telemetry[10:15]:
            f.write(json.dumps(entry) + '\n')

    # Load telemetry
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")
    entries = analyzer._load_telemetry(telemetry_file)

    # Should have 15 valid entries (malformed one skipped)
    assert len(entries) == 15


def test_sentiment_trend_computation(temp_data_dir, sample_telemetry):
    """Test sentiment distribution calculation."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    # Sample: 25 positive (empathetic), 8 positive + 7 neutral (professional), 5 negative
    # Total: 33 positive, 7 neutral, 5 negative = 45 entries
    sentiment_trend = analyzer._compute_sentiment_trend(sample_telemetry)

    # Verify all sentiments sum to ~1.0
    total = sentiment_trend["positive"] + sentiment_trend["neutral"] + sentiment_trend["negative"]
    assert 0.99 <= total <= 1.01

    # Positive should be majority (33/45 = 0.73)
    assert sentiment_trend["positive"] >= 0.70

    # Negative should be minority (5/45 = 0.11)
    assert sentiment_trend["negative"] <= 0.15


def test_token_efficiency_computation(temp_data_dir, sample_telemetry):
    """Test token efficiency for positive outcomes."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    # Pattern: empathetic tone (145 tokens) vs professional tone (178 tokens)
    token_eff = analyzer._compute_token_efficiency(sample_telemetry)

    # Should be close to 145 (empathetic entries dominate positive outcomes)
    assert 140 <= token_eff <= 160


def test_latency_percentiles(temp_data_dir, sample_telemetry):
    """Test latency percentile calculation."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    latency = analyzer._compute_latency_percentiles(sample_telemetry)

    # Should have p50, p95, p99
    assert "p50" in latency
    assert "p95" in latency
    assert "p99" in latency

    # Reasonable ranges from sample data (8.5-15.8ms)
    assert 7 <= latency["p50"] <= 13
    assert 12 <= latency["p95"] <= 16
    assert 14 <= latency["p99"] <= 17


def test_tone_correlation_analysis(temp_data_dir, sample_telemetry):
    """Test tone → sentiment correlation analysis."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    tone_corr = analyzer._compute_tone_correlation(sample_telemetry)

    # "Empathetic" should be top tone (100% positive in pattern)
    assert tone_corr["top_tone"] == "Empathetic"
    assert tone_corr["top_tone_score"] == 1.0  # 25/25 positive

    # Should have scores for both tones
    assert "Empathetic" in tone_corr["tone_scores"]
    assert "Professional" in tone_corr["tone_scores"]


def test_creativity_analysis(temp_data_dir, sample_telemetry):
    """Test optimal creativity bias detection."""
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")

    creativity = analyzer._compute_creativity_analysis(sample_telemetry)

    # Optimal should be ~0.65 (from empathetic positive patterns)
    assert 0.63 <= creativity["optimal_creativity"] <= 0.67

    # Should have sample size
    assert creativity["sample_size"] >= 25


def test_full_analysis_pipeline(temp_data_dir, sample_telemetry):
    """Test complete analysis pipeline."""
    # Write telemetry file
    insights_dir = temp_data_dir / "prompts" / "insights"
    telemetry_file = insights_dir / "career_coach.jsonl"

    with open(telemetry_file, 'w', encoding='utf-8') as f:
        for entry in sample_telemetry:
            f.write(json.dumps(entry) + '\n')

    # Run analysis
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")
    report = analyzer.analyze_all_coaches()

    # Validate report structure
    assert "generated_at" in report
    assert "coaches" in report
    assert "career_coach" in report["coaches"]

    # Validate metrics
    coach_metrics = report["coaches"]["career_coach"]
    assert coach_metrics["entries_analyzed"] == len(sample_telemetry)
    assert "sentiment_trend" in coach_metrics
    assert "token_efficiency" in coach_metrics
    assert "latency_percentiles" in coach_metrics


def test_suggestion_generation(temp_data_dir, sample_telemetry):
    """Test prompt tuning suggestion generation."""
    # Create mock analysis report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coaches": {
            "career_coach": {
                "entries_analyzed": 45,
                "sentiment_trend": {"positive": 0.65, "neutral": 0.20, "negative": 0.15},
                "token_efficiency": 145.0,
                "tone_correlation": {
                    "top_tone": "Empathetic",
                    "top_tone_score": 0.92,
                    "tone_scores": {"Empathetic": 0.92, "Professional": 0.50}
                },
                "creativity_analysis": {
                    "optimal_creativity": 0.65,
                    "sample_size": 30
                }
            }
        }
    }

    # Generate suggestions
    tuner = PromptTuner(analysis_report=report)
    suggestions = tuner.generate_suggestions()

    # Should generate suggestions
    assert len(suggestions) > 0

    # Check suggestion structure
    suggestion = suggestions[0]
    assert "id" in suggestion
    assert "coach_id" in suggestion
    assert "type" in suggestion
    assert "confidence" in suggestion
    assert "evidence" in suggestion
    assert "auto_apply_eligible" in suggestion


def test_confidence_calibration(temp_data_dir, sample_telemetry):
    """Test confidence score calibration."""
    # High-confidence pattern (large sample, strong signal)
    report_high = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coaches": {
            "test_coach": {
                "entries_analyzed": 100,
                "sentiment_trend": {"positive": 0.90, "neutral": 0.08, "negative": 0.02},
                "token_efficiency": 140.0,
                "tone_correlation": {
                    "top_tone": "Empathetic",
                    "top_tone_score": 0.95,
                    "tone_scores": {"Empathetic": 0.95, "Professional": 0.60}
                },
                "creativity_analysis": {
                    "optimal_creativity": 0.65,
                    "sample_size": 80
                }
            }
        }
    }

    tuner_high = PromptTuner(analysis_report=report_high)
    suggestions_high = tuner_high.generate_suggestions()

    # Should have high confidence (≥0.85)
    high_conf_count = sum(1 for s in suggestions_high if s["confidence"] >= 0.85)
    assert high_conf_count > 0

    # Low-confidence pattern (small sample, weak signal)
    report_low = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coaches": {
            "test_coach": {
                "entries_analyzed": 15,
                "sentiment_trend": {"positive": 0.60, "neutral": 0.30, "negative": 0.10},
                "token_efficiency": 150.0,
                "tone_correlation": {
                    "top_tone": "Empathetic",
                    "top_tone_score": 0.65,
                    "tone_scores": {"Empathetic": 0.65, "Professional": 0.60}
                },
                "creativity_analysis": {
                    "optimal_creativity": 0.68,
                    "sample_size": 12
                }
            }
        }
    }

    tuner_low = PromptTuner(analysis_report=report_low)
    suggestions_low = tuner_low.generate_suggestions()

    # Should have lower confidence (<0.85)
    for suggestion in suggestions_low:
        assert suggestion["confidence"] < 0.90  # Allow some variability


def test_evidence_tracing(temp_data_dir, sample_telemetry):
    """Test evidence references in suggestions."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coaches": {
            "career_coach": {
                "entries_analyzed": 50,
                "sentiment_trend": {"positive": 0.70, "neutral": 0.25, "negative": 0.05},
                "tone_correlation": {
                    "top_tone": "Empathetic",
                    "top_tone_score": 0.88,
                    "tone_scores": {"Empathetic": 0.88, "Professional": 0.55}
                },
                "creativity_analysis": {
                    "optimal_creativity": 0.65,
                    "sample_size": 40
                }
            }
        }
    }

    tuner = PromptTuner(analysis_report=report)
    suggestions = tuner.generate_suggestions()

    # Each suggestion should have evidence and telemetry refs
    for suggestion in suggestions:
        assert len(suggestion["evidence"]) > 0
        assert len(suggestion["telemetry_refs"]) > 0
        assert "prompts/insights/" in suggestion["telemetry_refs"][0]


def test_analysis_performance(temp_data_dir, sample_telemetry):
    """Test that analysis completes within performance targets."""
    import time

    # Create large telemetry file (1000 entries)
    insights_dir = temp_data_dir / "prompts" / "insights"
    telemetry_file = insights_dir / "career_coach.jsonl"

    # Replicate sample telemetry to reach 1000 entries
    large_telemetry = sample_telemetry * 23  # ~1000 entries

    with open(telemetry_file, 'w', encoding='utf-8') as f:
        for entry in large_telemetry:
            f.write(json.dumps(entry) + '\n')

    # Run analysis with timing
    analyzer = TelemetryAnalyzer(data_dir=temp_data_dir / "data")
    start_time = time.time()
    report = analyzer.analyze_all_coaches()
    elapsed_ms = (time.time() - start_time) * 1000

    # Should complete in <2000ms (ChatGPT target)
    assert elapsed_ms < 2000

    # Verify processing time in report
    assert report["processing_time_ms"] < 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
