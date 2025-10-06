# ucnrr_app.py — UCN/RR Demo API (compat + storage init)
from __future__ import annotations
import os, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APP_VERSION = "ucnrr-demo/1.1.0"

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("UCNRR_DATA", str(ROOT / "data")))
STORAGE = DATA_DIR / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def user_dir(uid: str) -> Path:
    return STORAGE / uid

def ensure_user(uid: str) -> Path:
    p = user_dir(uid)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _write_json(path: Path, obj: Dict[str, Any]):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")

app = FastAPI(title="UCN/RR Demo API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

# ---------- Schemas ----------
class IngestText(BaseModel):
    user_id: str
    text: str

# ---------- Health ----------
@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "ucnrr",
        "data_dir": str(DATA_DIR),
        "storage": str(STORAGE),
        "version": APP_VERSION,
        "endpoints": ["/health","/users/list","/users/init","/ingest_text","/legacy_import"],
    }

# ---------- Users ----------
@app.get("/users/list")
def users_list():
    if not STORAGE.exists():
        return {"ok": True, "users": []}
    users = sorted([p.name for p in STORAGE.iterdir() if p.is_dir()])
    return {"ok": True, "users": users}

@app.post("/users/init")
def users_init(payload: Dict[str, Any]):
    uid = (payload or {}).get("username") or (payload or {}).get("user_id")
    if not uid:
        raise HTTPException(400, "username (or user_id) required")
    p = ensure_user(uid)
    # leave a tiny marker so we can verify quickly
    (p / "_init.txt").write_text(f"{now_iso()} init\n", encoding="utf-8")
    return {"ok": True, "user_id": uid, "path": str(p)}

# ---------- Ingest freeform ----------
@app.post("/ingest_text")
def ingest_text(body: IngestText):
    uid, text = body.user_id.strip(), body.text.strip()
    if not uid or not text:
        raise HTTPException(400, "user_id and text required")

    # Always ensure user storage exists
    udir = ensure_user(uid)

    # Raw log for debugging (LLMDebug style)
    log = {
        "ts": now_iso(),
        "user_id": uid,
        "raw_text": text,
        "note": "ingest_text received",
    }
    _write_json(udir / f"llmdebug_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", log)

    # ---- Very small “AI” placeholder ----
    # Your real model should parse `text` into trait candidates/resolved.
    resolved: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    # canonical hint support (e.g., "EyeDNA.IrisColor=Blue")
    if "=" in text and "." in text:
        path, value = text.split("=", 1)
        resolved.append({
            "path": path.strip(),              # e.g., EyeDNA.IrisColor
            "value": value.strip(),            # e.g., Blue
            "value_type": "string",
            "confidence": 0.70,
            "provenance": {"source": "ingest_text", "ts": now_iso()},
        })

    # Minimal result file for Explorer/Core to pull
    out = {
        "ok": True,
        "user_id": uid,
        "resolved": resolved,
        "candidates": candidates,
        "schema": "ucnrr/traits/1.0",
    }
    _write_json(udir / "latest.json", out)
    return out

# ---------- Export for Core ingest ----------
@app.post("/legacy_import")
def legacy_import(payload: Dict[str, Any]):
    """
    Core calls this with {"user_id": "..."} to fetch the latest traits.
    """
    uid = (payload or {}).get("user_id")
    if not uid:
        raise HTTPException(400, "user_id required")
    udir = user_dir(uid)
    if not udir.exists():
        return {"ok": True, "user_id": uid, "resolved": [], "candidates": []}

    latest = udir / "latest.json"
    if latest.exists():
        try:
            return json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            pass
    # fallback empty
    return {"ok": True, "user_id": uid, "resolved": [], "candidates": []}