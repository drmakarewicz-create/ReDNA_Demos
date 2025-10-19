
from pathlib import Path

from ReDNACoreDemo.core.head_coach.empathy_monitor import EmpathyMonitor


def test_empathy_monitor_detects_positive_state(tmp_path: Path) -> None:
    monitor = EmpathyMonitor("alice", data_root=tmp_path / "data")
    snapshot = monitor.observe_turn(
        message_text="I'm so happy and grateful for the progress!",
        recent_history=[],
        metadata={},
    )

    assert snapshot.emotional_state.value in {"joy", "trust"}
    assert snapshot.bonding_metrics["trust_score"] > 0.5

    telemetry = tmp_path / "data" / "telemetry" / "empathy" / "alice.jsonl"
    assert telemetry.exists()
    assert telemetry.read_text().strip()


def test_empathy_monitor_records_vulnerability(tmp_path: Path) -> None:
    monitor = EmpathyMonitor("bob", data_root=tmp_path / "data")
    snapshot = monitor.observe_turn(
        message_text="Honestly I'm feeling anxious and overwhelmed.",
        recent_history=["previous message"],
        metadata={"user_shared_vulnerability": True},
    )

    assert "trust_deepening" in snapshot.primary_needs
    assert snapshot.bonding_metrics["rapport_score"] >= 0.5
