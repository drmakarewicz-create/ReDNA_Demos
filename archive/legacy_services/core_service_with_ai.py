"""
core_service_with_ai.py
Drop this file into ReDNACoreDemo/ and run it to test AI-assisted propagation
WITHOUT modifying your existing core_service.py.

What it does:
- Builds a small sample 'change_event' + 'neighborhood'.
- Calls core_ai_propagation.propose_propagation().
- If REDNA_AI_ENABLED=true and Ollama (llama3) is running, you'll see AI output.
- Otherwise you get the safe fallback plan.

Usage:
  REDNA_AI_ENABLED=true python core_service_with_ai.py
  # (or just) python core_service_with_ai.py  -> fallback plan
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

from core_ai_propagation import propose_propagation  # uses prompt_loader + llama3_client

def pretty(x: Dict[str, Any]) -> str:
    return json.dumps(x, indent=2, ensure_ascii=False)

def demo_change() -> tuple[Dict[str, Any], Dict[str, Any]]:
    change_event = {
        "path": "PaDNA.LooksDNA.EyeDNA.Color",
        "old_value": "brown",
        "new_value": "blue",
        "ts": 1699999999,  # any int/str timestamp
        "provenance": "demo-self-report"
    }
    neighborhood = {
        "parents": ["PaDNA.LooksDNA.EyeDNA", "PaDNA.LooksDNA", "PaDNA"],
        "siblings": ["PaDNA.LooksDNA.EyeDNA.Shape", "PaDNA.LooksDNA.EyeDNA.Size"],
        "cross_links": ["PaDNA.ContactsLensDNA", "EmDNA.MoodDNA"]
    }
    return change_event, neighborhood

def main():
    print("\n=== Core Propagation AI Demo ===")
    print(f"REDNA_AI_ENABLED={os.getenv('REDNA_AI_ENABLED', 'false')}")
    print(f"OLLAMA_MODEL={os.getenv('OLLAMA_MODEL', 'llama3')}\n")

    change_event, neighborhood = demo_change()

    print("Change event:\n", pretty(change_event))
    print("Neighborhood:\n", pretty(neighborhood))

    plan = propose_propagation(change_event, neighborhood)

    print("\nAI (or fallback) propagation plan:\n", pretty(plan))
    print("\nTip: set REDNA_AI_ENABLED=true and start Ollama (llama3) to see AI-driven suggestions.")
    print("You can wire this into your real Core write path once you're comfortable.")
    print()

if __name__ == "__main__":
    main()