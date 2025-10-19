from __future__ import annotations

from pathlib import Path


def test_devx_env_file_contains_required_variables():
    env_path = Path(__file__).resolve().parents[1] / "devx" / "frontend" / ".env"
    assert env_path.exists(), "DevX frontend .env file is missing"
    content = env_path.read_text(encoding="utf-8")
    assert "VITE_DEVX_API_BASE=" in content, "VITE_DEVX_API_BASE missing from .env"
    assert "VITE_CORE_API_BASE=" in content, "VITE_CORE_API_BASE missing from .env"


def test_frontend_source_avoids_process_env():
    src_root = Path(__file__).resolve().parents[1] / "devx" / "frontend" / "src"
    offenders = []
    for path in src_root.rglob("*"):
        if not path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "process.env" in text:
            offenders.append(path.relative_to(src_root))
    assert offenders == [], f"process.env references found: {offenders}"
