"""Test runner utilities for Developer Explorer."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_FILES_PATTERN = "test_*acceptance*.py"
TEST_HISTORY_PATH = REPO_ROOT / "data" / "dev_logs" / "test_history.jsonl"
VENV_PYTEST = REPO_ROOT / ".venv" / "bin" / "pytest"


@dataclass
class TestRun:
    """Result of a test execution."""

    test_file: str
    test_name: Optional[str]  # None = all tests in file
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    timestamp: str
    passed: int
    failed: int
    errors: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and self.failed == 0 and self.errors == 0

    @property
    def status(self) -> str:
        if self.success:
            return "✅ PASSED"
        elif self.exit_code != 0:
            return "❌ FAILED"
        else:
            return "⚠️ ERRORS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_file": self.test_file,
            "test_name": self.test_name,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:5000],  # Truncate for storage
            "stderr": self.stderr[:5000],
            "duration_sec": self.duration_sec,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
        }


def find_test_files() -> List[Path]:
    """Find all acceptance test files in repo root."""
    return sorted(REPO_ROOT.glob(TEST_FILES_PATTERN))


def find_test_functions(test_file: Path) -> List[str]:
    """Extract test function names from a test file."""
    test_names = []

    if not test_file.exists():
        return test_names

    content = test_file.read_text(encoding="utf-8", errors="ignore")

    import re
    # Match 'def test_*' patterns
    pattern = r'^def (test_\w+)\s*\('
    for match in re.finditer(pattern, content, re.MULTILINE):
        test_names.append(match.group(1))

    return test_names


def run_pytest(
    test_file: str,
    test_name: Optional[str] = None,
    verbose: bool = True,
    timeout: int = 300,
) -> TestRun:
    """
    Run pytest on a test file or specific test.

    Args:
        test_file: Path to test file (relative to repo root)
        test_name: Optional specific test function name
        verbose: Use -v flag
        timeout: Max seconds to wait

    Returns:
        TestRun with results
    """
    test_path = REPO_ROOT / test_file

    if not test_path.exists():
        return TestRun(
            test_file=test_file,
            test_name=test_name,
            exit_code=1,
            stdout="",
            stderr=f"Test file not found: {test_path}",
            duration_sec=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            passed=0,
            failed=0,
            errors=1,
        )

    # Build pytest command (use venv pytest if available, otherwise fallback to system)
    pytest_bin = str(VENV_PYTEST) if VENV_PYTEST.exists() else "pytest"
    cmd = [pytest_bin]

    if verbose:
        cmd.append("-v")

    if test_name:
        cmd.append(f"{test_file}::{test_name}")
    else:
        cmd.append(test_file)

    # Add output formatting
    cmd.extend(["-x", "--tb=short"])

    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

    except subprocess.TimeoutExpired:
        exit_code = 124
        stdout = ""
        stderr = f"Test timeout after {timeout}s"
    except Exception as exc:
        exit_code = 1
        stdout = ""
        stderr = f"Test execution failed: {exc}"

    duration = time.time() - start

    # Parse pytest output for counts
    passed, failed, errors = _parse_pytest_summary(stdout)

    run = TestRun(
        test_file=test_file,
        test_name=test_name,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_sec=round(duration, 2),
        timestamp=datetime.now(timezone.utc).isoformat(),
        passed=passed,
        failed=failed,
        errors=errors,
    )

    # Log to history
    _append_test_history(run)

    return run


def _parse_pytest_summary(output: str) -> tuple[int, int, int]:
    """Parse pytest output for pass/fail/error counts."""
    import re

    # Look for patterns like "3 passed, 1 failed in 2.34s"
    summary_pattern = r'(\d+)\s+passed|(\d+)\s+failed|(\d+)\s+error'

    passed = 0
    failed = 0
    errors = 0

    for match in re.finditer(summary_pattern, output):
        if match.group(1):  # passed
            passed = int(match.group(1))
        elif match.group(2):  # failed
            failed = int(match.group(2))
        elif match.group(3):  # error
            errors = int(match.group(3))

    return passed, failed, errors


def _append_test_history(run: TestRun) -> None:
    """Append test run to history log."""
    TEST_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(TEST_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(run.to_dict()) + "\n")


def load_test_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Load recent test history."""
    if not TEST_HISTORY_PATH.exists():
        return []

    lines = TEST_HISTORY_PATH.read_text(encoding="utf-8").strip().split("\n")

    history = []
    for line in reversed(lines[-limit:]):
        if not line.strip():
            continue
        try:
            history.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return history


def get_test_file_display_name(test_file: str | Path) -> str:
    """Get short display name for test file."""
    path = Path(test_file)
    name = path.stem

    # Strip test_ prefix for cleaner display
    if name.startswith("test_"):
        name = name[5:]

    # Replace underscores with spaces and title case
    display = name.replace("_", " ").title()

    return display
