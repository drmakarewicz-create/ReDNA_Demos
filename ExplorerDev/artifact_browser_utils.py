"""Artifact browser utilities for Developer Explorer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
USERS_DIR = REPO_ROOT / "data" / "users"
AUTOMATION_LOG_DIR = REPO_ROOT / "docs" / "automation_log"
RECENT_ARTIFACTS_PATH = REPO_ROOT / "data" / "dev_logs" / "recent_artifacts.jsonl"

MAX_RECENT_ARTIFACTS = 20


@dataclass
class ArtifactFile:
    """Metadata for an artifact file."""

    path: Path
    relative_path: str
    name: str
    size_bytes: int
    modified: datetime
    category: str  # "user_data", "automation_log", "other"

    @property
    def size_display(self) -> str:
        """Human-readable file size."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024 or unit == "GB":
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{self.size_bytes} B"

    @property
    def modified_display(self) -> str:
        """Human-readable modification time."""
        now = datetime.now(timezone.utc)
        delta = now - self.modified

        if delta.total_seconds() < 60:
            return "just now"
        elif delta.total_seconds() < 3600:
            mins = int(delta.total_seconds() / 60)
            return f"{mins}m ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days}d ago"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "modified": self.modified.isoformat(),
            "category": self.category,
        }


def find_user_artifacts(user_id: Optional[str] = None) -> List[ArtifactFile]:
    """Find artifact files in data/users/*."""
    artifacts = []

    if not USERS_DIR.exists():
        return artifacts

    # If user_id specified, scan only that user's directory
    if user_id:
        user_dirs = [USERS_DIR / user_id]
    else:
        user_dirs = [d for d in USERS_DIR.iterdir() if d.is_dir()]

    for user_dir in user_dirs:
        if not user_dir.exists():
            continue

        # Look for common artifact patterns
        patterns = [
            "*.jsonl",
            "*.json",
            "baseline.json",
            "journal.jsonl",
            "conversation.jsonl",
            "tasks.jsonl",
            "*.log",
        ]

        for pattern in patterns:
            for file_path in user_dir.rglob(pattern):
                if not file_path.is_file():
                    continue

                try:
                    stat = file_path.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

                    artifacts.append(
                        ArtifactFile(
                            path=file_path,
                            relative_path=str(file_path.relative_to(REPO_ROOT)),
                            name=file_path.name,
                            size_bytes=stat.st_size,
                            modified=modified,
                            category="user_data",
                        )
                    )
                except (OSError, ValueError):
                    continue

    return sorted(artifacts, key=lambda a: a.modified, reverse=True)


def find_automation_log_artifacts() -> List[ArtifactFile]:
    """Find artifact files in docs/automation_log/*."""
    artifacts = []

    if not AUTOMATION_LOG_DIR.exists():
        return artifacts

    for file_path in AUTOMATION_LOG_DIR.rglob("*"):
        if not file_path.is_file():
            continue

        # Include .md, .jsonl, .json files
        if file_path.suffix not in [".md", ".jsonl", ".json", ".txt"]:
            continue

        try:
            stat = file_path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)

            artifacts.append(
                ArtifactFile(
                    path=file_path,
                    relative_path=str(file_path.relative_to(REPO_ROOT)),
                    name=file_path.name,
                    size_bytes=stat.st_size,
                    modified=modified,
                    category="automation_log",
                )
            )
        except (OSError, ValueError):
            continue

    return sorted(artifacts, key=lambda a: a.modified, reverse=True)


def find_all_artifacts(search_term: Optional[str] = None) -> List[ArtifactFile]:
    """Find all artifact files, optionally filtered by search term."""
    artifacts = []

    artifacts.extend(find_user_artifacts())
    artifacts.extend(find_automation_log_artifacts())

    if search_term:
        search_lower = search_term.lower()
        artifacts = [
            a for a in artifacts
            if search_lower in a.name.lower() or search_lower in a.relative_path.lower()
        ]

    return sorted(artifacts, key=lambda a: a.modified, reverse=True)


def read_artifact_content(
    artifact_path: str,
    max_lines: int = 500,
) -> tuple[str, str]:
    """
    Read artifact file content.

    Returns:
        (content, file_type) where file_type is "json", "jsonl", "text", etc.
    """
    path = REPO_ROOT / artifact_path

    if not path.exists():
        return f"File not found: {artifact_path}", "error"

    try:
        content = path.read_text(encoding="utf-8", errors="replace")

        # Limit to max_lines
        lines = content.split("\n")
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines])
            content += f"\n\n... (truncated, showing first {max_lines} of {len(lines)} lines)"

        # Determine file type
        suffix = path.suffix.lower()
        if suffix == ".json":
            file_type = "json"
        elif suffix == ".jsonl":
            file_type = "jsonl"
        elif suffix == ".md":
            file_type = "markdown"
        elif suffix in [".log", ".txt"]:
            file_type = "text"
        else:
            file_type = "text"

        return content, file_type

    except Exception as exc:
        return f"Error reading file: {exc}", "error"


def track_recent_artifact(artifact_path: str) -> None:
    """Track an artifact as recently accessed."""
    RECENT_ARTIFACTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load existing recent artifacts
    recent = []
    if RECENT_ARTIFACTS_PATH.exists():
        lines = RECENT_ARTIFACTS_PATH.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("path") != artifact_path:
                    recent.append(entry)
            except json.JSONDecodeError:
                continue

    # Add new entry at the top
    recent.insert(
        0,
        {
            "path": artifact_path,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Keep only MAX_RECENT_ARTIFACTS
    recent = recent[:MAX_RECENT_ARTIFACTS]

    # Write back
    with open(RECENT_ARTIFACTS_PATH, "w", encoding="utf-8") as f:
        for entry in recent:
            f.write(json.dumps(entry) + "\n")


def load_recent_artifacts() -> List[str]:
    """Load list of recently accessed artifact paths."""
    if not RECENT_ARTIFACTS_PATH.exists():
        return []

    recent_paths = []
    lines = RECENT_ARTIFACTS_PATH.read_text(encoding="utf-8").strip().split("\n")

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            path = entry.get("path")
            if path:
                recent_paths.append(path)
        except json.JSONDecodeError:
            continue

    return recent_paths


def get_user_list() -> List[str]:
    """Get list of user IDs from data/users/."""
    if not USERS_DIR.exists():
        return []

    users = []
    for user_dir in USERS_DIR.iterdir():
        if user_dir.is_dir():
            users.append(user_dir.name)

    return sorted(users)
