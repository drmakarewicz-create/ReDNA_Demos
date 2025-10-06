#!/usr/bin/env python3
import os, sys, requests

CORE = os.environ.get("CORE_URL", "http://localhost:8010")

def main():
    if len(sys.argv) < 2:
        print("Usage: reconcile_cli.py USER_ID | ALL")
        sys.exit(1)
    target = sys.argv[1]
    if target.upper() == "ALL":
        r = requests.post(f"{CORE}/reconcile_all", timeout=60)
    else:
        r = requests.post(f"{CORE}/reconcile/{target}", timeout=30)
    print(r.status_code, r.text)

if __name__ == "__main__":
    main()