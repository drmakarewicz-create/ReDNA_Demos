# resolved_viewer.py
import sys, json, requests

CORE_URL = "http://127.0.0.1:8015"
user_id = sys.argv[1] if len(sys.argv) > 1 else "harness_user"

r = requests.get(f"{CORE_URL}/resolved/{user_id}")
if r.status_code != 200:
    print(f"Core returned {r.status_code}. Is Core running?")
    sys.exit(1)

doc = r.json()
resolved = doc.get("resolved", {})
print(f"User: {user_id} | Traits: {len(resolved)}\n")
for k in sorted(resolved.keys()):
    v = resolved[k]
    val = v.get("resolved_value", v.get("value", v))
    ucn = v.get("ucn")
    print(f"- {k}: {val}  (UCN={ucn})")
    