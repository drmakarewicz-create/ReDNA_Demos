#!/usr/bin/env python3
import sys
import json
import datetime
import pathlib

log = pathlib.Path("docs/automation_log/changes.jsonl")
log.parent.mkdir(parents=True, exist_ok=True)

try:
    entry = json.loads(sys.stdin.read())
except Exception as e:
    print("ERROR: invalid JSON on stdin:", e)
    sys.exit(1)

if "ts" not in entry:
    entry["ts"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

print("Appended to", log)
