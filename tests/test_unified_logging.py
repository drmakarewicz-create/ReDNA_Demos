import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ReDNACoreDemo.core import logutil


def test_stack_log_writes_json(monkeypatch, tmp_path):
    log_path = tmp_path / "stack.log"
    monkeypatch.setattr(logutil, "_LOG_PATH", log_path)

    logutil.stack_log("core", "INFO", "ingest_ok", "ingest success", {"user_id": "alice"})
    logutil.stack_log("devx", "WARN", "readiness_fail", "not ready", {})

    content = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 2

    first = json.loads(content[0])
    assert first["service"] == "core"
    assert first["level"] == "INFO"
    assert first["event"] == "ingest_ok"
    assert first["meta"]["user_id"] == "alice"

    second = json.loads(content[1])
    assert second["service"] == "devx"
    assert second["level"] == "WARN"
    assert second["event"] == "readiness_fail"
