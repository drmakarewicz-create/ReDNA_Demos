# UCN_RR_Demo/ucnrr_service.py
from __future__ import annotations
import os, json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

APP_VERSION = "ucnrr-demo-api/1.0.0"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
USERS_DIR = DATA_DIR / "users"            # staging yard for Explorer→UCN/RR
USERS_DIR.mkdir(parents=True, exist_ok=True)

CORE_BASE_DEFAULT = "http://localhost:8010"  # Core API base

def ts_name(prefix: str="bundle") -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

def latest_json_in(folder: Path) -> Optional[Path]:
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None

def compute_rr(bundle: Dict[str, Any]) -> float:
    traits = ((bundle.get("Prefs") or {}).get("traits")) or {}
    filled = sum(1 for _, v in traits.items() if v not in (None, "", [], {}))
    score = 5.0 * min(filled, 10) + 1.0 * max(filled - 10, 0)
    return max(0.0, min(100.0, score))

app = FastAPI(title="UCN/RR Demo API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {"ok": True, "app": APP_VERSION}

# -------- Phase 1: Explorer ↔ UCN/RR --------
@app.post("/gateway/save")
def gateway_save(payload: Dict[str, Any]):
    user_id = payload.get("user_id")
    bundle = payload.get("bundle")
    if not user_id or not isinstance(bundle, dict):
        raise HTTPException(400, "user_id and bundle required")

    # attach/update RR (coverage placeholder)
    rr = compute_rr(bundle)
    bundle.setdefault("scores", {})
    bundle["scores"]["rr_overall"] = rr

    user_dir = USERS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    out_path = user_dir / ts_name("bundle")
    out_path.write_text(json.dumps(bundle, indent=2))
    return {"ok": True, "ucnrr_id": out_path.name, "user_dir": str(user_dir), "rr_overall": rr}

@app.get("/gateway/latest")
def gateway_latest(env: str = Query("dev"), user_id: str = Query(...)):
    user_dir = USERS_DIR / user_id
    f = latest_json_in(user_dir)
    if not f:
        raise HTTPException(404, f"No bundle for user_id={user_id}")
    bundle = json.loads(f.read_text())
    rr = ((bundle.get("scores") or {}).get("rr_overall"))
    return {"ok": True, "bundle": bundle, "rr_overall": rr, "ucnrr_id": f.name}

# -------- Phase 2: UCN/RR ↔ Core (proxy) --------
def core_base() -> str:
    return os.environ.get("CORE_BASE", CORE_BASE_DEFAULT)

try:
    import requests
except Exception:
    requests = None

@app.post("/core/save")
def core_save(payload: Dict[str, Any]):
    if requests is None:
        raise HTTPException(503, "requests not available")
    url = core_base().rstrip("/") + "/core/save"
    r = requests.post(url, json=payload, timeout=5)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status": r.status_code, "text": r.text}
    if r.status_code != 200 or not data.get("ok"):
        raise HTTPException(502, f"core/save failed: {data}")
    return data

@app.get("/core/latest")
def core_latest(env: str = Query("dev"), user_id: str = Query(...)):
    if requests is None:
        raise HTTPException(503, "requests not available")
    url = core_base().rstrip("/") + f"/core/latest?env={env}&user_id={user_id}"
    r = requests.get(url, timeout=5)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "status": r.status_code, "text": r.text}
    if r.status_code != 200 or not data.get("ok"):
        raise HTTPException(502, f"core/latest failed: {data}")
    return data