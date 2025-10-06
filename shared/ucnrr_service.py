# ucnrr_service.py
# Minimal UCN/RR backend for ReDNA demos
# - GET  /health        -> 200 OK
# - POST /recompute     -> computes demo UCN, RR, Curiosity + returns contradictions/agenda
#
# Run:
#   pip install fastapi uvicorn "pydantic<3"
#   uvicorn ucnrr_service:app --host 0.0.0.0 --port 8011

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import hashlib, json, math

app = FastAPI(title="ReDNA UCN/RR (Demo)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

class RecomputeInput(BaseModel):
    bundle: dict

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "ucnrr",
        "ts": now_iso(),
        "endpoints": ["/health", "/recompute"],
        "version": "0.1"
    }

def deterministic_score(obj: dict) -> float:
    """
    Deterministic 0..1 score from a JSONable dict (so values don't jump around).
    """
    try:
        s = json.dumps(obj, sort_keys=True)
    except Exception:
        s = str(obj)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    # map first 8 hex chars -> int -> 0..1
    v = int(h[:8], 16) / 0xFFFFFFFF
    return v

@app.post("/recompute")
def recompute(inp: RecomputeInput):
    b = inp.bundle or {}
    # Basic, deterministic demo math:
    base = deterministic_score(b)
    # UCN as 600..980; RR as 5..95 percentile; Curiosity inverse of RR per v4.0
    ucn = round(600 + 380 * base, 2)
    rr  = round(5 + 90 * base, 1)
    curiosity = round(100 - rr, 1)

    # Toy contradiction detector: if PaDNA has both "image_mode" and "has_file" in traits, we pretend no conflict;
    # if multiple conflicting "eye" descriptors exist in strings, flag one demo contradiction.
    contradictions = []
    try:
        pdna_traits = b.get("umbrellas", {}).get("PaDNA", {}).get("traits", {})
        tstr = json.dumps(pdna_traits).lower()
        eye_flags = sum(1 for w in ["blue eye", "green eye", "brown eye", "hazel"] if w in tstr)
        if eye_flags >= 2:
            contradictions.append({
                "trait": "EyeColorDNA",
                "details": "Multiple eye color mentions detected in PaDNA traits.",
                "status": "in_tension"
            })
    except Exception:
        pass

    # Curiosity agenda: simple, shows one PaDNA basic confirm item
    curiosity_agenda = [{"gap": "PaDNA.basic_confirm", "weight": round(min(0.9, 0.2 + (100 - rr)/100.0), 2), "plan": "light"}]

    return {
        "ok": True,
        "ts": now_iso(),
        "ucn": ucn,
        "rr": rr,
        "curiosity": curiosity,
        "contradictions": contradictions,
        "curiosity_agenda": curiosity_agenda
    }