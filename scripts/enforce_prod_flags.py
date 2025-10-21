#!/usr/bin/env python3
"""Fail fast when production builds enable mock/skip/bypass flags."""

import os
import sys
from typing import List

FALSEY = {"", "0", "false", "off", "no"}

STRICT_RULES = [
    {
        "name": "NEXT_PUBLIC_CORE_BYPASS_ALLOWED",
        "allowed": {"false"},
        "required": True,
        "message": "NEXT_PUBLIC_CORE_BYPASS_ALLOWED must be set to 'false' for production builds.",
    },
    {
        "name": "DEV_LOOP_SKIP_RECOMPUTE",
        "allowed": FALSEY,
        "message": "Remove DEV_LOOP_SKIP_RECOMPUTE for production builds.",
    },
    {
        "name": "STACK_UP_SKIP_BOOTSTRAP",
        "allowed": FALSEY,
        "message": "STACK_UP_SKIP_BOOTSTRAP cannot be enabled in production.",
    },
    {
        "name": "READINESS_SKIP_CORE_HEALTH",
        "allowed": FALSEY,
        "message": "READINESS_SKIP_CORE_HEALTH cannot be enabled in production.",
    },
]

PREFIXES = (
    "NEXT_PUBLIC_",
    "DEV_",
    "STACK_",
    "READINESS_",
    "CORE_",
    "UCNRR_",
    "LLM_",
    "HC_",
    "AI_",
)
PATTERNS = ("MOCK", "SKIP", "BYPASS")


def _normalize(value: str) -> str:
    return value.strip().lower()


def main() -> int:
    violations: List[str] = []
    environment = os.environ

    monitored = {rule["name"] for rule in STRICT_RULES}

    for rule in STRICT_RULES:
        raw_value = environment.get(rule["name"], "")
        normalized = _normalize(raw_value)
        allowed = {_normalize(item) for item in rule["allowed"]}
        if rule.get("required") and not raw_value:
            violations.append(rule["message"])
            continue
        if raw_value and normalized not in allowed:
            violations.append(rule["message"])

    for key, value in environment.items():
        upper_key = key.upper()
        if key in monitored:
            continue
        if not any(upper_key.startswith(prefix) for prefix in PREFIXES):
            continue
        if not any(pattern in upper_key for pattern in PATTERNS):
            continue
        normalized = _normalize(value)
        if normalized not in FALSEY:
            violations.append(f"{key}={value} violates mock/skip/bypass policy.")

    if violations:
        sys.stderr.write("[Prod Safeguard] Unsafe environment flags detected:\n")
        for item in violations:
            sys.stderr.write(f" - {item}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
