# ucnrr_service.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone

app = FastAPI(title="UCN/RR Demo", version="0.1.0")

class ReconcileIn(BaseModel):
    user_id: str
    legacy_key: str
    value: str
    source: str = "imported"
    confidence: Optional[float] = 0.6  # 0..1

class ReconcileOut(BaseModel):
    ok: bool
    reconciled_at: str
    mapped_to: Optional[str] = None
    resolved: Optional[Dict[str, Any]] = None
    notes: Optional[Dict[str, Any]] = None

# simple key->trait mapping (expand as needed)
LEGACY_TO_TRAIT = {
    "Eye Color": "PaDNA.LooksDNA.EyeDNA.IrisColor",
    "Hair Color": "PaDNA.LooksDNA.HairDNA.NaturalColor",
    "Freckles": "PaDNA.LooksDNA.SkinDNA.Freckles",
}

def ucn_from_conf(conf: float) -> int:
    # demo rule: UCN = round(confidence * 220)
    conf = max(0.0, min(1.0, conf))
    return int(round(conf * 220))

@app.get("/health")
def health():
    return {"ok": True, "service": "UCN/RR Demo", "version": "0.1.0"}

@app.post("/reconcile", response_model=ReconcileOut)
def reconcile(inp: ReconcileIn):
    trait = LEGACY_TO_TRAIT.get(inp.legacy_key)
    out = ReconcileOut(ok=True, reconciled_at=datetime.now(timezone.utc).isoformat())

    if not trait:
        out.notes = {"reason": f"no mapping for legacy_key '{inp.legacy_key}'"}
        return out

    # naive normalization rule (translate value to TitleCase where applicable)
    normalized_value = inp.value.strip().title()

    out.mapped_to = trait
    out.resolved = {
        "user_id": inp.user_id,
        "schema_version": 4,
        "resolved": {
            trait: {
                "resolved_value": normalized_value,
                "ucn": ucn_from_conf(inp.confidence or 0.6),
                "flags": ["translated"],
                "reasons": [f"imported:{normalized_value}@{(inp.confidence or 0.6):.2f}"],
            }
        },
    }
    out.notes = {"source": inp.source}
    return out