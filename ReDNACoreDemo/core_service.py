# core_service.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pathlib import Path

try:  # pragma: no cover - allow running as module or script
    from .core import curiosity_engine  # type: ignore
except ImportError:  # pragma: no cover - fallback when relative import fails
    from ReDNACoreDemo.core import curiosity_engine  # type: ignore

app = FastAPI(title="ReDNA Core Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

workspace_candidate = os.getenv("WORKSPACE_ROOT")
if workspace_candidate:
    try:
        WORKSPACE_ROOT = Path(workspace_candidate).expanduser().resolve()
    except Exception:
        WORKSPACE_ROOT = Path(workspace_candidate).expanduser()
else:
    WORKSPACE_ROOT = PROJECT_ROOT

data_candidate = os.getenv("CORE_DATA_DIR") or os.getenv("REDNA_CORE_DATA")
if data_candidate:
    DATA_DIR = Path(data_candidate).expanduser().resolve()
else:
    DATA_DIR = (WORKSPACE_ROOT / "data").resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)

USERS_DIR = DATA_DIR / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)

def _load_json(p: Path):
    if not p.exists():
        raise FileNotFoundError(str(p))
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/health")
def health():
    return {"ok": True, "data_dir": str(DATA_DIR)}

@app.get("/resolved/{user_id}")
def get_resolved(user_id: str):
    """
    Returns nested resolved snapshot for a user from:
    <repo>/ReDNACoreDemo/data/users/<USER>/resolved.json
    """
    try:
        payload = _load_json(USERS_DIR / user_id / "resolved.json")
        resolved_map = payload.get("resolved") if isinstance(payload, dict) else None
        if isinstance(resolved_map, dict):
            curiosity_engine.seed_resolved(resolved_map)
        return payload
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"resolved.json not found for user {user_id}")

@app.get("/resolved/flat/{user_id}")
def get_resolved_flat(user_id: str):
    """
    Optional: a flat view if you want a table without hierarchy collapsing.
    """
    try:
        payload = _load_json(USERS_DIR / user_id / "resolved.json")
        resolved_map = payload.get("resolved") if isinstance(payload, dict) else None
        if isinstance(resolved_map, dict):
            curiosity_engine.seed_resolved(resolved_map)
        # if you ever want to transform into a flat list, do it here
        return payload
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"resolved.json not found for user {user_id}")
