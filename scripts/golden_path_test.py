#!/usr/bin/env python3
"""
Golden-path regression test script.

Tests the complete nudge workflow:
1. Enqueue a nudge
2. Accept the nudge
3. Verify it appears in Draft Chat
4. Undo the acceptance
5. Verify it's back in inbox

This script validates the entire user-facing nudge lifecycle.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

# Import required modules
from ExplorerFinal.core import nudge_store


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_step(step_num: int, description: str) -> None:
    """Print a test step."""
    print(f"{Colors.OKCYAN}[Step {step_num}]{Colors.ENDC} {description}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def print_info(msg: str) -> None:
    """Print an info message."""
    print(f"{Colors.OKBLUE}ℹ {msg}{Colors.ENDC}")


def check_write_protect() -> bool:
    """Check if WRITE_PROTECT is enabled."""
    write_protect_env = os.getenv("WRITE_PROTECT", "").strip().lower()
    write_protect = write_protect_env in {"true", "1", "yes", "on"}

    if write_protect:
        print_warning("WRITE_PROTECT is enabled - running in dry-run mode")
        print_info("Set WRITE_PROTECT=false to persist changes to disk")
    else:
        print_info("WRITE_PROTECT is disabled - changes will persist to disk")

    return write_protect


def create_test_nudge() -> Dict[str, Any]:
    """Create a test nudge payload."""
    return {
        "persona_id": "golden_path_test",
        "mode": "test",
        "tone_meta": "testing",
        "items": [
            {
                "container": "TestContainer",
                "trait_id": "test_trait",
                "text": "This is a golden-path regression test nudge.",
                "template_source": "test_template",
            }
        ],
        "provenance": {
            "source": "golden_path_test",
            "timestamp": time.time(),
        },
        "ttl_minutes": 1440,
        "snapshot_id": "golden_path_test",
    }


def run_golden_path_test(user_id: str = "test_user_golden_path") -> bool:
    """
    Run the complete golden path test.

    Returns:
        True if all tests pass, False otherwise
    """
    write_protect = check_write_protect()
    all_passed = True

    try:
        # Step 1: Enqueue a nudge
        print_step(1, "Enqueue a test nudge")
        payload = create_test_nudge()

        result = nudge_store.add_bundle(user_id, payload, write_protect=write_protect)

        if result.get("duplicate"):
            print_warning("Duplicate nudge detected - clearing inbox first")
            # Clear the existing nudge
            inbox = nudge_store.list_inbox(user_id, write_protect=write_protect)
            for item in inbox:
                nudge_store.dismiss(user_id, item["id"], write_protect=write_protect)

            # Try again
            result = nudge_store.add_bundle(user_id, payload, write_protect=write_protect)

        if not result.get("bundle"):
            print_error("Failed to enqueue nudge")
            return False

        nudge_id = result["bundle"]["id"]
        print_success(f"Nudge enqueued: {nudge_id}")

        # Step 2: Verify nudge is in inbox
        print_step(2, "Verify nudge appears in inbox")
        inbox = nudge_store.list_inbox(user_id, status_filter="inbox", write_protect=write_protect)

        if not any(item["id"] == nudge_id for item in inbox):
            print_error(f"Nudge {nudge_id} not found in inbox")
            all_passed = False
        else:
            print_success(f"Nudge found in inbox (status: {inbox[0]['status']})")

        # Step 3: Accept the nudge
        print_step(3, "Accept the nudge and deliver to Draft Chat")
        accept_result = nudge_store.accept(
            user_id,
            nudge_id,
            write_protect=write_protect,
            deliver_to_chat=True,
        )

        if not accept_result.get("ok"):
            print_error(f"Failed to accept nudge: {accept_result.get('error')}")
            all_passed = False
        else:
            chat_entry_ids = accept_result.get("chat_entry_ids", [])
            print_success(f"Nudge accepted ({len(chat_entry_ids)} chat entries created)")

        # Step 4: Verify nudge status changed to 'accepted'
        print_step(4, "Verify nudge status changed to 'accepted'")
        inbox = nudge_store.list_inbox(user_id, status_filter="accepted", write_protect=write_protect)

        accepted_nudge = next((item for item in inbox if item["id"] == nudge_id), None)
        if not accepted_nudge:
            print_error("Nudge not found with 'accepted' status")
            all_passed = False
        else:
            print_success(f"Nudge status: {accepted_nudge['status']}")

        # Step 5: Verify entries in Draft Chat
        print_step(5, "Verify nudge appears in Draft Chat")
        draft_chat = nudge_store.get_draft_chat(user_id, write_protect=write_protect)

        nudge_chat_entries = [msg for msg in draft_chat if msg.get("nudge_id") == nudge_id]
        if not nudge_chat_entries:
            print_error("No Draft Chat entries found for nudge")
            all_passed = False
        else:
            print_success(f"Found {len(nudge_chat_entries)} Draft Chat entries")

        # Step 6: Undo the acceptance
        print_step(6, "Undo the nudge acceptance")
        undo_result = nudge_store.undo(
            user_id,
            nudge_id,
            write_protect=write_protect,
            deliver_to_chat=True,
        )

        if not undo_result.get("ok"):
            print_error(f"Failed to undo nudge: {undo_result.get('error')}")
            all_passed = False
        else:
            print_success("Nudge acceptance undone")

        # Step 7: Verify nudge is back in inbox
        print_step(7, "Verify nudge is back in inbox")
        inbox = nudge_store.list_inbox(user_id, status_filter="inbox", write_protect=write_protect)

        inbox_nudge = next((item for item in inbox if item["id"] == nudge_id), None)
        if not inbox_nudge:
            print_error("Nudge not found in inbox after undo")
            all_passed = False
        else:
            print_success(f"Nudge back in inbox (status: {inbox_nudge['status']})")

        # Step 8: Verify Draft Chat entries were removed
        print_step(8, "Verify Draft Chat entries were removed")
        draft_chat = nudge_store.get_draft_chat(user_id, write_protect=write_protect)

        remaining_entries = [msg for msg in draft_chat if msg.get("nudge_id") == nudge_id]
        if remaining_entries:
            print_error(f"Draft Chat still contains {len(remaining_entries)} entries")
            all_passed = False
        else:
            print_success("Draft Chat entries successfully removed")

        # Step 9: Cleanup - dismiss the test nudge
        print_step(9, "Cleanup - dismiss test nudge")
        dismiss_result = nudge_store.dismiss(user_id, nudge_id, write_protect=write_protect)

        if not dismiss_result.get("ok"):
            print_warning(f"Failed to dismiss test nudge: {dismiss_result.get('error')}")
        else:
            print_success("Test nudge dismissed")

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def run_feedback_test(user_id: str = "test_user_feedback") -> bool:
    """Test feedback logging workflow."""
    print_header("Feedback Logging Test")

    write_protect = check_write_protect()
    all_passed = True

    try:
        # Create and enqueue a nudge
        print_step(1, "Create test nudge for feedback")
        payload = create_test_nudge()
        result = nudge_store.add_bundle(user_id, payload, write_protect=write_protect)
        nudge_id = result["bundle"]["id"]
        print_success(f"Nudge created: {nudge_id}")

        # Log helpful feedback
        print_step(2, "Log helpful feedback")
        feedback_result = nudge_store.log_feedback(
            user_id=user_id,
            nudge_id=nudge_id,
            persona_id="test_persona",
            rating="helpful",
            note="This is a helpful test",
            traits=[{"container": "TestContainer", "trait_id": "test_trait"}],
            write_protect=write_protect,
        )

        if not feedback_result.get("ok"):
            print_error("Failed to log helpful feedback")
            all_passed = False
        else:
            print_success("Helpful feedback logged")

        # Log not_helpful feedback
        print_step(3, "Log not_helpful feedback")
        feedback_result = nudge_store.log_feedback(
            user_id=user_id,
            nudge_id=f"{nudge_id}_2",
            persona_id="test_persona",
            rating="not_helpful",
            note="This is not helpful",
            traits=[{"container": "TestContainer", "trait_id": "test_trait"}],
            write_protect=write_protect,
        )

        if not feedback_result.get("ok"):
            print_error("Failed to log not_helpful feedback")
            all_passed = False
        else:
            print_success("Not helpful feedback logged")

        # Load feedback entries
        print_step(4, "Load feedback entries")
        entries = nudge_store.load_feedback_entries(
            user_id=user_id,
            write_protect=write_protect,
        )

        if len(entries) < 2:
            print_error(f"Expected at least 2 feedback entries, got {len(entries)}")
            all_passed = False
        else:
            print_success(f"Loaded {len(entries)} feedback entries")

        # Load feedback aggregates
        print_step(5, "Load feedback aggregates")
        aggregates = nudge_store.load_feedback_aggregates(
            user_id=user_id,
            write_protect=write_protect,
        )

        trait_path = "TestContainer.test_trait"
        if trait_path not in aggregates:
            print_error(f"No aggregates found for {trait_path}")
            all_passed = False
        else:
            agg = aggregates[trait_path]
            print_success(
                f"Aggregates: helpful={agg['helpful']}, not_helpful={agg['not_helpful']}, "
                f"score={agg['score']:.2f}"
            )

        # Cleanup
        print_step(6, "Cleanup")
        nudge_store.dismiss(user_id, nudge_id, write_protect=write_protect)
        print_success("Cleanup complete")

    except Exception as e:
        print_error(f"Feedback test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return all_passed


def main() -> int:
    """Main entry point."""
    print_header("ReDNA Golden Path Regression Test Suite")

    print_info(f"Repo root: {REPO_ROOT}")
    print_info(f"Mailbox root: {nudge_store.MAILBOX_ROOT}")
    print_info(f"Logs root: {nudge_store.LOGS_ROOT}")

    # Run golden path test
    print_header("Golden Path Test: Enqueue → Accept → Undo → Draft Chat")
    golden_path_passed = run_golden_path_test()

    # Run feedback test
    feedback_passed = run_feedback_test()

    # Print final summary
    print_header("Test Summary")

    if golden_path_passed:
        print_success("Golden Path Test: PASSED")
    else:
        print_error("Golden Path Test: FAILED")

    if feedback_passed:
        print_success("Feedback Test: PASSED")
    else:
        print_error("Feedback Test: FAILED")

    all_passed = golden_path_passed and feedback_passed

    if all_passed:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}All tests PASSED ✓{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}Some tests FAILED ✗{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
