# UCN_RR_Demo/app.py — v1.3.0 (surgical AI stub + compatibility)
# Endpoints kept stable for Explorer:
#   GET  /health
#   POST /ucnrr/recompute          -> return RR/UCN/Curiosity (display-only)
#   POST /gateway/save             -> normalize + score + snapshot + forward to Core
#   GET  /core/latest              -> proxy to Core /core/latest
#
# Behavior added (non-breaking):
#   - Per-trait scores -> bundle.Prefs.scores[trait] = { rr, ucn, curiosity }
#   - Overall rr/ucn/curiosity in responses
#   - Lightweight recency boost (recent provenance raises UCN a bit)
#   - Provenance stamp on each gateway save
from __future__ import annotations
import json, os, hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APP_VERSION = "ucnrr-demo/1.3.0"
CORE_URL_DEFAULT = os.getenv("REDNA_CORE_URL", "http://localhost:8010")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
USERS_DIR = DATA_DIR / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------ utils ------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def ts_name(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"

def ensure_bundle(b: Dict[str, Any]) -> Dict[str, Any]:
    b.setdefault("schema_version", "redna.bundle/3.0")
    b.setdefault("Prefs", {})
    b["Prefs"].setdefault("traits", {})
    b.setdefault("PaDNA", {})
    b.setdefault("provenance", [])
    return b

def _h01(s: str) -> float:
    """Stable hash -> [0,1)."""
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)

def _recent_boost(provenance: List[Dict[str, Any]]) -> float:
    """
    Tiny UCN boost if we see very recent activity (last ~14 days).
    This is a stub for 'recency raises confidence'.
    """
    try:
        now = datetime.now(timezone.utc)
        for entry in reversed(provenance[-8:]):  # look at a few latest
            ts = entry.get("ts")
            if not ts:
                continue
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            days = (now - dt).days
            if days <= 3:
                return 0.08
            if days <= 7:
                return 0.05
            if days <= 14:
                return 0.02
    except Exception:
        pass
    return 0.0

def assign_confidence_scores(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stubbed AI: deterministic per-trait UCN/RR/Curiosity with a small recency boost to UCN.
    Writes per-trait into Prefs.scores (non-destructive). Returns overall aggregates.
    """
    bundle = ensure_bundle(bundle)
    traits = (bundle.get("Prefs") or {}).get("traits") or {}
    prov = bundle.get("provenance") or []
    ucn_bonus = _recent_boost(prov)

    per_trait = {}
    rr_vals: List[float] = []
    ucn_vals: List[float] = []
    cu_vals: List[float] = []

    for k, v in traits.items():
        base = _h01(f"{k}|{v}")
        rr = round(20.0 + base * 80.0, 2)                   # 20..100
        ucn = round(min(1.0, 0.35 + base * 0.6 + ucn_bonus), 3)  # 0.35..~1.0 with recency
        curiosity = round(abs(0.5 - base) * 1.2, 3)         # 0..~0.6
        per_trait[k] = {"rr": rr, "ucn": ucn, "curiosity": curiosity}
        rr_vals.append(rr); ucn_vals.append(ucn); cu_vals.append(curiosity)

    overall_rr = round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else 50.0
    overall_ucn = round(sum(ucn_vals) / len(ucn_vals), 3) if ucn_vals else 0.5
    overall_cu = round(sum(cu_vals) / len(cu_vals), 3) if cu_vals else 0.25

    # write per-trait scores (non-destructive)
    bundle.setdefault("Prefs", {}).setdefault("scores", {}).update(per_trait)
    return {"rr": {"overall": overall_rr}, "ucn": {"overall": overall_ucn}, "curiosity": {"overall": overall_cu}}

def add_provenance(bundle: Dict[str, Any], note: str):
    bundle = ensure_bundle(bundle)
    bundle["provenance"].append({"ts": utc_now_iso(), "source": "ucnrr", "note": note})

# ------------------------ schemas ------------------------
class RecomputeReq(BaseModel):
    bundle: Dict[str, Any]

class GatewaySaveReq(BaseModel):
    env: Optional[str] = "dev"
    user_id: str
    bundle: Dict[str, Any]
    origin: Optional[str] = "explorer"
    client_rev: Optional[int] = 0

# ------------------------ app ------------------------
app = FastAPI(title="UCN_RR_Demo", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True
)

@app.get("/health")
def health():
    return {"ok": True, "app": APP_VERSION}

@app.post("/ucnrr/recompute")
def ucnrr_recompute(req: RecomputeReq):
    # Return display-only aggregates (does not mutate caller's bundle)
    b = ensure_bundle(req.bundle.copy())
    scores = assign_confidence_scores(b)  # writes per-trait on our copy, not caller
    return {"ok": True, **scores}

@app.post("/gateway/save")
def gateway_save(
    req: GatewaySaveReq,
    compute: str = Query("auto"),
    normalize: str = Query("on"),
    persist_snapshot: str = Query("on"),
    to_core: str = Query("on"),
    core_url: str = Query(CORE_URL_DEFAULT),
):
    if not req.user_id or not isinstance(req.bundle, dict):
        raise HTTPException(400, "user_id and bundle required")

    bundle = ensure_bundle(req.bundle)
    if normalize == "on":
        add_provenance(bundle, f"normalize (ensure shape)")

    # AI stub scoring (writes Prefs.scores + returns aggregates)
    aggregates = {"rr": {"overall": None}, "ucn": {"overall": None}, "curiosity": {"overall": None}}
    if compute in ("on", "auto"):
        aggregates = assign_confidence_scores(bundle)
        add_provenance(bundle, f"scored (ucnrr v{APP_VERSION})")

    # optional local snapshot for debugging
    if persist_snapshot == "on":
        inbox = (USERS_DIR / req.user_id / "inbox")
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / ts_name("ucnrr")).write_text(json.dumps(bundle, indent=2))
        add_provenance(bundle, "snapshot persisted (ucnrr inbox)")

    # forward to Core
    chained_core = None
    if to_core == "on":
        try:
            import requests
            r = requests.post(core_url.rstrip("/") + "/core/save",
                              json={"env": req.env or "dev", "user_id": req.user_id, "bundle": bundle},
                              timeout=10)
            if r.status_code == 200:
                chained_core = r.json()
                add_provenance(bundle, f"forwarded to Core {chained_core.get('core_id')}")
            else:
                raise HTTPException(r.status_code, r.text)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Forward to Core failed: {e}")

    return {"ok": True, "ucnrr_version": APP_VERSION, "ucnrr_id": ts_name("ucnrr"), **aggregates, "chained_core": chained_core}

# Explorer uses this to load via UCN/RR:
@app.get("/core/latest")
def proxy_core_latest(env: str = Query("dev"), user_id: str = Query(...),
                      core_url: str = Query(CORE_URL_DEFAULT)):
    try:
        import requests
        r = requests.get(core_url.rstrip("/") + f"/core/latest?env={env}&user_id={user_id}", timeout=10)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text)
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Proxy to Core failed: {e}")

if __name__ == "__main__":
    # Run: uvicorn app:app --reload --port 8011
    uvicorn.run("app:app", host="0.0.0.0", port=8011, reload=True)