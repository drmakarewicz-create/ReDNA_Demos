"""Log tailing utilities for Developer Explorer."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class LogSource:
    """Configuration for a log source."""

    name: str
    description: str
    command: Optional[str]  # Shell command to get logs, or None for file
    file_path: Optional[Path]  # Log file path, or None for command
    tail_lines: int = 200

    @property
    def is_file(self) -> bool:
        return self.file_path is not None

    @property
    def is_command(self) -> bool:
        return self.command is not None


# Predefined log sources
LOG_SOURCES = {
    "uvicorn": LogSource(
        name="Uvicorn Server",
        description="Backend API server logs (port 8001)",
        command="ps aux | grep 'uvicorn.*8001' | grep -v grep | awk '{print $2}' | xargs -I {} tail -n 200 /proc/{}/fd/1 2>/dev/null || echo 'Server not running'",
        file_path=None,
    ),
    "test_output": LogSource(
        name="Test Output",
        description="Latest pytest execution output",
        command=None,
        file_path=REPO_ROOT / "data" / "dev_logs" / "last_test_output.log",
    ),
    "trace_core": LogSource(
        name="Core Trace",
        description="ReDNACore API trace log",
        command=None,
        file_path=REPO_ROOT / "ReDNACoreDemo" / "data" / "dev_logs" / "trace_core.jsonl",
    ),
    "diagnostics": LogSource(
        name="Diagnostics",
        description="Developer Explorer diagnostics log",
        command=None,
        file_path=REPO_ROOT / "data" / "dev_logs" / "diagnostics.log",
    ),
}


def get_log_tail(
    source_key: str,
    max_lines: int = 200,
) -> tuple[str, str]:
    """
    Get tail of a log source.

    Returns:
        (content, status) where status is "ok", "empty", "error"
    """
    source = LOG_SOURCES.get(source_key)

    if not source:
        return f"Unknown log source: {source_key}", "error"

    try:
        if source.is_file:
            return _tail_file(source.file_path, max_lines)
        elif source.is_command:
            return _tail_command(source.command, max_lines)
        else:
            return "Log source not configured", "error"

    except Exception as exc:
        return f"Error reading log: {exc}", "error"


def _tail_file(
    file_path: Optional[Path],
    max_lines: int,
) -> tuple[str, str]:
    """Tail a log file."""
    if not file_path:
        return "No file path configured", "error"

    if not file_path.exists():
        return f"Log file not found: {file_path.name}", "empty"

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        # Get last max_lines
        tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        tail_content = "\n".join(tail_lines)

        if not tail_content.strip():
            return "Log file is empty", "empty"

        return tail_content, "ok"

    except Exception as exc:
        return f"Error reading file: {exc}", "error"


def _tail_command(
    command: Optional[str],
    max_lines: int,
) -> tuple[str, str]:
    """Execute a command to get log output."""
    if not command:
        return "No command configured", "error"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(REPO_ROOT),
        )

        output = result.stdout or result.stderr

        if not output.strip():
            return "No output from command", "empty"

        # Limit to max_lines
        lines = output.split("\n")
        tail_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        return "\n".join(tail_lines), "ok"

    except subprocess.TimeoutExpired:
        return "Command timeout", "error"
    except Exception as exc:
        return f"Error executing command: {exc}", "error"


def get_server_pids() -> List[tuple[int, str]]:
    """
    Get PIDs of running uvicorn servers.

    Returns:
        List of (pid, port) tuples
    """
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        pids = []

        for line in result.stdout.split("\n"):
            if "uvicorn" in line and "ReDNACoreDemo.core.api" in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])

                        # Extract port from command line
                        port = "unknown"
                        if "--port" in line:
                            port_idx = line.index("--port") + 7
                            port_str = line[port_idx:].split()[0]
                            port = port_str

                        pids.append((pid, port))
                    except (ValueError, IndexError):
                        continue

        return pids

    except Exception:
        return []


def tail_server_logs(pid: int, max_lines: int = 200) -> tuple[str, str]:
    """
    Tail logs from a running server process.

    Note: This is platform-dependent and may not work on all systems.
    macOS doesn't support /proc, so we use lsof as fallback.

    Returns:
        (content, status)
    """
    # Try to find log file via lsof
    try:
        result = subprocess.run(
            ["lsof", "-p", str(pid), "-a", "-d", "1"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        # Parse lsof output to find stdout log file
        lines = result.stdout.split("\n")
        log_file = None

        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 9:
                # Check if it's a regular file (not pipe or socket)
                file_type = parts[4]
                if file_type == "REG":
                    log_file = " ".join(parts[8:])
                    break

        if log_file and Path(log_file).exists():
            return _tail_file(Path(log_file), max_lines)

    except Exception:
        pass

    # Fallback: try to capture recent stderr/stdout
    # This won't work well but provides user feedback
    return (
        f"Live log capture not available for PID {pid}\n\n"
        "Tip: Check terminal where uvicorn was started, or configure logging to file",
        "empty"
    )


def save_test_output(output: str) -> None:
    """Save test output to last_test_output.log."""
    log_file = REPO_ROOT / "data" / "dev_logs" / "last_test_output.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp_line = f"\n{'=' * 80}\n"
    timestamp_line += f"Test run at {datetime.now(timezone.utc).isoformat()}\n"
    timestamp_line += f"{'=' * 80}\n\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(timestamp_line)
        f.write(output)
        f.write("\n\n")
