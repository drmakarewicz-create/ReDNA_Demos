"""
Head Coach Task Runner
======================

Lightweight, file-backed task queue system for autonomous execution.

Task Schema:
{
  "id": "uuid",
  "title": "Human-readable title",
  "action": "add_evidence | import_photo | re_render | custom",
  "args": {...},
  "state": "queued | running | done | failed | snoozed",
  "priority": "low | normal | high",
  "created_ts": "ISO8601",
  "updated_ts": "ISO8601",
  "eta_mins": 2,
  "provenance": {"source_coach": "...", "reason": "..."},
  "error": "Optional error message if failed"
}

Task States:
- queued: Ready to execute
- running: Currently executing
- done: Successfully completed
- failed: Execution failed (with error message)
- snoozed: Temporarily paused (will return to queued later)
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskRunner:
    """
    File-backed task queue and runner.

    Tasks are stored as JSON files in data/users/{user_id}/hc/tasks/
    """

    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)

    def _get_tasks_dir(self, user_id: str) -> Path:
        """Get tasks directory for user, create if needed."""
        tasks_dir = self.data_root / "users" / user_id / "hc" / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        return tasks_dir

    def _task_file_path(self, user_id: str, task_id: str) -> Path:
        """Get path to task file."""
        return self._get_tasks_dir(user_id) / f"{task_id}.json"

    def _save_task(self, user_id: str, task: Dict[str, Any]) -> None:
        """Save task to file."""
        task["updated_ts"] = datetime.now(timezone.utc).isoformat()
        task_file = self._task_file_path(user_id, task["id"])

        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task, f, indent=2, ensure_ascii=False)

    def _load_task(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Load task from file."""
        task_file = self._task_file_path(user_id, task_id)

        if not task_file.exists():
            return None

        with open(task_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def enqueue(
        self,
        user_id: str,
        title: str,
        action: str,
        args: Dict[str, Any],
        eta_mins: int = 2,
        provenance: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Enqueue a new task.

        Args:
            user_id: User identifier
            title: Human-readable task title
            action: Task action type (add_evidence, import_photo, etc.)
            args: Task-specific arguments
            eta_mins: Estimated time in minutes
            provenance: Source and reason for the task
            priority: Task priority (low, normal, high) - default: normal

        Returns:
            Task dict with assigned ID
        """
        task_id = str(uuid4())

        task = {
            "id": task_id,
            "title": title,
            "action": action,
            "args": args,
            "state": "queued",
            "priority": priority if priority in ["low", "normal", "high"] else "normal",
            "created_ts": datetime.now(timezone.utc).isoformat(),
            "updated_ts": datetime.now(timezone.utc).isoformat(),
            "eta_mins": eta_mins,
            "provenance": provenance or {}
        }

        self._save_task(user_id, task)
        logger.info(f"Enqueued task {task_id} for {user_id}: {title} (priority: {task['priority']})")

        return task

    def get_task(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task."""
        return self._load_task(user_id, task_id)

    def list_tasks(
        self,
        user_id: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List tasks for a user.

        Args:
            user_id: User identifier
            state: Optional state filter (queued, running, done, failed, snoozed)

        Returns:
            List of tasks sorted by created_ts (oldest first)
        """
        tasks_dir = self._get_tasks_dir(user_id)
        tasks = []

        for task_file in tasks_dir.glob("*.json"):
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    task = json.load(f)

                    # Filter by state if specified
                    if state is None or task.get("state") == state:
                        tasks.append(task)
            except Exception as e:
                logger.error(f"Error loading task {task_file}: {e}")

        # Sort by created_ts (oldest first)
        tasks.sort(key=lambda t: t.get("created_ts", ""))

        return tasks

    def update_state(
        self,
        user_id: str,
        task_id: str,
        new_state: str,
        error: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update task state.

        Args:
            user_id: User identifier
            task_id: Task ID
            new_state: New state (queued, running, done, failed, snoozed)
            error: Optional error message if new_state is "failed"

        Returns:
            Updated task or None if not found
        """
        task = self._load_task(user_id, task_id)

        if not task:
            logger.warning(f"Task {task_id} not found for {user_id}")
            return None

        old_state = task.get("state")
        task["state"] = new_state

        if error:
            task["error"] = error
        elif "error" in task:
            # Clear error if transitioning away from failed
            if old_state == "failed" and new_state != "failed":
                del task["error"]

        self._save_task(user_id, task)
        logger.info(f"Task {task_id} state: {old_state} → {new_state}")

        return task

    def tick(self, user_id: str) -> Dict[str, Any]:
        """
        Run one safe execution step.

        Finds the highest priority queued task and attempts to execute it.
        Priority order: high > normal > low. Within same priority, oldest first.

        Args:
            user_id: User identifier

        Returns:
            {
                "executed": true/false,
                "task": task dict if executed,
                "reason": string if not executed
            }
        """
        # Get all queued tasks
        queued_tasks = self.list_tasks(user_id, state="queued")

        if not queued_tasks:
            return {
                "executed": False,
                "reason": "No queued tasks"
            }

        # Sort by priority (high > normal > low), then by created_ts (oldest first)
        priority_order = {"high": 0, "normal": 1, "low": 2}

        def task_sort_key(t):
            priority = t.get("priority", "normal")
            priority_rank = priority_order.get(priority, 1)
            created_ts = t.get("created_ts", "")
            return (priority_rank, created_ts)

        queued_tasks.sort(key=task_sort_key)

        task = queued_tasks[0]
        task_id = task["id"]

        # Mark as running
        self.update_state(user_id, task_id, "running")

        try:
            # Execute task based on action
            result = self._execute_task(user_id, task)

            # Mark as done
            self.update_state(user_id, task_id, "done")

            return {
                "executed": True,
                "task": task,
                "result": result
            }

        except Exception as e:
            # Mark as failed
            error_msg = str(e)
            self.update_state(user_id, task_id, "failed", error=error_msg)
            logger.error(f"Task {task_id} failed: {error_msg}")

            return {
                "executed": True,
                "task": task,
                "error": error_msg
            }

    def _execute_task(self, user_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task.

        This is a stub that will be expanded based on action type.
        For v2 Sprint 1, we support basic actions.

        Args:
            user_id: User identifier
            task: Task dict

        Returns:
            Execution result dict
        """
        action = task.get("action")
        args = task.get("args", {})

        if action == "add_evidence":
            # Real implementation: Create a journal entry to prompt user
            trait = args.get("trait")
            logger.info(f"Task: add_evidence for {trait}")

            # Import here to avoid circular dependency
            from .storage import read_user_state

            # Get current trait value for context (handle missing state gracefully)
            current_value = "unknown"
            curiosity = 0
            try:
                resolved, evidence, obs = read_user_state(user_id)
                trait_data = resolved.get(trait, {})
                current_value = trait_data.get("resolved_value", "unknown")
                curiosity = trait_data.get("curiosity", 0)
            except Exception as e:
                logger.warning(f"Could not read user state for {user_id}: {e}. Using defaults.")

            # Create journal entry prompting for evidence
            from datetime import datetime, timezone
            from pathlib import Path
            import json

            user_dir = Path(self.data_root) / "users" / user_id
            journal_dir = user_dir / "hc" / "conversation"
            journal_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{date_str}.jsonl"

            # Merge provenance with task_runner source
            provenance = {"source": "task_runner"}
            if task.get("provenance"):
                provenance.update(task["provenance"])

            entry = {
                "ts": now.isoformat(),
                "role": "assistant",
                "content": f"I need your help with {trait.split('.')[-1]}. Current value: {current_value} (curiosity: {int(curiosity)}). Can you provide evidence to reduce uncertainty?",
                "task_id": task["id"],
                "provenance": provenance
            }

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "message": f"Evidence request for {trait} logged to conversation",
                "journal_entry": entry["ts"],
                "trait": trait,
                "current_value": current_value
            }

        elif action == "import_photo":
            # Real implementation: Log photo import request
            photo_path = args.get("photo_path")
            logger.info(f"Task: import_photo {photo_path}")

            # In a full implementation, this would trigger Photo Coach extraction
            # For now, log to conversation
            from datetime import datetime, timezone
            from pathlib import Path
            import json

            user_dir = Path(self.data_root) / "users" / user_id
            journal_dir = user_dir / "hc" / "conversation"
            journal_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{date_str}.jsonl"

            entry = {
                "ts": now.isoformat(),
                "role": "assistant",
                "content": f"Ready to process photo: {photo_path}. Please upload via Photo Coach.",
                "task_id": task["id"]
            }

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "message": f"Photo import request logged",
                "photo_path": photo_path,
                "next_step": "Upload via Photo Coach"
            }

        elif action == "re_render":
            # Real implementation: Log re-render request
            logger.info("Task: re_render portrait")

            from datetime import datetime, timezone
            from pathlib import Path
            import json

            user_dir = Path(self.data_root) / "users" / user_id
            journal_dir = user_dir / "hc" / "conversation"
            journal_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{date_str}.jsonl"

            entry = {
                "ts": now.isoformat(),
                "role": "assistant",
                "content": "Your traits have been updated! Ready to re-render your portrait. Head to Rendering Coach to generate a new image.",
                "task_id": task["id"]
            }

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "message": "Portrait re-render request logged",
                "next_step": "Use Rendering Coach"
            }

        elif action == "morning_snapshot":
            # Real implementation: Generate morning snapshot
            logger.info("Task: morning_snapshot")

            from .storage import read_user_state
            from datetime import datetime, timezone
            from pathlib import Path
            import json

            # Get top 5 traits by curiosity
            resolved, evidence, obs = read_user_state(user_id)

            traits_by_curiosity = sorted(
                [(trait_id, data.get("curiosity", 0)) for trait_id, data in resolved.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]

            snapshot_text = "Good morning! Here's your trait snapshot:\n\n"
            for trait_id, curiosity in traits_by_curiosity:
                trait_name = trait_id.split('.')[-1]
                snapshot_text += f"• {trait_name}: curiosity {int(curiosity)}\n"

            # Log to conversation
            user_dir = Path(self.data_root) / "users" / user_id
            journal_dir = user_dir / "hc" / "conversation"
            journal_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{date_str}.jsonl"

            entry = {
                "ts": now.isoformat(),
                "role": "assistant",
                "content": snapshot_text,
                "task_id": task["id"],
                "snapshot_type": "morning"
            }

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "message": "Morning snapshot generated",
                "traits_count": len(traits_by_curiosity),
                "snapshot": snapshot_text
            }

        elif action == "end_of_day_recap":
            # Real implementation: Generate end-of-day recap
            logger.info("Task: end_of_day_recap")

            from .storage import read_user_state
            from .events import list_checkpoints
            from datetime import datetime, timezone
            from pathlib import Path
            import json

            # Get today's checkpoints
            checkpoints = list_checkpoints(user_id)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_checkpoints = [cp for cp in checkpoints if today in cp]

            recap_text = "End of day recap:\n\n"
            recap_text += f"• {len(today_checkpoints)} updates today\n"
            recap_text += "• Keep up the momentum tomorrow!\n"

            # Log to conversation
            user_dir = Path(self.data_root) / "users" / user_id
            journal_dir = user_dir / "hc" / "conversation"
            journal_dir.mkdir(parents=True, exist_ok=True)

            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            journal_file = journal_dir / f"{date_str}.jsonl"

            entry = {
                "ts": now.isoformat(),
                "role": "assistant",
                "content": recap_text,
                "task_id": task["id"],
                "recap_type": "end_of_day"
            }

            with open(journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

            return {
                "message": "End-of-day recap generated",
                "checkpoints_today": len(today_checkpoints),
                "recap": recap_text
            }

        else:
            # Unknown action
            raise ValueError(f"Unknown action: {action}")

    def snooze(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Snooze a task (pause temporarily).

        Args:
            user_id: User identifier
            task_id: Task ID

        Returns:
            Updated task or None
        """
        return self.update_state(user_id, task_id, "snoozed")

    def unsnooze(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Unsnooze a task (return to queued).

        Args:
            user_id: User identifier
            task_id: Task ID

        Returns:
            Updated task or None
        """
        return self.update_state(user_id, task_id, "queued")

    def delete_task(self, user_id: str, task_id: str) -> bool:
        """
        Delete a task permanently.

        Args:
            user_id: User identifier
            task_id: Task ID

        Returns:
            True if deleted, False if not found
        """
        task_file = self._task_file_path(user_id, task_id)

        if not task_file.exists():
            return False

        task_file.unlink()
        logger.info(f"Deleted task {task_id} for {user_id}")
        return True


# Singleton instance
_task_runner = None

def get_task_runner(data_root: str = "data") -> TaskRunner:
    """Get singleton task runner instance."""
    global _task_runner
    if _task_runner is None:
        _task_runner = TaskRunner(data_root)
    return _task_runner
