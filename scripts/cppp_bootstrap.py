#!/usr/bin/env python3
"""
CP++ DevX Bootstrap Script
==========================

Starts the UCNRR, Core, and DevX backend services in sequence, verifies their
health, and provides a summary table for quick confirmation. Any failure
triggers a clean rollback so the stack never ends up in a half-started state.
"""

from __future__ import annotations
# --- bootstrap path fix (inserted) ---
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ReDNACoreDemo.devx.backend import stack_api
# --- end bootstrap path fix ---

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional



SERVICE_SEQUENCE = ["ucnrr", "core", "devx"]


@dataclass
class ServiceResult:
    service: stack_api.ServiceDefinition
    port: int
    pid: int
    duration: float
    health: Dict[str, object]


def _format_duration(seconds: float) -> str:
    return f"{seconds:.1f}s"


def _color_status(state: str) -> str:
    badge = {"healthy": "🟢", "degraded": "🟠", "down": "🔴"}.get(state.lower(), "⚪️")
    return f"{badge} {state.capitalize()}"


def _ensure_port(service: stack_api.ServiceDefinition) -> int:
    port = service.port
    listeners = stack_api._listeners_for(service, port)
    if not listeners:
        return port

    if stack_api.find_free_port:
        new_port: Optional[int] = stack_api.find_free_port(8000, 8099) if service.key == "core" else stack_api.find_free_port(8010, 8199)
    else:
        new_port = stack_api._fallback_find_port(8000, 8099) if service.key == "core" else stack_api._fallback_find_port(8010, 8199)

    if new_port is None:
        raise RuntimeError(f"No available port for {service.display_name}; tried to move off {port}.")

    stack_api._update_env_var(service.env_var, str(new_port))
    os.environ[service.env_var] = str(new_port)
    return new_port


async def _await_health(service: stack_api.ServiceDefinition, port: int) -> Dict[str, object]:
    return await stack_api._wait_for_health(service, port, attempts=15, delay=1.0)


def _print_header() -> None:
    print("🚀 ReDNA Stack Bootstrap v1.0\n")
    print(f"Using Python: {sys.executable}")
    print("Starting services...")


def _print_step(index: int, total: int, name: str, port: int, status_text: str) -> None:
    print(f"  [{index}/{total}] {name} (port {port})... {status_text}")


def _print_summary(results: List[ServiceResult]) -> None:
    print("\nStack Status:")
    headers = ("Service", "Port", "Status", "PID", "Startup")
    row_fmt = "│ {0:<9} │ {1:<4} │ {2:<9} │ {3:<8} │ {4:<8} │"
    border = "┌───────────┬──────┬─────────┬──────────┬──────────┐"
    separator = "├───────────┼──────┼─────────┼──────────┼──────────┤"
    footer = "└───────────┴──────┴─────────┴──────────┴──────────┘"

    print(border)
    print(row_fmt.format(*headers))
    print(separator)
    for result in results:
        status = result.health.get("status", "unknown")
        badge = _color_status(str(status))
        print(
            row_fmt.format(
                result.service.display_name[:9],
                result.port,
                badge,
                result.pid,
                _format_duration(result.duration),
            )
        )
    print(footer)
    print("\n🟢 All services running!\n")
    print("Next steps:")
    print("  - Stack Status UI: http://127.0.0.1:3100/stack")
    print("  - Core API: http://127.0.0.1:{}/health".format(stack_api.SERVICES["core"].port))
    print("  - UCNRR: http://127.0.0.1:{}/health".format(stack_api.SERVICES["ucnrr"].port))


def _first_error_line(lines: List[str]) -> Optional[str]:
    for line in lines:
        if "ERROR" in line or '"level": "ERROR"' in line or '"level": "error"' in line.lower():
            return line
    return lines[0] if lines else None


def _print_failure(name: str, error: Exception, log_lines: List[str]) -> None:
    print(f"\n❌ Failed to start {name}: {error}")
    if log_lines:
        error_line = _first_error_line(log_lines)
        print("\nLast log entries:")
        if error_line:
            print(error_line)
        for line in log_lines[:5]:
            if line == error_line:
                continue
            print(line)


def _tail_logs(service: stack_api.ServiceDefinition, lines: int = 20) -> List[str]:
    entries = stack_api._tail_json(service.resolve_log_path(), lines)
    rendered = []
    for entry in entries:
        if isinstance(entry, dict):
            rendered.append(json.dumps(entry, ensure_ascii=False))
        else:
            rendered.append(str(entry))
    return rendered


def _stop_started(started: List[ServiceResult]) -> None:
    for result in reversed(started):
        pid = result.pid if stack_api._pid_alive(result.pid) else stack_api._read_pid(result.service)
        if pid:
            stack_api._kill_pid(pid)


def bootstrap_stack(interactive: bool = True) -> int:
    total = len(SERVICE_SEQUENCE)
    started: List[ServiceResult] = []
    current_service: Optional[stack_api.ServiceDefinition] = None

    if interactive:
        _print_header()

    try:
        for index, key in enumerate(SERVICE_SEQUENCE, start=1):
            service = stack_api.SERVICES[key]
            current_service = service
            port = _ensure_port(service)
            start_ts = time.perf_counter()
            pid = stack_api._start_service_sync(service, port)
            try:
                health = asyncio.run(_await_health(service, port))
            except Exception:
                stack_api._kill_pid(pid)
                raise

            duration = time.perf_counter() - start_ts

            status = str(health.get("status", "unknown"))
            healthy = status.lower() in {"healthy", "ok", "green"}

            if interactive:
                badge = "✅ Healthy" if healthy else "⚠️ Check logs"
                _print_step(index, total, service.display_name, port, f"{badge} ({_format_duration(duration)})")

            if not healthy:
                stack_api._kill_pid(pid)
                raise RuntimeError(f"Health check failed ({status})")

            started.append(ServiceResult(service=service, port=port, pid=pid, duration=duration, health=health))

        if interactive:
            _print_summary(started)
        return 0

    except Exception as exc:
        failing_service = current_service or stack_api.SERVICES[SERVICE_SEQUENCE[0]]
        log_lines = _tail_logs(failing_service)
        if interactive:
            _print_failure(failing_service.display_name, exc, log_lines)
        _stop_started(started)
        if current_service and all(result.service != current_service for result in started):
            # ensure current service is terminated if it failed before recording
            pid = stack_api._read_pid(current_service)
            if pid:
                stack_api._kill_pid(pid)
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the ReDNA stack (UCNRR, Core, DevX).")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    args = parser.parse_args(argv)
    return bootstrap_stack(interactive=not args.quiet)


if __name__ == "__main__":
    sys.exit(main())
