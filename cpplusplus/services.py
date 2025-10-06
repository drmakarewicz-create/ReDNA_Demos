"""Service process management for Control Panel Plus Plus."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence

try:  # pragma: no cover - psutil optional
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

from cpplusplus import ports

LOG_MAX_LINES = 500
STOP_TIMEOUT = 5.0


@dataclass
class ServiceProcess:
    name: str
    command: Sequence[str]
    cwd: Optional[Path]
    env: Dict[str, str]
    process: subprocess.Popen[str]
    started_at: float = field(default_factory=time.time)
    log: Deque[str] = field(default_factory=lambda: deque(maxlen=LOG_MAX_LINES))
    _log_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stop_requested: bool = field(default=False, init=False, repr=False)

    def is_running(self) -> bool:
        return self.process.poll() is None

    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    def append_log(self, line: str) -> None:
        if self.log.maxlen is None or len(self.log) < self.log.maxlen:
            self.log.append(line.rstrip("\n"))
        else:
            self.log.append(line.rstrip("\n"))

    def stop(self) -> Dict[str, List[int] | Dict[int, str]]:
        if not self.is_running():
            return {"terminated": [], "already_dead": [], "errors": {}}

        self._stop_requested = True
        pid = self.pid()
        if not pid:
            return {"terminated": [], "already_dead": [], "errors": {}}

        pids = {pid}
        if psutil:
            try:
                proc = psutil.Process(pid)
                for child in proc.children(recursive=True):
                    if child.pid:
                        pids.add(child.pid)
            except psutil.Error:
                pass

        summary = ports.kill_pids(list(pids))

        if not psutil:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                pass

        try:
            self.process.wait(timeout=1.0)
        except Exception:
            pass

        return summary

    def logs(self) -> List[str]:
        return list(self.log)


def _ensure_sequence(command: Sequence[str] | str) -> List[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return list(command)


def start_service(
    name: str,
    command: Sequence[str] | str,
    cwd: Optional[str | Path] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
) -> ServiceProcess:
    cmd_seq = _ensure_sequence(command)
    workdir = Path(cwd).resolve() if cwd else None
    proc_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if value is None:
                continue
            proc_env[str(key)] = str(value)

    popen = subprocess.Popen(
        cmd_seq,
        cwd=str(workdir) if workdir else None,
        env=proc_env,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
        text=True,
        bufsize=1,
        universal_newlines=True,
        start_new_session=True,
    )

    service = ServiceProcess(name=name, command=cmd_seq, cwd=workdir, env={k: proc_env[k] for k in (env or {}).keys()}, process=popen)

    if capture_output and popen.stdout:
        thread = threading.Thread(target=_pump_logs, args=(service, popen.stdout), name=f"{name}-log", daemon=True)
        thread.start()
        service._log_thread = thread

    return service


def _pump_logs(service: ServiceProcess, stream: Iterable[str]) -> None:
    try:
        for line in stream:
            if line is None:
                break
            service.append_log(line)
            if service._stop_requested:
                break
    except Exception:
        pass


def stop_service(service: Optional[ServiceProcess]) -> Dict[str, Any]:
    if not service:
        return {"terminated": [], "already_dead": [], "errors": {}}
    try:
        return service.stop()
    except Exception:
        return {"terminated": [], "already_dead": [], "errors": {}}


def poll_service(service: Optional[ServiceProcess]) -> Optional[int]:
    if not service:
        return None
    try:
        return service.process.poll()
    except Exception:
        return None
