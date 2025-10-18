#!/usr/bin/env python3
"""
Tier-2 Trait Verification Script

Automates a targeted verification loop for env-gated Tier-2 promotions.

Workflow per trait:
1. Enable the env toggle and set RR gate to default.
2. Restart Core to pick up new settings.
3. Run up to --limit positive samples against /core/api/ingest_text.
4. If a sample fails with trait_not_found, bump the RR gate once (+rr_bump)
   and retry that sample (recording the outcome).
5. Append a summary entry to docs/reports/tier2_verify_summary.md.

Usage:
    python scripts/tier2_verify.py --trait CHRONO [--limit 3] [--rr-bump 40]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"
REPORT_FILE = PROJECT_ROOT / "docs" / "reports" / "tier2_verify_summary.md"
CORE_PID_FILE = PROJECT_ROOT / ".core_pid"

CORE_BASE = os.getenv("CORE_BASE", "http://127.0.0.1:8004")


@dataclass
class TraitConfig:
    code: str
    env_toggle: str
    env_rr: str
    default_rr: float
    samples: List[Tuple[str, str]]
    expected_trait_id: str


TRAITS: Dict[str, TraitConfig] = {
    "CHRONO": TraitConfig(
        code="CHRONO",
        env_toggle="PROMOTE_ENABLE_CHRONO",
        env_rr="RR_PROMOTE_MIN_CHRONO",
        default_rr=780.0,
        expected_trait_id="BehaviorDNA.Sleep.Chronotype",
        samples=[
            ("I'm a morning person, up before sunrise every weekday.", "morning"),
            ("Total night owl, usually in bed after midnight.", "evening"),
            ("Early riser here, up by 5 even on weekends.", "morning"),
        ],
    ),
    "DIET": TraitConfig(
        code="DIET",
        env_toggle="PROMOTE_ENABLE_DIET",
        env_rr="RR_PROMOTE_MIN_DIET",
        default_rr=780.0,
        expected_trait_id="BehaviorDNA.Health.Diet",
        samples=[
            ("I don't eat meat at all—strictly vegetarian.", "vegetarian"),
            ("Vegan meals only, no exceptions.", "vegan"),
            ("Gluten-free diet keeps my energy steady.", "gluten_free"),
        ],
    ),
    "WORKLOC": TraitConfig(
        code="WORKLOC",
        env_toggle="PROMOTE_ENABLE_WORKLOC",
        env_rr="RR_PROMOTE_MIN_WORKLOC",
        default_rr=800.0,
        expected_trait_id="BehaviorDNA.Work.Location",
        samples=[
            ("I work from home full time in a remote role.", "remote"),
            ("My job is onsite in the office every day.", "onsite"),
            ("We're hybrid now—two days in the office, rest remote.", "hybrid"),
        ],
    ),
    "GROUPSIZE": TraitConfig(
        code="GROUPSIZE",
        env_toggle="PROMOTE_ENABLE_GROUPSIZE",
        env_rr="RR_PROMOTE_MIN_GROUPSIZE",
        default_rr=800.0,
        expected_trait_id="PreferenceDNA.Social.GroupSize",
        samples=[
            ("Quiet weekend plans, I prefer small group dinners.", "small"),
            ("I love big parties and the energy of large crowds.", "large"),
            ("Small group chats are my comfort zone.", "small"),
        ],
    ),
    "EXERCISE_TYPE": TraitConfig(
        code="EXERCISE_TYPE",
        env_toggle="PROMOTE_ENABLE_EXERCISE_TYPE",
        env_rr="RR_PROMOTE_MIN_EXERCISE_TYPE",
        default_rr=800.0,
        expected_trait_id="BehaviorDNA.Exercise.Type",
        samples=[
            ("I run every morning before work; running is my therapy.", "running"),
            ("I swim laps whenever the pool opens.", "swimming"),
            ("Evening yoga sessions keep me calm.", "yoga"),
        ],
    ),
}


def read_env_file() -> Dict[str, str]:
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env not found at {ENV_FILE}")

    env_vars: Dict[str, str] = {}
    with ENV_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            env_vars[key.strip()] = value.strip()
    return env_vars


def write_env_file(replacements: Dict[str, str]) -> None:
    lines: List[str] = []
    remaining = dict(replacements)

    with ENV_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                lines.append(line)
                continue

            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                lines.append(f"{key}={remaining.pop(key)}\n")
            else:
                lines.append(line)

    for key, value in remaining.items():
        lines.append(f"{key}={value}\n")

    with ENV_FILE.open("w", encoding="utf-8") as handle:
        handle.writelines(lines)


def restart_core() -> bool:
    print("  Restarting Core service...")

    if CORE_PID_FILE.exists():
        try:
            pid = int(CORE_PID_FILE.read_text().strip())
            os.kill(pid, 15)
            time.sleep(2)
        except (ValueError, ProcessLookupError):
            pass

    try:
        proc = subprocess.Popen(
            ["python3", "-m", "ReDNACoreDemo.core.api"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=PROJECT_ROOT,
        )
        CORE_PID_FILE.write_text(str(proc.pid))

        for _ in range(30):
            try:
                resp = requests.get(f"{CORE_BASE}/health", timeout=2)
                if resp.status_code == 200:
                    print("  Core ready.")
                    return True
            except requests.RequestException:
                pass
            time.sleep(1)

        print("  Warning: Core did not report healthy within 30s.")
        return False
    except Exception as exc:
        print(f"  Error restarting Core: {exc}")
        return False


def run_sample(trait: TraitConfig, text: str, expected: str) -> Tuple[bool, str]:
    user_id = f"tier2_verify_{trait.code.lower()}_{int(time.time())}"
    try:
        resp = requests.post(
            f"{CORE_BASE}/core/api/ingest_text",
            json={
                "user_id": user_id,
                "text": text,
                "source": "tier2_verify",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        return False, f"http_error:{exc}"

    if resp.status_code != 200:
        return False, f"http_{resp.status_code}"

    time.sleep(2)

    try:
        snapshot_resp = requests.get(f"{CORE_BASE}/users/{user_id}/snapshot", timeout=10)
        if snapshot_resp.status_code != 200:
            return False, f"snapshot_http_{snapshot_resp.status_code}"
        snapshot = snapshot_resp.json()
    except requests.RequestException as exc:
        return False, f"snapshot_error:{exc}"

    traits = snapshot.get("traits", {})
    if trait.expected_trait_id not in traits:
        return False, "trait_not_found"

    value = traits[trait.expected_trait_id].get("value")
    if value != expected:
        return False, f"unexpected_value:{value}"

    return True, value


def append_report(trait: TraitConfig, result: Dict[str, object]) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = ""
    if not REPORT_FILE.exists():
        header = "# Tier-2 Trait Verification Summary\n\n"

    lines = [
        f"## {timestamp} — {trait.code}\n",
        f"- Toggle: `{trait.env_toggle}`\n",
        f"- RR Gate Final: {result['rr_gate']}\n",
        f"- RR Bump Used: {'yes' if result['bumped'] else 'no'} (+{result['rr_bump']} if yes)\n",
        f"- Samples Run: {result['samples_run']}\n",
        f"- Precision: {result['precision']:.1f}%\n",
        f"- Success: {'yes' if result['success'] else 'no'}\n",
        "- Attempts:\n",
    ]

    for attempt in result["attempts"]:
        status = "✓" if attempt["success"] else "✗"
        value = attempt.get("value")
        note = attempt.get("note", "")
        lines.append(
            f"  - {status} RR={attempt['rr']} text=\"{attempt['text']}\" "
            f"→ {value if value else attempt.get('error')} {note}\n"
        )

    lines.append("\n")

    with REPORT_FILE.open("a", encoding="utf-8") as handle:
        if header:
            handle.write(header)
        handle.writelines(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tier-2 verification helper")
    parser.add_argument("--trait", required=True, choices=TRAITS.keys(), help="Trait code to verify")
    parser.add_argument("--limit", type=int, default=3, help="Number of samples to run (default 3)")
    parser.add_argument("--rr-bump", type=float, default=40.0, help="RR bump applied on failure")
    args = parser.parse_args()

    trait = TRAITS[args.trait]
    limit = max(1, min(args.limit, len(trait.samples)))
    rr_bump = args.rr_bump

    env_vars = read_env_file()
    original_toggle = env_vars.get(trait.env_toggle, "false")
    original_rr = env_vars.get(trait.env_rr, str(trait.default_rr))

    attempts: List[Dict[str, object]] = []
    successes = 0
    bumped = False
    current_rr = trait.default_rr
    samples_processed = 0

    try:
        env_vars[trait.env_toggle] = "true"
        env_vars[trait.env_rr] = str(trait.default_rr)
        write_env_file(env_vars)

        if not restart_core():
            print("Core restart failed. Aborting.")
            return

        for text, expected in trait.samples[:limit]:
            samples_processed += 1
            success, info = run_sample(trait, text, expected)
            attempt_record: Dict[str, object] = {
                "text": text,
                "expected": expected,
                "rr": current_rr,
                "success": success,
            }
            if success:
                attempt_record["value"] = info
                successes += 1
            else:
                attempt_record["error"] = info

            attempts.append(attempt_record)

            if success or info != "trait_not_found" or bumped:
                continue

            # Apply bump and retry once
            bumped = True
            current_rr = trait.default_rr + rr_bump
            env_vars[trait.env_rr] = str(current_rr)
            write_env_file(env_vars)

            if not restart_core():
                attempt_record["note"] = "core_restart_failed_after_bump"
                break

            success_retry, info_retry = run_sample(trait, text, expected)
            retry_record: Dict[str, object] = {
                "text": text,
                "expected": expected,
                "rr": current_rr,
                "success": success_retry,
            }
            if success_retry:
                retry_record["value"] = info_retry
                successes += 1
                attempt_record["note"] = "recovered_after_bump"
            else:
                retry_record["error"] = info_retry
                attempt_record["note"] = "still_missing_after_bump"

            attempts.append(retry_record)

    finally:
        env_vars[trait.env_toggle] = original_toggle
        env_vars[trait.env_rr] = original_rr
        write_env_file(env_vars)

    samples_run = samples_processed
    precision = (successes / samples_run * 100.0) if samples_run else 0.0
    result = {
        "trait": trait.code,
        "rr_gate": current_rr,
        "rr_bump": rr_bump,
        "samples_run": samples_run,
        "precision": precision,
        "success": precision >= 95.0,
        "attempts": attempts,
        "bumped": bumped,
    }

    append_report(trait, result)

    print("\nVerification complete")
    print(f"- Trait: {trait.code}")
    print(f"- Samples run: {samples_run}")
    print(f"- Precision: {precision:.1f}%")
    print(f"- RR Gate Final: {current_rr}")
    print(f"- RR Bump Applied: {'yes' if bumped else 'no'}")
    print(f"- Summary: {REPORT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
