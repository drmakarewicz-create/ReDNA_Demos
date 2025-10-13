import json
from pathlib import Path

from ReDNACoreDemo.core.ingestion_pipeline import IngestionPipeline


def _create_pipeline(tmp_path: Path) -> IngestionPipeline:
    data_root = tmp_path / "data"
    telemetry_root = tmp_path / "telemetry" / "ingestion"
    return IngestionPipeline(data_root=data_root, telemetry_root=telemetry_root)


def _load_single_record(root: Path) -> dict:
    records = list(root.rglob("*.json"))
    assert len(records) == 1, f"expected single record in {root}, found {len(records)}"
    return json.loads(records[0].read_text())


def test_chat_ingestion_writes_record(tmp_path: Path) -> None:
    pipeline = _create_pipeline(tmp_path)

    pipeline.capture_chat(
        user_id="test_user",
        text="Hello coach!",
        meta={"tone_hint": "warm"},
        source="unit_test",
        actor="test_suite",
    )

    telemetry_root = tmp_path / "telemetry" / "ingestion" / "accepted" / "test_user"
    record = _load_single_record(telemetry_root)

    assert record["event_type"] == "chat_message"
    assert record["content"]["text"] == "Hello coach!"
    assert record["metadata"]["tone_hint"] == "warm"
    assert record["accepted"] is True


def test_file_ingestion_respects_comfort(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    user_dir = data_root / "users" / "alice"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "comfort_index.json").write_text(json.dumps({"max_level": "standard"}))

    pipeline = IngestionPipeline(data_root=data_root, telemetry_root=tmp_path / "telemetry" / "ingestion")

    pipeline.capture_file(
        user_id="alice",
        file_name="therapy_notes.pdf",
        file_bytes=b"super secret",
        metadata={"sensitivity_level": "restricted", "mime_type": "application/pdf"},
        source="unit_test",
        actor="test_suite",
    )

    telemetry_root = tmp_path / "telemetry" / "ingestion" / "quarantined" / "alice"
    record = _load_single_record(telemetry_root)

    assert record["event_type"] == "file_upload"
    assert record["accepted"] is False
    assert record["comfort"]["threshold"] == "standard"
    assert record["content"]["sha256"]


def test_coach_handoff_ingestion(tmp_path: Path) -> None:
    pipeline = _create_pipeline(tmp_path)

    pipeline.capture_coach_handoff(
        user_id="bob",
        from_coach="head_coach",
        to_coach="ucn_rr",
        reason="Needs relational recalibration",
        metadata={"sensitivity_level": "standard"},
        source="unit_test",
        actor="test_suite",
    )

    telemetry_root = tmp_path / "telemetry" / "ingestion" / "accepted" / "bob"
    record = _load_single_record(telemetry_root)

    assert record["event_type"] == "coach_handoff"
    assert record["content"]["from"] == "head_coach"
    assert record["content"]["to"] == "ucn_rr"
    assert record["content"]["reason"] == "Needs relational recalibration"
