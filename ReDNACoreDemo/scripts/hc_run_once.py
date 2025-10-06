#!/usr/bin/env python3
"""
Head Coach CLI Runner
=====================

Run one tick of HC task/reminder processing for a user.

Usage:
    python scripts/hc_run_once.py --user alice
    python scripts/hc_run_once.py --user alice --reminders-only
    python scripts/hc_run_once.py --user alice --tasks-only
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ReDNACoreDemo.core.hc_task_runner import get_task_runner
from ReDNACoreDemo.core.hc_reminders import get_reminders


def main():
    parser = argparse.ArgumentParser(description="HC CLI Runner")
    parser.add_argument("--user", required=True, help="User ID")
    parser.add_argument("--reminders-only", action="store_true", help="Process reminders only")
    parser.add_argument("--tasks-only", action="store_true", help="Process tasks only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    user_id = args.user
    results = {}

    print(f"HC Runner for user: {user_id}")
    print("=" * 60)

    # Process reminders
    if not args.tasks_only:
        print("\n[1/2] Processing reminders...")
        reminders = get_reminders()
        reminder_result = reminders.tick(user_id)

        results["reminders"] = reminder_result

        if reminder_result.get("executed"):
            print(f"  ✓ Processed {reminder_result['count']} due reminder(s)")
            print(f"  ✓ Enqueued {len(reminder_result['enqueued_task_ids'])} task(s)")
            if args.verbose:
                print(f"    Task IDs: {reminder_result['enqueued_task_ids']}")
        else:
            print(f"  • No due reminders")

    # Process tasks
    if not args.reminders_only:
        print("\n[2/2] Processing tasks...")
        runner = get_task_runner()
        task_result = runner.tick(user_id)

        results["tasks"] = task_result

        if task_result.get("executed"):
            task = task_result.get("task", {})
            print(f"  ✓ Executed task: {task.get('title', 'Unknown')}")
            print(f"    Action: {task.get('action')}")
            print(f"    State: {task.get('state')}")

            if "error" in task_result:
                print(f"    ❌ Error: {task_result['error']}")
            elif "result" in task_result:
                if args.verbose:
                    print(f"    Result: {json.dumps(task_result['result'], indent=2)}")
        else:
            reason = task_result.get("reason", "Unknown")
            print(f"  • {reason}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Reminders processed: {results.get('reminders', {}).get('count', 0)}")
    print(f"  Tasks executed: {'1' if results.get('tasks', {}).get('executed') else '0'}")

    if args.verbose:
        print("\nFull Results:")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
