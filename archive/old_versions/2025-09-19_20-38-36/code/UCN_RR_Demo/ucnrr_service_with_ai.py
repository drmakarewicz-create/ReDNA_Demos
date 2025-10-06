"""
ucnrr_service_with_ai.py
Drop this file into UCN_RR_Demo/ and run it to test AI-assisted scoring
WITHOUT modifying your existing ucnrr_service.py.

What it does:
- Loads small sample nodes/evidence (or you can paste your own JSON).
- If REDNA_AI_ENABLED=true and your local Ollama (llama3) is running,
  it will call the AI scorer (ucn_rr_ai.score_confidence).
- If AI is off/unavailable, it returns a safe baseline (your current behavior).

Usage:
  REDNA_AI_ENABLED=true python ucnrr_service_with_ai.py
  # (or just) python ucnrr_service_with_ai.py  -> baseline fallback

You can adapt this later to call your real data instead of the sample.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Ensure we can import the root-level helpers you added
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ucn_rr_ai import score_confidence  # uses prompt_loader + llama3_client under the hood

def pretty(d: Dict[str, Any]) -> str:
    return json.dumps(d, indent=2, ensure_ascii=False)

def demo_case() -> tuple[Dict[str, Any], Dict[str, Any]]:
    node = {
        "path": "PaDNA.LooksDNA.EyeDNA.Color",
        "prior_ucn": 420.0,     # pretend previous confidence
        "prior_rr": 0.48,       # pretend previous RR
        "last_update_ts": None,
        "preset": "Normal"
    }
    evidence = {
        # You can replace ints with arrays of dicts if you want;
        # the prompt tolerates both.
        "confirmations": 3,
        "neutrals": 1,
        "contradictions": 1,
        "half_life_days": 90
    }
    return node, evidence

def main():
    print("\n=== UCN/RR AI Scoring Demo ===")
    print(f"REDNA_AI_ENABLED={os.getenv('REDNA_AI_ENABLED', 'false')}")
    print(f"OLLAMA_MODEL={os.getenv('OLLAMA_MODEL', 'llama3')}\n")

    node, evidence = demo_case()

    print("Input node:\n", pretty(node))
    print("Input evidence:\n", pretty(evidence))

    out = score_confidence(node, evidence)

    print("\nAI (or baseline) output:")
    print(pretty(out))

    print("\nTip: set REDNA_AI_ENABLED=true and start Ollama (llama3) to see AI-adjusted numbers.")
    print("Ollama quickstart (in another terminal):")
    print("  ollama pull llama3")
    print("  ollama run llama3  # ensures model present")
    print()

if __name__ == "__main__":
    main()