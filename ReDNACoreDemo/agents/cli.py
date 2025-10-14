from __future__ import annotations

"""
Command-line helpers for managing Head Coach agents.

Examples:
    python3 -m ReDNACoreDemo.agents.cli --user USER1 --status
    python3 -m ReDNACoreDemo.agents.cli --user USER1 --run-once
"""

import argparse
import json
from typing import Any, Dict, Optional, Sequence

from ReDNACoreDemo import agents
from ReDNACoreDemo.core.agent_daemon import AgentDaemon


def _summarize_mailbox(mailbox: agents.AgentMailbox) -> Dict[str, Any]:
    inbox_entries, inbox_index = mailbox.read_inbox(start_index=0)
    outbox_entries, outbox_index = mailbox.read_outbox(start_index=0)
    return {
        "inbox_count": inbox_index,
        "outbox_count": outbox_index,
        "recent_inbox": inbox_entries[-5:],
        "recent_outbox": outbox_entries[-5:],
    }


def handle_status(user_id: str) -> Dict[str, Any]:
    record = agents.ensure_agent_record(user_id)
    policy = agents.get_agent_policy(user_id)
    state_store = agents.AgentStateStore(user_id)
    state = state_store.load()
    mailbox = agents.AgentMailbox(user_id)
    mailbox_summary = _summarize_mailbox(mailbox)
    return {
        "user_id": record.user_id,
        "agent_id": record.agent_id,
        "status": record.status,
        "autonomy": policy.autonomy,
        "quotas": policy.quotas,
        "permissions": policy.permissions,
        "state": state.to_dict(),
        "mailbox": mailbox_summary,
    }


def update_autonomy(user_id: str, autonomy: str) -> Dict[str, Any]:
    policy = agents.update_agent_policy(user_id, {"autonomy": autonomy})
    agents.update_agent_record(user_id, {"autonomy": autonomy})
    return {"user_id": user_id, "agent_id": f"hc_{user_id}", "autonomy": policy.autonomy}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent registry and daemon helpers")
    parser.add_argument("--user", required=True, help="Target user ID")
    parser.add_argument("--status", action="store_true", help="Print current agent status summary")
    parser.add_argument("--run-once", action="store_true", help="Invoke agent daemon once")
    parser.add_argument("--set-autonomy", choices=["propose", "semi", "auto"], help="Update autonomy level")
    parser.add_argument("--quota", type=int, help="Override jobs per day quota")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    user_id = args.user

    results: Dict[str, Any] = {"user_id": user_id}

    if args.set_autonomy:
        results["autonomy"] = update_autonomy(user_id, args.set_autonomy)["autonomy"]

    if args.quota is not None:
        policy = agents.update_agent_policy(user_id, {"quotas": {"jobs_per_day": args.quota}})
        agents.update_agent_record(user_id, {"quotas": {"jobs_per_day": args.quota}})
        results["quota"] = policy.quotas.get("jobs_per_day")

    if args.run_once:
        summary = AgentDaemon().run_once(user_id)
        results["run"] = summary

    if args.status or (not args.run_once and not args.set_autonomy and args.quota is None):
        # Default to status if no other action was requested.
        results["status"] = handle_status(user_id)

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    main()
