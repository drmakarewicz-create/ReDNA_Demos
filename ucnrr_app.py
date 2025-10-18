# ucnrr_app.py — UCN/RR Demo API (compat + storage init)
from __future__ import annotations
import os, json, re
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

FORCE_INJECT_CHRONO = os.environ.get("FORCE_INJECT_CHRONO", "false").lower() in ("1", "true", "yes")

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


CHRONO_DETECT_PATTERNS: List[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmorning\s+person\b", re.IGNORECASE), "morning person"),
    (re.compile(r"\bearly\s+riser\b", re.IGNORECASE), "early riser"),
    (re.compile(r"\bup\s+before\s+sunrise\b", re.IGNORECASE), "before sunrise"),
    (re.compile(r"\bup\s+by\s+sunrise\b", re.IGNORECASE), "by sunrise"),
    (
        re.compile(r"\bup\s+before\b[\s,\w]{0,40}\bsunrise\b", re.IGNORECASE),
        "before sunrise",
    ),
]


def _detect_chronotype(text: str) -> List[str]:
    """Return matched chronotype phrases from free text."""
    if not isinstance(text, str) or not text.strip():
        return []

    matches: List[str] = []
    for pattern, label in CHRONO_DETECT_PATTERNS:
        if pattern.search(text):
            if label not in matches:
                matches.append(label)
    return matches


def _maybe_inject_chronotype(
    user_text: str,
    rr_by_trait: Dict[str, float],
    why_by_trait: Dict[str, str],
    curiosity_by_trait: Optional[Dict[str, float]] = None,
) -> None:
    """Insert Chronotype promotion data when phrases or force toggle are present."""
    trait_id = "BehaviorDNA.Sleep.Chronotype"
    if trait_id in rr_by_trait:
        return

    matches = _detect_chronotype(user_text)
    if not matches and not FORCE_INJECT_CHRONO:
        return

    rr_by_trait[trait_id] = 830.0
    if curiosity_by_trait is not None:
        curiosity_by_trait.setdefault(trait_id, 12.0)

    if matches:
        rationale = "Matched " + " and/or ".join(f"'{m}'" for m in matches)
    else:
        rationale = "Injected due to FORCE_INJECT_CHRONO toggle"

    why_by_trait[trait_id] = rationale

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

# ---------- Northstar Phase 2: /api/rescore endpoint ----------
@app.post("/api/rescore")
def api_rescore(body: IngestText):
    """
    Northstar Core ingestion endpoint.
    Receives text, extracts traits, calculates RR scores.

    Expected by Core API for Northstar Phase 2 ingestion roundtrip.
    """
    uid, text = body.user_id.strip(), body.text.strip()
    if not uid or not text:
        raise HTTPException(400, "user_id and text required")

    # Ensure user storage exists
    udir = ensure_user(uid)

    # Log ingestion for debugging
    log = {
        "ts": now_iso(),
        "user_id": uid,
        "raw_text": text,
        "note": "api/rescore received from Core",
    }
    _write_json(udir / f"rescore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", log)

    # ---- Extract traits (placeholder AI logic) ----
    rr_by_trait: Dict[str, float] = {}
    curiosity_by_trait: Dict[str, float] = {}
    why_by_trait: Dict[str, str] = {}

    # Simple extraction: look for patterns like "I am 25 years old"
    text_lower = text.lower()

    # Age extraction
    if "25" in text or "twenty" in text_lower or "age" in text_lower:
        rr_by_trait["BasicDNA.Age"] = 95.0
        curiosity_by_trait["BasicDNA.Age"] = 15.0

    # Gender/orientation extraction
    if any(word in text_lower for word in ["male", "female", "man", "woman", "non-binary"]):
        rr_by_trait["BasicDNA.Gender"] = 85.0
        curiosity_by_trait["BasicDNA.Gender"] = 20.0

    # Interest extraction
    if any(word in text_lower for word in ["love", "enjoy", "like", "hobby"]):
        rr_by_trait["InterestDNA.Hobbies"] = 70.0
        curiosity_by_trait["InterestDNA.Hobbies"] = 40.0

    # Would You Rather extraction
    if "option a" in text_lower or "option b" in text_lower or "cozy" in text_lower or "adventure" in text_lower:
        rr_by_trait["PersonalityDNA.WYRChoice"] = 90.0
        curiosity_by_trait["PersonalityDNA.WYRChoice"] = 10.0

    _maybe_inject_chronotype(text, rr_by_trait, why_by_trait, curiosity_by_trait)

    # Return format expected by Core
    return {
        "ok": True,
        "user_id": uid,
        "rr_by_trait": rr_by_trait,
        "curiosity_by_trait": curiosity_by_trait,
        "why_by_trait": why_by_trait,
        "traits_updated": len(rr_by_trait),
        "timestamp": now_iso()
    }

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
