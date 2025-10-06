# app.py — ReDNACoreDemo API (v4 resolved, tolerant ingest)
from __future__ import annotations
import os, json, re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

APP_VERSION = "core-demo/1.1.0"

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("REDNA_CORE_DATA", str(ROOT / "data")))
STORAGE = DATA_DIR / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

def user_dir(uid: str) -> Path:
    p = STORAGE / uid
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(p: Path, obj: Any):
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")

def _norm_path(path: str) -> str:
    return re.sub(r"^PaDNA\.", "", path or "")

class IngestReq(BaseModel):
    user_id: str

app = FastAPI(title="ReDNACoreDemo", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "version": APP_VERSION,
        "prompt_main": os.getenv("CORE_PROMPT_MAIN"),
        "prompt_prop": os.getenv("CORE_PROMPT_PROP"),
        "model": os.getenv("CORE_MODEL", "llama3"),
        "provider": os.getenv("CORE_PROVIDER", "llama"),
    }

@app.get("/resolved/{user_id}")
def resolved(user_id: str):
    udir = user_dir(user_id)
    p = udir / "resolved.json"
    if not p.exists():
        return {"user_id": user_id, "schema_version": 4, "resolved": {}}
    return _load_json(p, {"user_id": user_id, "schema_version": 4, "resolved": {}})

@app.get("/resolved/flat/{user_id}")
def resolved_flat(user_id: str):
    doc = resolved(user_id)
    rows = []
    for k, v in (doc.get("resolved") or {}).items():
        rows.append({
            "path": k,
            "value": v.get("value"),
            "value_type": v.get("value_type"),
            "confidence": v.get("confidence"),
            "source": (v.get("provenance") or {}).get("source"),
        })
    return {"rows": rows}

def _fetch_ucnrr(uid: str) -> Dict[str, Any]:
    base = os.getenv("UCNRR_URL", "http://127.0.0.1:8011").rstrip("/")
    try:
        r = requests.post(f"{base}/legacy_import", json={"user_id": uid}, timeout=10)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return {"resolved": [], "candidates": []}

@app.post("/ingest_from_ucnrr")
def ingest_from_ucnrr(req: IngestReq):
    uid = req.user_id
    data = _fetch_ucnrr(uid)

    items: List[Dict[str, Any]] = list(data.get("resolved") or []) + list(data.get("candidates") or [])
    out_map: Dict[str, Dict[str, Any]] = {}
    for it in items:
        path = _norm_path(it.get("path", ""))
        if not path:
            continue
        val = it.get("value")
        vtype = it.get("value_type")
        conf = it.get("confidence")
        prov = it.get("provenance") or {}
        cur = out_map.get(path)
        if cur is None or (conf is not None and (cur.get("confidence") or 0) < conf):
            out_map[path] = {
                "value": val,
                "value_type": vtype,
                "confidence": conf,
                "provenance": prov,
            }

    udir = user_dir(uid)
    rp = udir / "resolved.json"
    doc = _load_json(rp, {"user_id": uid, "schema_version": 4, "resolved": {}})
    existing = doc.get("resolved") or {}
    changed = []
    for k, v in out_map.items():
        if existing.get(k) != v:
            existing[k] = v
            changed.append(k)
    doc["resolved"] = existing
    _write_json(rp, doc)

    return {"ok": True, "user_id": uid, "changed": changed, "resolved_keys": sorted(existing.keys())}