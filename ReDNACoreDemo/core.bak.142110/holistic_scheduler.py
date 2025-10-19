"""
Holistic Scheduler

Runs periodic holistic reviews for users on a configurable cadence.
Controlled by HOLISTIC_CADENCE_HOURS environment variable (default: 168 = weekly).
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import holistic, storage


# Configuration
DEFAULT_CADENCE_HOURS = 168  # 1 week
DEFAULT_ENABLED = False

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False
_scheduler_lock = threading.Lock()


def get_cadence_hours() -> int:
    """Get the holistic cadence from environment."""
    cadence = os.getenv("HOLISTIC_CADENCE_HOURS", "").strip()
    try:
        value = int(cadence)
        if value <= 0:
            return DEFAULT_CADENCE_HOURS
        return value
    except (ValueError, TypeError):
        return DEFAULT_CADENCE_HOURS


def is_enabled() -> bool:
    """Check if holistic scheduler is enabled."""
    enabled = os.getenv("HOLISTIC_SCHEDULER_ENABLED", "").strip().lower()
    return enabled in {"true", "1", "yes", "on"}


def get_last_holistic_path(user_id: str) -> Path:
    """Get path to last_holistic.json for a user."""
    return storage.get_user_dir(user_id) / "last_holistic.json"


def load_last_holistic_time(user_id: str) -> Optional[datetime]:
    """Load the last time holistic review ran for a user."""
    path = get_last_holistic_path(user_id)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ts = data.get("timestamp")
        if not ts:
            return None

        # Parse ISO timestamp
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    except Exception:
        return None


def save_holistic_run_time(user_id: str, timestamp: Optional[datetime] = None) -> None:
    """Save the timestamp of a holistic run."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    path = get_last_holistic_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "timestamp": timestamp.isoformat(),
        "user_id": user_id,
    }

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def should_run_holistic(user_id: str, cadence_hours: Optional[int] = None) -> bool:
    """Determine if holistic review should run for a user."""
    if cadence_hours is None:
        cadence_hours = get_cadence_hours()

    last_run = load_last_holistic_time(user_id)
    if last_run is None:
        # Never run before
        return True

    # Check if enough time has elapsed
    now = datetime.now(timezone.utc)
    elapsed = now - last_run
    threshold = timedelta(hours=cadence_hours)

    return elapsed >= threshold


def run_holistic_for_user(user_id: str) -> Dict[str, Any]:
    """
    Run holistic review for a single user.

    Returns:
        Result dict with ok status and optional error
    """
    try:
        # Load user state
        resolved, evidence, obs = storage.read_user_state(user_id)

        # Run holistic review
        report, updated_resolved, updated_evidence, updated_obs = holistic.run_holistic(
            user_id,
            loader=lambda uid: storage.read_user_state(uid),
            use_llm=False,  # LLM can be enabled separately
        )

        # Save updated state
        storage.write_user_state(user_id, updated_resolved, updated_evidence, updated_obs)

        # Record run time
        save_holistic_run_time(user_id)

        return {
            "ok": True,
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "updates_count": len(report.get("ucn_rr_updates", [])),
        }

    except Exception as e:
        return {
            "ok": False,
            "user_id": user_id,
            "error": str(e),
        }


def get_active_users() -> List[str]:
    """Get list of users that should be considered for holistic scheduling."""
    try:
        users_dir = storage.STORAGE_ROOT / "users"
        if not users_dir.exists():
            return []

        # Return all users with a resolved.json file
        active_users = []
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue

            resolved_path = user_dir / "resolved.json"
            if resolved_path.exists():
                active_users.append(user_dir.name)

        return active_users

    except Exception:
        return []


def scheduler_loop() -> None:
    """Main scheduler loop (runs in background thread)."""
    global _scheduler_running

    cadence_hours = get_cadence_hours()
    check_interval_seconds = 3600  # Check every hour

    print(f"[HolisticScheduler] Starting with cadence: {cadence_hours} hours")

    while _scheduler_running:
        try:
            # Get users to check
            users = get_active_users()

            for user_id in users:
                if not _scheduler_running:
                    break

                # Check if holistic should run
                if should_run_holistic(user_id, cadence_hours):
                    print(f"[HolisticScheduler] Running holistic for user: {user_id}")
                    result = run_holistic_for_user(user_id)

                    if result.get("ok"):
                        print(f"[HolisticScheduler] ✓ Completed for {user_id}")
                    else:
                        print(f"[HolisticScheduler] ✗ Failed for {user_id}: {result.get('error')}")

            # Sleep until next check
            time.sleep(check_interval_seconds)

        except Exception as e:
            print(f"[HolisticScheduler] Error in loop: {e}")
            time.sleep(60)  # Sleep 1 min on error


def start_scheduler() -> bool:
    """
    Start the holistic scheduler in a background thread.

    Returns:
        True if started successfully, False otherwise
    """
    global _scheduler_thread, _scheduler_running

    if not is_enabled():
        print("[HolisticScheduler] Not enabled (set HOLISTIC_SCHEDULER_ENABLED=true)")
        return False

    with _scheduler_lock:
        if _scheduler_running:
            print("[HolisticScheduler] Already running")
            return False

        _scheduler_running = True
        _scheduler_thread = threading.Thread(
            target=scheduler_loop,
            daemon=True,
            name="HolisticScheduler",
        )
        _scheduler_thread.start()

    print("[HolisticScheduler] Started")
    return True


def stop_scheduler() -> None:
    """Stop the holistic scheduler."""
    global _scheduler_running

    with _scheduler_lock:
        if not _scheduler_running:
            return

        _scheduler_running = False

    print("[HolisticScheduler] Stopped")


def get_status() -> Dict[str, Any]:
    """Get scheduler status."""
    return {
        "enabled": is_enabled(),
        "running": _scheduler_running,
        "cadence_hours": get_cadence_hours(),
        "check_interval_seconds": 3600,
        "active_users_count": len(get_active_users()),
    }


def get_next_run_time(user_id: str) -> Optional[datetime]:
    """Get the next scheduled run time for a user."""
    last_run = load_last_holistic_time(user_id)
    if last_run is None:
        return datetime.now(timezone.utc)  # Run ASAP

    cadence_hours = get_cadence_hours()
    return last_run + timedelta(hours=cadence_hours)


__all__ = [
    "get_cadence_hours",
    "is_enabled",
    "should_run_holistic",
    "run_holistic_for_user",
    "start_scheduler",
    "stop_scheduler",
    "get_status",
    "get_next_run_time",
]
