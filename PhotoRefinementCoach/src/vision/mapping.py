from __future__ import annotations
from typing import Dict, Any
from src.vision.model import VisionObservation

def map_observation_to_descriptors(obs: VisionObservation) -> Dict[str, Dict[str, Any]]:
    """
    Identity mapping for now: tokens already use descriptor vocabulary.
    This is where you'd normalize/clean or map model-specific labels → our controlled tokens.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for path, payload in obs.tokens.items():
        out[path] = {
            "value": payload.get("value"),
            "ucn": None,                 # assigned later by scoring policy
            "details": payload.get("details", {}),
            "conf": float(payload.get("confidence", 0.6))
        }
    return out