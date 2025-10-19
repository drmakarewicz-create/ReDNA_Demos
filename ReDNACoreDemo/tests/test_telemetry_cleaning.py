"""
Telemetry Cleaning & Tolerant Analyzer Tests
============================================

Ensures the telemetry janitor, tolerant analyzer mode, and daemon dry-run
operate end-to-end with resilient handling of malformed JSONL input.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

import pytest

from ReDNACoreDemo.core.learning.telemetry_analyzer import TelemetryAnalyzer


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def telemetry_workspace(tmp_path):
    """Create isolated prompts/data directories for telemetry tests."""
    root = tmp_path / "telemetry_workspace"
    insights_dir = root / "prompts" / "insights"
    data_dir = root / "data"
    insights_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    return {
        "root": root,
        "insights_dir": insights_dir,
        "data_dir": data_dir,
    }


def run_janitor(insights_dir: Path, *flags: str) -> subprocess.CompletedProcess:
    """Invoke telemetry_janitor.py with the provided flags."""
    cmd: List[str] = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "telemetry_janitor.py"),
        "--insights-dir",
        str(insights_dir),
    ]
    cmd.extend(flags)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, check=True)


def write_jsonl(path: Path, entries: Iterable[dict]) -> None:
    """Write iterable of dict entries to JSONL."""
    with open(path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def test_janitor_strips_blank_lead_and_enables_analysis(telemetry_workspace):
    insights_dir = telemetry_workspace["insights_dir"]
    data_dir = telemetry_workspace["data_dir"]
    telemetry_file = insights_dir / "head_coach.jsonl"

    minimal_entry = {"ts": "2025-10-09T10:00:00Z", "coach_id": "head_coach", "kind": "telemetry"}

    with open(telemetry_file, "w", encoding="utf-8") as handle:
        handle.write("\n")  # leading blank line
        handle.write(json.dumps(minimal_entry) + "\n")

    run_janitor(insights_dir, "--fix")

    cleaned_lines = telemetry_file.read_text(encoding="utf-8").splitlines()
    assert cleaned_lines == [json.dumps(minimal_entry)]

    analyzer = TelemetryAnalyzer(data_dir=data_dir, tolerant_validation=True)
    entries = analyzer._load_telemetry(telemetry_file)
    assert len(entries) == 1


def test_janitor_removes_non_json_noise(telemetry_workspace):
    insights_dir = telemetry_workspace["insights_dir"]
    telemetry_file = insights_dir / "chatdna_coach.jsonl"

    valid_entry = {
        "ts": "2025-10-09T11:00:00Z",
        "coach_id": "chatdna_coach",
        "kind": "telemetry",
    }

    with open(telemetry_file, "w", encoding="utf-8") as handle:
        handle.write("2025-10-09T00:00:00Z (not json)\n")
        handle.write(json.dumps(valid_entry) + "\n")

    run_janitor(insights_dir, "--fix")

    lines = telemetry_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines == [json.dumps(valid_entry)]


def test_janitor_inserts_kind_default(telemetry_workspace):
    insights_dir = telemetry_workspace["insights_dir"]
    telemetry_file = insights_dir / "beliefdna_coach.jsonl"

    entry_missing_kind = {"ts": "2025-10-09T12:00:00Z", "coach_id": "beliefdna_coach"}
    write_jsonl(telemetry_file, [entry_missing_kind])

    run_janitor(insights_dir, "--fix")

    cleaned = json.loads(telemetry_file.read_text(encoding="utf-8").strip())
    assert cleaned["kind"] == "telemetry"
    assert cleaned["coach_id"] == "beliefdna_coach"


def test_tolerant_mode_counts_and_strict_mode_fails(telemetry_workspace):
    insights_dir = telemetry_workspace["insights_dir"]
    data_dir = telemetry_workspace["data_dir"]
    telemetry_file = insights_dir / "confused_coach.jsonl"

    malformed_lines = [
        {"ts": "", "coach_id": "", "kind": ""},  # missing values to trigger defaults
    ]

    with open(telemetry_file, "w", encoding="utf-8") as handle:
        for entry in malformed_lines:
            handle.write(json.dumps(entry) + "\n")
        handle.write("not-json-line\n")

    strict_analyzer = TelemetryAnalyzer(data_dir=data_dir, tolerant_validation=False)
    with pytest.raises(ValueError):
        strict_analyzer._load_telemetry(telemetry_file)

    tolerant_analyzer = TelemetryAnalyzer(data_dir=data_dir, tolerant_validation=True)
    report = tolerant_analyzer.analyze_all_coaches()

    assert report["malformed_lines_skipped"] >= 1
    assert report["defaults_injected"] >= 1
    assert report["files_cleaned"] >= 1
    assert report["coaches"]["confused_coach"]["entries_analyzed"] == 1


def test_end_to_end_janitor_analyzer_daemon(telemetry_workspace):
    root = telemetry_workspace["root"]
    insights_dir = telemetry_workspace["insights_dir"]
    data_dir = telemetry_workspace["data_dir"]
    coach_file = insights_dir / "head_coach.jsonl"

    now = datetime.now(timezone.utc)
    entries = []
    # Create tone contrast for suggestions
    for idx in range(6):
        entries.append(
            {
                "ts": (now.replace(microsecond=0).isoformat()),
                "coach_id": "head_coach",
                "kind": "telemetry",
                "user_id": f"user_{idx}",
                "active_coach_id": "head_coach",
                "context_version": 1,
                "sentiment": "positive" if idx < 4 else "neutral",
                "features": {"tone": "empathetic" if idx < 4 else "professional"},
                "hints": {"creativity_bias": 0.6},
                "build_ms": 500,
            }
        )

    write_jsonl(coach_file, entries)

    # Introduce malformed extras
    with open(coach_file, "a", encoding="utf-8") as handle:
        handle.write("garbage-leading-text\n")
        handle.write(json.dumps({"ts": "", "coach_id": "head_coach"}) + "\n")

    run_janitor(insights_dir, "--fix")

    analyzer = TelemetryAnalyzer(data_dir=data_dir, tolerant_validation=True)
    report = analyzer.analyze_all_coaches()
    assert report["coaches"]["head_coach"]["entries_analyzed"] >= 6

    env = os.environ.copy()
    env["REDNA_CORE_DATA"] = str(data_dir)
    env["WORKSPACE_ROOT"] = str(root)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ReDNACoreDemo.core.learning.daemon",
            "--once",
            "--dry-run",
            "--threshold",
            "0.9",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    stdout = result.stdout
    start = stdout.find("{")
    end = stdout.rfind("}")
    assert start != -1 and end != -1 and end > start
    summary = json.loads(stdout[start : end + 1])
    assert summary["coaches_analyzed"] >= 1
    assert summary["elapsed_seconds"] >= 0.0
