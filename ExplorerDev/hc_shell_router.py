#!/usr/bin/env python3
"""Launcher that routes to the preferred Head Coach shell."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED = {"react", "streamlit"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_BASE = "http://127.0.0.1:8015"


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> int:
    printable_cmd = " ".join(shlex.quote(part) for part in cmd)
    print(f"⇒ Executing: {printable_cmd}")
    try:
        process = subprocess.run(cmd, cwd=str(cwd), env=env, check=False)
    except FileNotFoundError:
        print("⚠️  Command not found. Ensure the required tool is installed and on $PATH.")
        return 127
    return process.returncode


def _ensure_binary(name: str) -> bool:
    if shutil.which(name):
        return True
    print(f"⚠️  Required binary '{name}' not found on PATH.")
    return False


def launch() -> int:
    shell = os.getenv("HC_SHELL_V2", "react").strip().lower()
    if shell not in SUPPORTED:
        print(
            "⚠️  HC_SHELL_V2 must be one of {react, streamlit}. "
            "Defaulting to 'react'."
        )
        shell = "react"

    env = os.environ.copy()

    if shell == "react":
        if not _ensure_binary("npm"):
            return 127
        env.setdefault("NEXT_PUBLIC_CORE_API_BASE", DEFAULT_API_BASE)
        cmd = ["npm", "run", "dev"]
        workdir = PROJECT_ROOT / "web"
        print(
            "Launching Head Coach Track A (React).\n"
            f"NEXT_PUBLIC_CORE_API_BASE={env['NEXT_PUBLIC_CORE_API_BASE']}"
        )
        print("Open http://localhost:3000 once the build completes.")
    else:
        if not _ensure_binary("streamlit"):
            return 127
        cmd = [
            "streamlit",
            "run",
            str(PROJECT_ROOT / "ExplorerFinal" / "pages" / "HC_v2.py"),
        ]
        workdir = PROJECT_ROOT
        print("Launching Head Coach Track B (Streamlit).")
        print("The app will open in your browser once Streamlit starts.")

    return _run(cmd, cwd=workdir, env=env)


if __name__ == "__main__":
    sys.exit(launch())
