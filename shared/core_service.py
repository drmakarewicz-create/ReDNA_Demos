# core_service.py
# Minimal Core backend for ReDNA demos
# - GET  /health                -> 200 OK (used by the UI probe)
# - POST /dna/save              -> saves bundle in memory + disk snapshot
# - GET  /dna/load_latest?user_id=... -> returns most recent bundle
#
# Run:
#   pip install fastapi uvicorn "pydantic<3"
#   uvicorn core_service:app --host 0.0.0.0 --port 8010
#
# Snapshots are stored under ./core_snapshots/<user_id>/

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os, json, hashlib

app = FastAPI(title="ReDNA Core (Demo)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# In-memory latest-by-user cache (for quick demo)
LATEST: dict[str, dict] = {}

def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def sha_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]

def local_save_bundle(bundle: dict) -> str:
    user_id = bundle.get("user_id") or "unknown"
    folder = os.path.join("core_snapshots", user_id)
    os.makedirs(folder, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fn = f"dna_{ts}_{sha_short(json.dumps(bundle, sort_keys=True))}.json"
    path = os.path.join(folder, fn)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)
    return path

def local_load_latest(user_id: str) -> dict | None:
    folder = os.path.join("core_snapshots", user_id)
    if not os.path.isdir(folder): return None
    files = [p for p in os.listdir(folder) if p.endswith(".json")]
    if not files: return None
    files.sort(reverse=True)
    with open(os.path.join(folder, files[0]), "r", encoding="utf-8") as f:
        return json.load(f)

class BundleModel(BaseModel):
    # Accept any JSON bundle; validate minimally
    bundle: dict

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "core",
        "ts": now_iso(),
        "endpoints": ["/health", "/dna/save", "/dna/load_latest"],
        "version": "0.1"
    }

@app.post("/dna/save")
def dna_save(payload: dict):
    """
    Accept either the bundle directly OR {"bundle": {...}}
    """
    bundle = payload.get("bundle", payload)
    if not isinstance(bundle, dict):
        raise HTTPException(400, "Invalid bundle")
    user_id = bundle.get("user_id") or "unknown"
    bundle = dict(bundle)
    bundle["updated_at"] = now_iso()
    LATEST[user_id] = bundle
    path = local_save_bundle(bundle)
    return {"ok": True, "id": sha_short(json.dumps(bundle, sort_keys=True)), "path": path}

@app.get("/dna/load_latest")
def dna_load_latest(user_id: str):
    if user_id in LATEST:
        return {"ok": True, "bundle": LATEST[user_id]}
    local = local_load_latest(user_id)
    if local:
        LATEST[user_id] = local
        return {"ok": True, "bundle": local}
    raise HTTPException(404, f"No snapshot found for user_id={user_id}")