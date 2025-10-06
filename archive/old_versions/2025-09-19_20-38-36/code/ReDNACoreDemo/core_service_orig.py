# ReDNACoreDemo/core_service.py
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

APP_VERSION = "core-demo-api/1.0.0"
ROOT = Path(__file__).resolve().parent
CHECKPOINTS = (ROOT / "data" / "checkpoints")
CHECKPOINTS.mkdir(parents=True, exist_ok=True)

def ts_name(prefix: str = "bundle") -> str:
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

def latest_json_in(folder: Path) -> Optional[Path]:
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.json"))
    return files[-1] if files else None

app = FastAPI(title="ReDNACoreDemo API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {"ok": True, "app": APP_VERSION}

@app.post("/core/save")
def core_save(payload: Dict[str, Any]):
    env = payload.get("env") or "dev"
    user_id = payload.get("user_id")
    bundle = payload.get("bundle")
    if not user_id or not isinstance(bundle, dict):
        raise HTTPException(400, "user_id and bundle required")

    user_dir = CHECKPOINTS / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    out_path = user_dir / ts_name("bundle")
    out_path.write_text(json.dumps(bundle, indent=2))
    return {"ok": True, "core_id": out_path.name, "user_dir": str(user_dir)}

@app.get("/core/latest")
def core_latest(env: str = Query("dev"), user_id: str = Query(...)):
    user_dir = CHECKPOINTS / user_id
    f = latest_json_in(user_dir)
    if not f:
        raise HTTPException(404, f"No bundle for user_id={user_id}")
    bundle = json.loads(f.read_text())
    return {"ok": True, "bundle": bundle, "core_id": f.name}

if __name__ == "__main__":
    # Run this API on 8010 (leaving Streamlit free to use its own port)
    uvicorn.run("core_service:app", host="0.0.0.0", port=8010, reload=True)