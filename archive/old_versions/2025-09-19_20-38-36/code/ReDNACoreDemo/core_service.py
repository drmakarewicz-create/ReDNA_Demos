# core_service.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import os

app = FastAPI(title="ReDNA Core Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CORE_DATA_DIR", ROOT / "data"))
USERS_DIR = DATA_DIR / "users"

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
        # if you ever want to transform into a flat list, do it here
        return payload
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"resolved.json not found for user {user_id}")