"""Port scanning and cleanup utilities for Control Panel Plus Plus."""

from __future__ import annotations

import os
import platform
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # pragma: no cover - psutil optional
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

IS_DARWIN = platform.system() == "Darwin"
SCAN_TIMEOUT = 2.0


@dataclass
class PortProcess:
    """A listener discovered on a monitored port."""

    port: int
    pid: int
    name: str
    cmdline: str


LAST_SCAN: Dict[str, List[PortProcess]] = {}
LAST_ERRORS: Dict[str, List[str]] = {}
LSOF_PATH = shutil.which("lsof")


def scan_ports(label: str, ports: Sequence[int]) -> Tuple[List[PortProcess], List[str]]:
    """Scan *ports* and cache the result under *label*.

    Returns a tuple ``(rows, errors)`` where rows contains ``PortProcess``
    entries matching the monitored port range. Errors are surfaced for
    debugging but never raised.
    """

    port_list = sorted({int(port) for port in ports})
    found: Dict[Tuple[int, int], PortProcess] = {}
    errors: List[str] = []

    if not port_list:
        LAST_SCAN[label] = []
        LAST_ERRORS[label] = []
        return [], []

    lsof_attempted = False

    if LSOF_PATH and (IS_DARWIN or not found):
        lsof_attempted = True
        try:
            lsof_rows, lsof_errors = _scan_ports_lsof_range(port_list)
            for row in lsof_rows:
                found[(row.port, row.pid)] = row
            errors.extend(lsof_errors)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"lsof scan error: {exc}")

    if not found and not IS_DARWIN:
        if psutil:
            ps_rows, ps_errors = _scan_ports_psutil(port_list)
            for row in ps_rows:
                found[(row.port, row.pid)] = row
            errors.extend(ps_errors)
        elif not lsof_attempted:
            errors.append("Port scan requires lsof or psutil capabilities on this platform.")

    rows = sorted(found.values(), key=lambda item: (item.port, item.pid))
    LAST_SCAN[label] = rows
    LAST_ERRORS[label] = errors
    return rows, errors


def get_cached(label: str) -> List[PortProcess]:
    """Return the latest cached result for a label."""

    return list(LAST_SCAN.get(label, []))


def get_scan_errors(label: str) -> List[str]:
    """Return the scan diagnostics captured for *label*."""

    return list(LAST_ERRORS.get(label, []))


def who_listens(port: int) -> List[Dict[str, Any]]:
    """Return listeners on *port* as ``{"pid": int, "cmd": str}`` entries."""

    if port <= 0:
        return []

    listeners: Dict[int, Dict[str, Any]] = {}

    if LSOF_PATH:
        try:
            lsof_rows, _ = _scan_ports_lsof_range([port])
            for row in lsof_rows:
                if row.pid > 0:
                    listeners[row.pid] = {"pid": row.pid, "cmd": row.cmdline or row.name}
        except Exception:
            pass

    if not listeners and psutil:
        try:
            ps_rows, _ = _scan_ports_psutil([port])
            for row in ps_rows:
                if row.pid > 0:
                    listeners[row.pid] = {"pid": row.pid, "cmd": row.cmdline or row.name}
        except Exception:
            pass

    return sorted(listeners.values(), key=lambda item: item["pid"])


def is_expected_core_owner(rows: List[Dict[str, Any]]) -> bool:
    """True if any listener command appears to be the expected Core app."""

    for row in rows:
        cmd = str(row.get("cmd", ""))
        if not cmd:
            continue
        lower = cmd.lower()
        if "uvicorn" in lower and "rednacoredemo.core.api:build_app" in lower:
            return True
    return False


def find_free_port(start: int, end: int) -> Optional[int]:
    """Return the first free TCP port in the inclusive range, if any."""

    if start > end:
        start, end = end, start
    for port in range(start, end + 1):
        if who_listens(port):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    return None


def kill_cached(label: str) -> Dict[str, Any]:
    """Terminate all cached listeners for a label using the cached PIDs."""

    cached = get_cached(label)
    pids = sorted({entry.pid for entry in cached if entry.pid > 0})
    if not pids:
        return {
            "label": label,
            "terminated": [],
            "already_dead": [],
            "errors": {},
            "status": "empty",
        }
    result = kill_pids(pids)
    result.update({"label": label, "status": "ok", "pids": pids})
    return result


def kill_single(label: str, pid: int) -> Dict[str, Any]:
    """Terminate a single PID from the cached label set."""

    if pid <= 0:
        return {
            "label": label,
            "terminated": [],
            "already_dead": [pid],
            "errors": {pid: "Invalid PID"} if pid else {},
            "status": "invalid",
        }
    result = kill_pids([pid])
    result.update({"label": label, "status": "ok", "pids": [pid]})
    return result


def kill_pids(pids: Sequence[int]) -> Dict[str, Any]:
    unique_pids = sorted({pid for pid in pids if pid > 0})
    terminated: List[int] = []
    already_dead: List[int] = []
    errors: Dict[int, str] = {}

    for pid in unique_pids:
        try:
            if psutil:
                try:
                    proc = psutil.Process(pid)
                except psutil.NoSuchProcess:
                    already_dead.append(pid)
                    continue
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                    terminated.append(pid)
                    continue
                except psutil.TimeoutExpired:
                    pass
                except psutil.NoSuchProcess:
                    already_dead.append(pid)
                    continue
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                    terminated.append(pid)
                except psutil.TimeoutExpired:
                    errors[pid] = "Timeout waiting after SIGKILL"
                except psutil.NoSuchProcess:
                    terminated.append(pid)
            else:
                if not _send_signal(pid, signal.SIGTERM):
                    already_dead.append(pid)
                    continue
                time.sleep(0.2)
                if _is_alive(pid):
                    if not _send_signal(pid, signal.SIGKILL):
                        terminated.append(pid)
                    else:
                        time.sleep(0.2)
                        if _is_alive(pid):
                            errors[pid] = "Process still running after SIGKILL"
                        else:
                            terminated.append(pid)
                else:
                    terminated.append(pid)
        except PermissionError:
            errors[pid] = "Permission denied"
        except ProcessLookupError:
            already_dead.append(pid)
        except Exception as exc:  # pragma: no cover - unexpected platform specifics
            errors[pid] = str(exc)

    return {
        "terminated": terminated,
        "already_dead": already_dead,
        "errors": errors,
    }


def _scan_ports_lsof_range(port_list: Sequence[int]) -> Tuple[List[PortProcess], List[str]]:
    if not port_list or not LSOF_PATH:
        return [], []

    range_spec = f"{port_list[0]}-{port_list[-1]}" if len(port_list) > 1 else str(port_list[0])
    command = [LSOF_PATH, "-nP", f"-iTCP:{range_spec}", "-sTCP:LISTEN"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return [], ["lsof timed out"]

    errors: List[str] = []
    if completed.returncode not in (0, 1):
        stderr = (completed.stderr or "").strip()
        errors.append(stderr or f"lsof exited with code {completed.returncode}")

    output = completed.stdout or ""
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) <= 1:
        return [], errors

    found: Dict[Tuple[int, int], PortProcess] = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        command_name = parts[0]
        pid_text = parts[1]
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        address = parts[-2]
        port = _extract_port(address)
        if port is None or port not in port_list:
            continue
        cmdline = command_name
        if psutil:
            try:
                proc = psutil.Process(pid)
                cmdline_list = proc.cmdline()
                if cmdline_list:
                    cmdline = " ".join(cmdline_list)
                else:
                    cmdline = proc.name()
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                pass
            except Exception as exc:  # pragma: no cover
                errors.append(f"pid {pid}: {exc}")
        key = (port, pid)
        if key not in found:
            found[key] = PortProcess(port=port, pid=pid, name=command_name, cmdline=cmdline)

    return list(found.values()), errors


def _scan_ports_psutil(port_list: Sequence[int]) -> Tuple[List[PortProcess], List[str]]:
    if not psutil:
        return [], ["psutil not available"]

    port_set = set(port_list)
    found: Dict[Tuple[int, int], PortProcess] = {}
    errors: List[str] = []

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        pid = proc.info.get("pid")
        if not pid:
            continue
        try:
            connections = proc.connections(kind="inet")
        except (psutil.AccessDenied, psutil.ZombieProcess) as exc:
            errors.append(f"pid {pid}: {exc.__class__.__name__}")
            continue
        except psutil.NoSuchProcess:
            errors.append(f"pid {pid}: NoSuchProcess")
            continue
        except Exception as exc:  # pragma: no cover
            errors.append(f"pid {pid}: {exc}")
            continue

        for conn in connections:
            if conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr:
                continue
            port = conn.laddr.port
            if port not in port_set:
                continue
            cmdline_list = proc.info.get("cmdline") or []
            if cmdline_list:
                cmdline = " ".join(cmdline_list)
            else:
                cmdline = proc.info.get("name") or "unknown"
            key = (port, pid)
            if key not in found:
                found[key] = PortProcess(
                    port=port,
                    pid=pid,
                    name=proc.info.get("name") or "unknown",
                    cmdline=cmdline,
                )

    return list(found.values()), errors


def _send_signal(pid: int, sig: int) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return False


def _is_alive(pid: int) -> bool:
    if psutil:
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and not proc.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _extract_port(address: str) -> Optional[int]:
    address = address.strip()
    if not address:
        return None
    if "(" in address:
        address = address.split("(", 1)[0].strip()
    if address.startswith("[") and "]" in address:
        address = address[address.find("]") + 1 :]
    if ":" in address:
        port_text = address.rsplit(":", 1)[-1]
    elif "." in address:
        port_text = address.split(".")[-1]
    else:
        port_text = address
    port_text = port_text.strip()
    if not port_text:
        return None
    try:
        return int(port_text)
    except ValueError:
        return None
