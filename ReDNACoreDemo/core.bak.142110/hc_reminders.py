"""
Head Coach Reminders System
============================

Minimal reminder broker that schedules future actions and converts them
to tasks when due.

Reminder Schema:
{
  "id": "uuid",
  "title": "Human-readable title",
  "when_iso": "2025-10-05T14:00:00Z",
  "action": "add_evidence | import_photo | re_render | morning_snapshot | end_of_day_recap",
  "args": {...},
  "created_ts": "ISO8601",
  "completed_ts": "ISO8601 or null",
  "cancelled_ts": "ISO8601 or null"
}

Lifecycle:
- Created → Pending (when_iso in future)
- Due (when_iso ≤ now) → tick() enqueues task → Completed
- Or manually cancelled
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class Reminders:
    """
    File-backed reminder system.

    Reminders are stored as JSON files in data/users/{user_id}/hc/reminders/
    """

    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)

    def _get_reminders_dir(self, user_id: str) -> Path:
        """Get reminders directory for user, create if needed."""
        reminders_dir = self.data_root / "users" / user_id / "hc" / "reminders"
        reminders_dir.mkdir(parents=True, exist_ok=True)
        return reminders_dir

    def _reminder_file_path(self, user_id: str, reminder_id: str) -> Path:
        """Get path to reminder file."""
        return self._get_reminders_dir(user_id) / f"{reminder_id}.json"

    def _save_reminder(self, user_id: str, reminder: Dict[str, Any]) -> None:
        """Save reminder to file."""
        reminder_file = self._reminder_file_path(user_id, reminder["id"])

        with open(reminder_file, 'w', encoding='utf-8') as f:
            json.dump(reminder, f, indent=2, ensure_ascii=False)

    def _load_reminder(self, user_id: str, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Load reminder from file."""
        reminder_file = self._reminder_file_path(user_id, reminder_id)

        if not reminder_file.exists():
            return None

        try:
            with open(reminder_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading reminder {reminder_id}: {e}")
            return None

    def add(
        self,
        user_id: str,
        title: str,
        when_iso: str,
        action: str,
        args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new reminder.

        Args:
            user_id: User identifier
            title: Human-readable reminder title
            when_iso: ISO8601 UTC timestamp when reminder should trigger
            action: Action type (add_evidence, re_render, morning_snapshot, etc.)
            args: Optional action-specific arguments

        Returns:
            Reminder dict with assigned ID
        """
        reminder_id = str(uuid4())

        # Validate when_iso is parseable
        try:
            datetime.fromisoformat(when_iso.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Invalid when_iso '{when_iso}': {e}, using current time")
            when_iso = datetime.now(timezone.utc).isoformat()

        reminder = {
            "id": reminder_id,
            "title": title,
            "when_iso": when_iso,
            "action": action,
            "args": args or {},
            "created_ts": datetime.now(timezone.utc).isoformat(),
            "completed_ts": None,
            "cancelled_ts": None
        }

        self._save_reminder(user_id, reminder)
        logger.info(f"Added reminder {reminder_id} for {user_id}: {title} at {when_iso}")

        return reminder

    def list(self, user_id: str) -> List[Dict[str, Any]]:
        """
        List all reminders for a user.

        Returns:
            List of reminders sorted by when_iso (earliest first)
        """
        reminders_dir = self._get_reminders_dir(user_id)
        reminders = []

        for reminder_file in reminders_dir.glob("*.json"):
            reminder = self._load_reminder(user_id, reminder_file.stem)
            if reminder:
                reminders.append(reminder)

        # Sort by when_iso (earliest first)
        def sort_key(r: Dict[str, Any]) -> str:
            when = r.get("when_iso", "")
            try:
                # Parse to ensure valid sorting
                dt = datetime.fromisoformat(when.replace('Z', '+00:00'))
                return dt.isoformat()
            except Exception:
                # Put invalid dates at the end
                return "9999-12-31T23:59:59+00:00"

        reminders.sort(key=sort_key)

        return reminders

    def complete(self, user_id: str, reminder_id: str) -> Optional[Dict[str, Any]]:
        """
        Mark a reminder as completed.

        Args:
            user_id: User identifier
            reminder_id: Reminder ID

        Returns:
            Updated reminder or None if not found
        """
        reminder = self._load_reminder(user_id, reminder_id)

        if not reminder:
            logger.warning(f"Reminder {reminder_id} not found for {user_id}")
            return None

        reminder["completed_ts"] = datetime.now(timezone.utc).isoformat()
        self._save_reminder(user_id, reminder)
        logger.info(f"Completed reminder {reminder_id}")

        return reminder

    def cancel(self, user_id: str, reminder_id: str) -> Optional[Dict[str, Any]]:
        """
        Cancel a reminder.

        Args:
            user_id: User identifier
            reminder_id: Reminder ID

        Returns:
            Updated reminder or None if not found
        """
        reminder = self._load_reminder(user_id, reminder_id)

        if not reminder:
            logger.warning(f"Reminder {reminder_id} not found for {user_id}")
            return None

        reminder["cancelled_ts"] = datetime.now(timezone.utc).isoformat()
        self._save_reminder(user_id, reminder)
        logger.info(f"Cancelled reminder {reminder_id}")

        return reminder

    def tick(self, user_id: str) -> Dict[str, Any]:
        """
        Process due reminders.

        Finds all reminders that are due (when_iso ≤ now, not completed/cancelled),
        enqueues them as tasks, and marks them completed.

        Args:
            user_id: User identifier

        Returns:
            {
                "executed": true/false,
                "enqueued_task_ids": [task_id, ...],
                "count": int,
                "reminders_processed": [reminder_id, ...]
            }
        """
        from .hc_task_runner import get_task_runner

        now = datetime.now(timezone.utc)
        all_reminders = self.list(user_id)

        # Find due reminders (not completed, not cancelled, when_iso ≤ now)
        due_reminders = []

        for reminder in all_reminders:
            # Skip if already completed or cancelled
            if reminder.get("completed_ts") or reminder.get("cancelled_ts"):
                continue

            # Parse when_iso
            when_iso = reminder.get("when_iso", "")
            try:
                when_dt = datetime.fromisoformat(when_iso.replace('Z', '+00:00'))
                if when_dt <= now:
                    due_reminders.append(reminder)
            except Exception as e:
                logger.warning(f"Skipping reminder {reminder.get('id')} with invalid when_iso '{when_iso}': {e}")
                continue

        if not due_reminders:
            return {
                "executed": False,
                "enqueued_task_ids": [],
                "count": 0,
                "reminders_processed": []
            }

        # Enqueue tasks for due reminders
        task_runner = get_task_runner(str(self.data_root))
        enqueued_task_ids = []
        reminders_processed = []

        for reminder in due_reminders:
            try:
                # Enqueue task
                task = task_runner.enqueue(
                    user_id=user_id,
                    title=reminder["title"],
                    action=reminder["action"],
                    args=reminder["args"],
                    eta_mins=2,
                    provenance={
                        "source": "reminder",
                        "reminder_id": reminder["id"],
                        "reason": f"Scheduled reminder at {reminder['when_iso']}"
                    }
                )

                enqueued_task_ids.append(task["id"])

                # Mark reminder as completed
                self.complete(user_id, reminder["id"])
                reminders_processed.append(reminder["id"])

                logger.info(f"Reminder {reminder['id']} → Task {task['id']}")

            except Exception as e:
                logger.error(f"Error processing reminder {reminder.get('id')}: {e}")

        return {
            "executed": True,
            "enqueued_task_ids": enqueued_task_ids,
            "count": len(enqueued_task_ids),
            "reminders_processed": reminders_processed
        }

    def get_pending(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all pending reminders (not completed, not cancelled).

        Args:
            user_id: User identifier

        Returns:
            List of pending reminders sorted by when_iso
        """
        all_reminders = self.list(user_id)

        pending = [
            r for r in all_reminders
            if not r.get("completed_ts") and not r.get("cancelled_ts")
        ]

        return pending

    def get_due_count(self, user_id: str) -> int:
        """
        Get count of due reminders.

        Args:
            user_id: User identifier

        Returns:
            Count of reminders due now
        """
        now = datetime.now(timezone.utc)
        pending = self.get_pending(user_id)
        due_count = 0

        for reminder in pending:
            when_iso = reminder.get("when_iso", "")
            try:
                when_dt = datetime.fromisoformat(when_iso.replace('Z', '+00:00'))
                if when_dt <= now:
                    due_count += 1
            except Exception:
                continue

        return due_count


# Singleton instance
_reminders = None

def get_reminders(data_root: str = "data") -> Reminders:
    """Get singleton reminders instance."""
    global _reminders
    if _reminders is None:
        _reminders = Reminders(data_root)
    return _reminders
