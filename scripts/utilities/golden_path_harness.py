# golden_path_harness.py
"""
Golden Path Harness for ReDNA (Corrected Core endpoint)
------------------------------------------------------
What it does:
  1) POSTs test sentences to UCN/RR (/ingest_text)
  2) GETs Core's resolved doc at /resolved/<user_id>
  3) Prints PASS/FAIL for the trait path you expect

How to run:
  - Ensure Core (app.py) is running on port 8015
  - Ensure UCN/RR (ucnrr_app.py) is running on port 8011
  - (Optional) export UCNRR_USE_MIN_HEURISTICS=true for guaranteed test hits
  - python golden_path_harness.py
"""

import time
import json
import requests

UCNRR_URL = "http://127.0.0.1:8017"
CORE_URL  = "http://127.0.0.1:8015"

# Use a user id that you actually use (or keep harness_user)
USER_ID = "harness_user"

TEST_CASES = [
    ("I'm around 6 feet.", "PaDNA.BodyDNA.Height"),              # expecting any height path under BodyDNA
    ("I've been a husband for 25 years.", "SocDNA.Relationship"),# expecting relationship signals
    ("My eyes are dark brown.", "Eye"),                           # broad match to eye traits
    ("The little bit of hair I have left is red.", "Hair"),       # hair color/balding
]

def send_text_to_ucnrr(user_id: str, text: str):
    payload = {
        "schema_version": "explorer.text/1.0",
        "user_id": user_id,
        "text": text,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provenance": {"actor": "user", "source": "harness"}
    }
    r = requests.post(f"{UCNRR_URL}/ingest_text", json=payload)
    return r.status_code, r.text

def fetch_core_resolved(user_id: str):
    # Correct Core endpoint
    r = requests.get(f"{CORE_URL}/health")
    health_ok = (r.status_code == 200)
    try:
        health = r.json()
    except Exception:
        health = {"_raw": r.text}

    r2 = requests.get(f"{CORE_URL}/resolved/{user_id}")
    status = r2.status_code
    try:
        resolved = r2.json() if status == 200 else None
    except Exception:
        resolved = None

    return health_ok, health, status, resolved

def contains_path_fragment(resolved_doc, fragment: str) -> bool:
    if not isinstance(resolved_doc, dict):
        return False
    # resolved_doc schema: {"user_id":..., "schema_version":4, "resolved": {dotpath: {..}, ...}}
    resolved_map = resolved_doc.get("resolved", {})
    payload_str = json.dumps(resolved_map, ensure_ascii=False)
    return (fragment in payload_str)

def run_tests():
    print("Running Golden Path Harness (corrected)...\n")
    for sentence, expected_fragment in TEST_CASES:
        print(f"➤ Test text: {sentence}")
        code, resp = send_text_to_ucnrr(USER_ID, sentence)
        print(f"  UCN/RR response [{code}]: {resp[:300]}{'...' if len(resp)>300 else ''}")

        # Give Core a moment to ingest + write
        time.sleep(2.0)

        health_ok, health, status, resolved = fetch_core_resolved(USER_ID)
        if not health_ok:
            print(f"  FAIL: Core /health not OK: {health}\n")
            continue

        if status != 200 or not resolved:
            print(f"  FAIL: Core /resolved/{USER_ID} status={status} (no resolved doc)\n")
            continue

        found = contains_path_fragment(resolved, expected_fragment)
        if found:
            print(f"  PASS: Found '{expected_fragment}' in Core resolved map\n")
        else:
            # Print a tiny peek (first few keys) to help debugging without overwhelming
            keys = list((resolved.get('resolved') or {}).keys())[:8]
            print(f"  FAIL: Missing '{expected_fragment}'. Core keys sample: {keys}\n")

if __name__ == "__main__":
    run_tests()
