"""
Head Coach Prompt Loader

Dynamically loads HC system prompt from markdown file with SHA256 verification
and hot-reload capability for development.
"""
from __future__ import annotations

import hashlib
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

# Global cache and lock
_prompt_cache: Optional[Dict[str, str]] = None
_prompt_lock = threading.Lock()


def load_hc_prompt(prompt_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Load Head Coach system prompt from markdown file.

    Args:
        prompt_path: Path to prompt markdown file. If None, uses default location.

    Returns:
        Dict with keys:
            - text: Full prompt text
            - sha256: SHA256 hash of file content
            - version: Extracted version from markdown
            - loaded_at: ISO timestamp of load
            - error: Error message if load failed (optional)

    Thread-safe: Uses lock to prevent race conditions on cache.
    """
    global _prompt_cache

    # Use default path if not specified
    if prompt_path is None:
        file_root = Path(__file__).resolve().parents[1]
        prompt_path = file_root.parent / "prompts" / "head_coach_ai_ingestion_v2.md"

    # Check cache first (without lock for performance)
    if _prompt_cache is not None:
        return _prompt_cache

    # Acquire lock for file I/O and cache update
    with _prompt_lock:
        # Double-check cache after acquiring lock (another thread may have loaded)
        if _prompt_cache is not None:
            return _prompt_cache

        try:
            if not prompt_path.exists():
                error_result = {
                    "text": "Head Coach prompt not loaded (file missing)",
                    "sha256": "none",
                    "version": "missing",
                    "loaded_at": datetime.now(timezone.utc).isoformat(),
                    "error": f"Prompt file not found at {prompt_path}"
                }
                _prompt_cache = error_result
                return error_result

            # Read prompt file
            prompt_text = prompt_path.read_text(encoding="utf-8")

            # Compute SHA256
            prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

            # Extract version from markdown (look for **Version**: X.X)
            version_match = re.search(r'\*\*Version\*\*:\s*(\S+)', prompt_text)
            version = version_match.group(1) if version_match else "unknown"

            result = {
                "text": prompt_text,
                "sha256": prompt_sha,
                "version": version,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "path": str(prompt_path)
            }

            _prompt_cache = result
            return result

        except Exception as e:
            error_result = {
                "text": f"Error loading HC prompt: {e}",
                "sha256": "error",
                "version": "error",
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
            _prompt_cache = error_result
            return error_result


def reload_hc_prompt(prompt_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Force reload of Head Coach prompt from file.

    Args:
        prompt_path: Optional path to prompt file

    Returns:
        Same format as load_hc_prompt()

    Thread-safe: Acquires lock before clearing cache.
    """
    global _prompt_cache

    with _prompt_lock:
        # Clear cache to force reload
        _prompt_cache = None

    # Load fresh copy
    return load_hc_prompt(prompt_path)


def get_hc_prompt_text() -> str:
    """
    Get just the prompt text (for convenience).

    Returns:
        Prompt text string, or error message if load failed
    """
    prompt_info = load_hc_prompt()
    return prompt_info.get("text", "")


def get_hc_prompt_sha256() -> str:
    """
    Get just the prompt SHA256 hash (for health checks).

    Returns:
        SHA256 hex string, or "none"/"error" if not loaded
    """
    prompt_info = load_hc_prompt()
    return prompt_info.get("sha256", "none")


def get_hc_prompt_version() -> str:
    """
    Get just the prompt version (for health checks).

    Returns:
        Version string, or "unknown"/"error" if not loaded
    """
    prompt_info = load_hc_prompt()
    return prompt_info.get("version", "unknown")
