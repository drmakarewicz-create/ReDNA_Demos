"""Persistence helpers for Control Panel Plus Plus environment and state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".cpplusplus_env.json"
STATE_PATH = ROOT / ".cpplusplus_state.json"
PROFILES_PATH = Path.home() / ".cpplusplus_profiles.json"

_DEFAULT_WORKSPACE_ROOT = ROOT

DEFAULT_ENV: Dict[str, Any] = {
    "core_port": 8004,
    "react_port": 3000,
    "DEVX_BACKEND_PORT": 8100,
    "streamlit_port": 8510,
    "streamlit_photo_port": 8510,
    "streamlit_padna_port": 8511,
    "ucnrr_port": 8017,
    "core_workdir": str(ROOT),
    "core_start_command": "uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8004",
    "ucnrr_workdir": str(ROOT),
    "ucnrr_start_command": f"{ROOT / '.venv' / 'bin' / 'python'} -m uvicorn ucnrr_app:app --host 0.0.0.0 --port {{port}} --reload",
    "ucnrr_health_url": "http://127.0.0.1:{{ucnrr_port}}/health",
    "HC_CHAT_ENABLED": True,
    "HC_CHAT_STREAM_ENABLED": True,
    "HC_ASK_ACTIONS_ENABLED": True,
    "NEXT_PUBLIC_CORE_API_BASE": "http://127.0.0.1:8004",
    "LLM_PROVIDER": "ollama",
    "LLM_MODEL": "phi3:mini",
    "LLM_BASE_URL": "http://127.0.0.1:11434",
    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
    "OLLAMA_BASE": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "phi3:mini",
    "llm_start_command": f"bash {(ROOT / 'start_llm.sh').resolve()}" if (ROOT / "start_llm.sh").exists() else "",
    "NEXT_PUBLIC_DEVX_API_BASE": "http://127.0.0.1:8100",
    "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:3000",
    "AUTO_OPEN_REACT_AFTER_LAUNCH": False,
    "AUTO_OPEN_STREAMLIT_AFTER_LAUNCH": False,
    "AUTO_OPEN_BENCHMARKS_AFTER_LAUNCH": False,
    "AUTO_OPEN_DEVEXPLORER_AFTER_LAUNCH": False,
    "APPEND_UI_DEBUG_PARAM": False,
    "dev_explorer_port": 8550,
    "UCNRR_BASE_URL": "http://127.0.0.1:8017",
    "UCNRR_BASE": "http://127.0.0.1:8017",
    "UCNRR_SCORE_PATH": "/api/rescore",
    "NEXT_PUBLIC_UCNRR_API_BASE": "http://127.0.0.1:8017",
    "WORKSPACE_ROOT": str(_DEFAULT_WORKSPACE_ROOT),
    "WORKSPACE_LABEL": "Default workspace",
    "react_workdir": str(ROOT / "web"),
    "react_npm_path": "",
}


def _ensure_json_serializable(payload: Dict[str, Any]) -> Dict[str, Any]:
    serializable: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            serializable[key] = value
        else:
            serializable[key] = str(value)
    return serializable


def load_env_config() -> Dict[str, Any]:
    data = DEFAULT_ENV.copy()
    if not ENV_PATH.exists():
        return data
    try:
        loaded = json.loads(ENV_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if key in data:
                    data[key] = value
                else:
                    data[key] = value
    except Exception:
        return data
    return data


def save_env_config(config: Dict[str, Any]) -> None:
    ENV_PATH.write_text(json.dumps(_ensure_json_serializable(config), indent=2, sort_keys=True), encoding="utf-8")


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(_ensure_json_serializable(state), indent=2, sort_keys=True), encoding="utf-8")


def load_profiles() -> Dict[str, Dict[str, Any]]:
    if not PROFILES_PATH.exists():
        return {}
    try:
        payload = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        profiles: Dict[str, Dict[str, Any]] = {}
        for name, config in payload.items():
            if isinstance(config, dict):
                profiles[str(name)] = dict(config)
        return profiles
    except Exception:
        return {}


def save_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    serializable: Dict[str, Any] = {}
    for name, config in profiles.items():
        serializable[str(name)] = _ensure_json_serializable(dict(config))
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")
