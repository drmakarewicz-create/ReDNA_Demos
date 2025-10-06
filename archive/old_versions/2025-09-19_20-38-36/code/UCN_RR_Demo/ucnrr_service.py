# ucnrr_service.py
"""
Drop-in wrapper for UCN/RR with optional AI scoring.
- Keeps all existing endpoints/CLI by delegating to ucnrr_service_orig (your current file).
- When REDNA_AI_ENABLED=true, score_confidence() uses the AI helper.
- If anything fails or AI is off, behavior is identical to your original service.

Install:
  1) Rename your existing file to ucnrr_service_orig.py
  2) Save this file as ucnrr_service.py
  3) Ensure the AI helpers exist at project root:
       - prompt_loader.py
       - llama3_client.py
       - ucn_rr_ai.py
  4) Run as you normally do. Flip AI with REDNA_AI_ENABLED=true
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AI_ENABLED = os.getenv("REDNA_AI_ENABLED", "false").lower() == "true"

try:
    import ucnrr_service_orig as _orig
except Exception as e:
    raise SystemExit(
        f"\n[UCN/RR drop-in] Could not import ucnrr_service_orig.py.\n"
        f"Please rename your previous ucnrr_service.py to ucnrr_service_orig.py.\n\nDetails: {e}\n"
    )

try:
    from ucn_rr_ai import score_confidence as _ai_score
except Exception as e:
    _ai_score = None


def _wrap_score(orig_fn):
    """
    Wrap a scoring function (per node or batch).
    We accept flexible signatures and return the same shape the original returns.
    """
    def wrapped(*args, **kwargs):
        if not (AI_ENABLED and _ai_score):
            return orig_fn(*args, **kwargs)

        # Try to get per-node scoring inputs from common names/shapes.
        # If the original already handles batching, we loop through items if needed.
        try:
            # Case A: explicit node/evidence kwargs
            if "node" in kwargs and "evidence" in kwargs:
                return _ai_score(kwargs["node"], kwargs["evidence"])

            # Case B: positional node/evidence
            if len(args) >= 2 and isinstance(args[0], dict) and isinstance(args[1], dict):
                return _ai_score(args[0], args[1])

            # Case C: batch structure
            if "items" in kwargs and isinstance(kwargs["items"], list):
                out = []
                for item in kwargs["items"]:
                    node = item.get("node", {})
                    evidence = item.get("evidence", {})
                    out.append(_ai_score(node, evidence))
                return out

            # Fallback to original if shapes are unknown
            return orig_fn(*args, **kwargs)
        except Exception:
            # Never break the original behavior
            return orig_fn(*args, **kwargs)
    return wrapped


# ---- Monkey-patch likely scoring callpoints if they exist ----
LIKELY_SCORE_NAMES = [
    "score_confidence",      # ideal
    "compute_ucn_rr",        # common
    "score_node",            # alt
    "recalculate_scores",    # batch
]

for _name in LIKELY_SCORE_NAMES:
    if hasattr(_orig, _name):
        setattr(_orig, _name, _wrap_score(getattr(_orig, _name)))

# ---- Re-export everything from the original module so existing imports keep working ----
globals().update({k: v for k, v in _orig.__dict__.items() if not k.startswith("_")})

if __name__ == "__main__":
    if hasattr(_orig, "main"):
        sys.exit(_orig.main())