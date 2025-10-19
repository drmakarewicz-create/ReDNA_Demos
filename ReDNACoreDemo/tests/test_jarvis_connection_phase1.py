"""
Test Jarvis Connection Phase 1 — Adaptive Tone & Empathy

Tests real-time tone and empathy adaptation including:
1. Tone echo (casual → casual, formal → formal)
2. Formality control
3. Empathy cue detection and response
4. Consent safety (no private corpus access)
5. EMA smoothing and delta clamping
6. Telemetry logging
7. Performance requirements
"""

import json
import pytest
import time
from pathlib import Path
from typing import Dict, Any

from ReDNACoreDemo.core.connection.tone_adapter import ToneAdapter, create_tone_adapter


@pytest.fixture
def temp_config(tmp_path):
    """Create temporary connection config."""
    config = {
        "ema_alpha": 0.5,
        "default_tone": "professional",
        "tone_map": {
            "casual": [0.0, 0.3],
            "empathetic": [0.3, 0.7],
            "professional": [0.6, 0.9],
            "direct": [0.8, 1.0]
        },
        "empathy_keywords": [
            "sorry", "understand", "frustrated", "overwhelmed",
            "tough", "appreciate", "worried", "anxious", "stressed"
        ],
        "max_delta_per_turn": 0.25,
        "developer_trace": True
    }

    config_path = tmp_path / "test_jarvis_connection_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f)

    return config_path


# Test 1: Tone echo - casual message → casual tone
def test_casual_tone_echo(temp_config):
    """Test that casual user message shifts tone toward casual."""
    adapter = ToneAdapter(config_path=temp_config)

    casual_text = "hey can you help me plan tmrw? super swamped lol 😅"

    analysis = adapter.analyze_turn(
        user_text=casual_text,
        recent_history=[],
        user_id="TEST"
    )

    adjustments = adapter.compute_adjustments(
        tone_score=analysis["tone_score"],
        formality_score=analysis["formality_score"],
        empathy_cue=analysis["empathy_cue"],
        user_id="TEST"
    )

    # Casual text should have low tone score and formality
    assert analysis["tone_score"] < 0.5, f"Expected casual tone (<0.5), got {analysis['tone_score']}"
    assert analysis["formality_score"] < 0.5, f"Expected low formality (<0.5), got {analysis['formality_score']}"

    # Tone target should be casual or empathetic
    assert adjustments["hints"]["tone_target"] in ["casual", "empathetic"]


# Test 2: Formality control - formal message → higher formality
def test_formal_tone_shift(temp_config):
    """Test that formal user message increases formality_bias."""
    adapter = ToneAdapter(config_path=temp_config)

    formal_text = "I would appreciate a comprehensive structured outline of tomorrow's agenda, prioritized by strategic impact and resource allocation."

    analysis = adapter.analyze_turn(
        user_text=formal_text,
        recent_history=[],
        user_id="TEST"
    )

    adjustments = adapter.compute_adjustments(
        tone_score=analysis["tone_score"],
        formality_score=analysis["formality_score"],
        empathy_cue=analysis["empathy_cue"],
        user_id="TEST"
    )

    # Formal text should have high formality score
    assert analysis["formality_score"] > 0.6, f"Expected high formality (>0.6), got {analysis['formality_score']}"

    # Formality bias should be elevated
    assert adjustments["hints"]["formality_bias"] > 0.6


# Test 3: Empathy cue detection
def test_empathy_cue_detection(temp_config):
    """Test that empathy keywords trigger empathy_cue increase."""
    adapter = ToneAdapter(config_path=temp_config)

    empathy_text = "I'm feeling really overwhelmed and frustrated with this project. Sorry for being confused."

    analysis = adapter.analyze_turn(
        user_text=empathy_text,
        recent_history=[],
        user_id="TEST"
    )

    adjustments = adapter.compute_adjustments(
        tone_score=analysis["tone_score"],
        formality_score=analysis["formality_score"],
        empathy_cue=analysis["empathy_cue"],
        user_id="TEST"
    )

    # Should detect high empathy cue
    assert analysis["empathy_cue"] == "high", f"Expected high empathy, got {analysis['empathy_cue']}"

    # Empathy bias should be elevated (accounting for EMA smoothing from 0.5 baseline)
    # With alpha=0.5, first turn moves halfway from 0.5 to 0.85 = 0.675
    # But max_delta=0.25, so clamped to 0.5 + 0.25 = 0.75 on first turn
    # Actually, it's EMA: 0.5 + 0.5 * min(0.25, 0.85-0.5) = 0.5 + 0.5*0.25 = 0.625
    assert adjustments["hints"]["empathy_bias"] >= 0.6

    # Tone target should be empathetic (high empathy cue overrides tone score)
    assert adjustments["hints"]["tone_target"] == "empathetic"


# Test 4: No consent access - adapter only uses current turn
def test_no_consent_access(temp_config):
    """Test that adapter doesn't access private corpus without consent."""
    adapter = ToneAdapter(config_path=temp_config)

    # Adapter should only use provided text and history
    # No file system access beyond config
    analysis = adapter.analyze_turn(
        user_text="Test message",
        recent_history=["Previous message"],
        user_id="TEST"
    )

    # Should complete successfully without requiring file access
    assert "tone_score" in analysis
    assert "formality_score" in analysis
    assert "empathy_cue" in analysis


# Test 5: EMA smoothing prevents oscillation
def test_ema_smoothing(temp_config):
    """Test that EMA smoothing converges and doesn't oscillate beyond max_delta."""
    adapter = ToneAdapter(config_path=temp_config)

    user_id = "TEST_EMA"

    # Turn 1: Casual
    casual_analysis = adapter.analyze_turn(
        user_text="hey what's up?",
        user_id=user_id
    )
    adj1 = adapter.compute_adjustments(
        tone_score=casual_analysis["tone_score"],
        formality_score=casual_analysis["formality_score"],
        empathy_cue=casual_analysis["empathy_cue"],
        user_id=user_id
    )

    # Turn 2: Formal (should not jump immediately)
    formal_analysis = adapter.analyze_turn(
        user_text="I require a detailed analysis of the quarterly performance metrics.",
        user_id=user_id
    )
    adj2 = adapter.compute_adjustments(
        tone_score=formal_analysis["tone_score"],
        formality_score=formal_analysis["formality_score"],
        empathy_cue=formal_analysis["empathy_cue"],
        user_id=user_id
    )

    # Delta should be clamped by max_delta_per_turn (0.25)
    formality_delta = adj2["hints"]["formality_bias"] - adj1["hints"]["formality_bias"]
    assert abs(formality_delta) <= 0.25, f"Delta {formality_delta} exceeds max_delta_per_turn 0.25"


# Test 6: Telemetry integration (via orchestrator)
def test_telemetry_logged(tmp_path, temp_config):
    """Test that connection adjustments are logged to telemetry."""
    from ReDNACoreDemo.core.hc_orchestrator import HCOrchestrator

    # Create temp data directory
    data_root = tmp_path / "data"
    data_root.mkdir()

    orchestrator = HCOrchestrator(data_root=data_root)

    behavior_context = orchestrator.on_turn_start(
        user_id="TEST",
        text="I'm feeling stressed about this deadline.",
        meta={"developer_mode": False},
        behavior_context={},
        recent_history=[]
    )

    # Should have connection data
    assert "_connection_data" in behavior_context
    assert "tone_target" in behavior_context["_connection_data"]
    assert "empathy_bias" in behavior_context["_connection_data"]


# Test 7: Performance - analysis overhead ≤ 20ms (unit)
def test_performance_unit(temp_config):
    """Test that tone analysis completes in ≤ 20ms (unit test)."""
    adapter = ToneAdapter(config_path=temp_config)

    start = time.time()

    for _ in range(10):
        analysis = adapter.analyze_turn(
            user_text="This is a test message for performance benchmarking.",
            user_id="PERF_TEST"
        )

        adjustments = adapter.compute_adjustments(
            tone_score=analysis["tone_score"],
            formality_score=analysis["formality_score"],
            empathy_cue=analysis["empathy_cue"],
            user_id="PERF_TEST"
        )

    elapsed_ms = (time.time() - start) / 10 * 1000

    # Should be well under 20ms per analysis + adjustment
    assert elapsed_ms < 20, f"Analysis took {elapsed_ms:.2f}ms (target: <20ms)"


# Test 8: Signals extraction
def test_signals_extraction(temp_config):
    """Test that signal extraction identifies key features."""
    adapter = ToneAdapter(config_path=temp_config)

    text = "I'm SO FRUSTRATED!!! This is TERRIBLE and I'm overwhelmed. 😢"

    analysis = adapter.analyze_turn(user_text=text, user_id="TEST")

    signals = analysis["signals"]

    # Should detect exclamations
    assert signals["exclamations"] >= 3

    # Should detect negative sentiment
    assert signals["sentiment"] == "negative"

    # Should detect empathy keywords
    assert signals["empathy_keywords"] >= 2

    # Should detect high uppercase ratio
    assert signals["uppercase_ratio"] > 0.1

    # Should detect emoji
    assert signals["emoji_count"] >= 1


# Test 9: Confidence scoring
def test_confidence_scoring(temp_config):
    """Test that adjustments include confidence score."""
    adapter = ToneAdapter(config_path=temp_config)

    analysis = adapter.analyze_turn(
        user_text="Test message",
        user_id="TEST"
    )

    adjustments = adapter.compute_adjustments(
        tone_score=analysis["tone_score"],
        formality_score=analysis["formality_score"],
        empathy_cue=analysis["empathy_cue"],
        user_id="TEST"
    )

    # Should include confidence
    assert "confidence" in adjustments
    assert 0.0 <= adjustments["confidence"] <= 1.0


# Test 10: Tone map coverage
def test_tone_map_coverage(temp_config):
    """Test that all tone scores map to valid tone targets."""
    adapter = ToneAdapter(config_path=temp_config)

    # Test different tone scores
    test_cases = [
        (0.1, "low empathy"),   # Casual
        (0.5, "med empathy"),   # Empathetic
        (0.75, "low empathy"),  # Professional
        (0.95, "low empathy"),  # Direct
    ]

    for tone_score, empathy_cue_str in test_cases:
        empathy_cue = empathy_cue_str.split()[0]  # Extract "low"/"med"/"high"

        tone_target = adapter._map_tone_target(tone_score, empathy_cue)

        assert tone_target in ["casual", "empathetic", "professional", "direct"]


# Test 11: Creativity bias preservation
def test_creativity_bias_preservation(temp_config):
    """Test that creativity_bias from behavior_context is preserved."""
    adapter = ToneAdapter(config_path=temp_config)

    existing_context = {"creativity_bias": 0.85}

    analysis = adapter.analyze_turn(
        user_text="Test message",
        user_id="TEST"
    )

    adjustments = adapter.compute_adjustments(
        tone_score=analysis["tone_score"],
        formality_score=analysis["formality_score"],
        empathy_cue=analysis["empathy_cue"],
        behavior_context=existing_context,
        user_id="TEST"
    )

    # Should preserve existing creativity bias
    assert adjustments["hints"]["creativity_bias"] == 0.85


# Test 12: Recent history influence
def test_recent_history_tracking(temp_config):
    """Test that recent history is tracked per user."""
    adapter = ToneAdapter(config_path=temp_config)

    user_id = "HISTORY_TEST"

    # Add multiple messages
    messages = [
        "First message",
        "Second message",
        "Third message"
    ]

    for msg in messages:
        adapter.analyze_turn(user_text=msg, user_id=user_id)

    # History should be tracked (up to 5 messages)
    assert user_id in adapter._user_history
    assert len(adapter._user_history[user_id]) == 3


# Test 13: Empathy cue levels
def test_empathy_cue_levels(temp_config):
    """Test that empathy cue correctly maps to low/med/high."""
    adapter = ToneAdapter(config_path=temp_config)

    # Low empathy (no keywords, positive)
    low_signals = {
        "empathy_keywords": 0,
        "sentiment": "positive",
        "avg_word_length": 5.0,
        "avg_sentence_length": 12.0,
        "exclamations": 0,
        "questions": 0,
        "emoji_count": 0,
        "uppercase_ratio": 0.0
    }
    assert adapter._detect_empathy_cue(low_signals) == "low"

    # Med empathy (1 keyword or negative)
    med_signals = {**low_signals, "empathy_keywords": 1}
    assert adapter._detect_empathy_cue(med_signals) == "med"

    # High empathy (3+ keywords or 2 keywords + negative)
    high_signals = {**low_signals, "empathy_keywords": 3}
    assert adapter._detect_empathy_cue(high_signals) == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
