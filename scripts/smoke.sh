#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "error: virtual environment not found at $ROOT_DIR/.venv" >&2
  exit 1
fi

wait_for_port() {
  local port=$1
  local attempts=10
  for _ in $(seq 1 "$attempts"); do
    if lsof -iTCP:"$port" -sTCP:LISTEN -nP >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "error: port $port did not become ready" >&2
  return 1
}

# 1) Start DevX backend if not listening
DEVX_PORT="${DEVX_BACKEND_PORT:-8100}"
if ! lsof -iTCP:"$DEVX_PORT" -sTCP:LISTEN -nP >/dev/null; then
  "$PYTHON_BIN" -m uvicorn ReDNACoreDemo.devx.backend.api:app \
    --host 127.0.0.1 --port "$DEVX_PORT" --reload >/dev/null 2>&1 &
  wait_for_port "$DEVX_PORT"
fi

# 2) Start UCNRR if not listening
if ! lsof -iTCP:8011 -sTCP:LISTEN -nP >/dev/null; then
  "$PYTHON_BIN" -m uvicorn UCN_RR_Demo.ucnrr_app:app \
    --host 127.0.0.1 --port 8011 --reload >/dev/null 2>&1 &
  wait_for_port 8011
fi

# 3) Start Core on 8001 if not listening
if ! lsof -iTCP:8001 -sTCP:LISTEN -nP >/dev/null; then
  "$PYTHON_BIN" -m uvicorn ReDNACoreDemo.core.api:build_app \
    --factory --host 127.0.0.1 --port 8001 --reload >/dev/null 2>&1 &
  wait_for_port 8001
fi

# 4) Health probes
curl -fsS http://127.0.0.1:8011/health >/dev/null
curl -fsS http://127.0.0.1:8001/health >/dev/null
curl -fsS "http://127.0.0.1:${DEVX_PORT}/health" >/dev/null

# 5) Contracts
"$PYTHON_BIN" - <<'PY'
import requests

good = {
    "user_id": "smoke_user",
    "evidence": [
        {
            "trait_id": "PaDNA.EyeDNA.IrisColor",
            "value": {"enum": "blue"},
            "source": "smoke",
        }
    ],
}
bad = {
    "user_id": "smoke_user",
    "evidence": [
        {
            "value": {"text": "bad only"},
        }
    ],
}

r1 = requests.post(
    "http://127.0.0.1:8001/core/api/ingest_evidence",
    json=good,
    timeout=5,
)
assert r1.status_code == 200 and r1.json().get("ok") is True, r1.text

r2 = requests.post(
    "http://127.0.0.1:8001/core/api/ingest_evidence",
    json=bad,
    timeout=5,
)
assert r2.status_code == 400 and r2.json().get("error") == "EVIDENCE_VALIDATION_FAILED", r2.text
PY

# 6) Readiness + resilience check
READINESS_OUTPUT="$("$PYTHON_BIN" <<'PY'
import os
import sys
import time
import requests

devx_port = int(os.getenv("DEVX_BACKEND_PORT", "8100"))
base = f"http://127.0.0.1:{devx_port}/devx/api/stack"

deadline = time.time() + 90
restart_after = time.time() + 60
resilience_used = False
last_error = "timeout"

def fetch_ready():
    resp = requests.get(f"{base}/ready", timeout=5)
    resp.raise_for_status()
    return resp.json()

while time.time() < deadline:
    try:
        payload = fetch_ready()
    except Exception as exc:  # pragma: no cover - integration behavior
        last_error = f"ready_error:{exc}"
        time.sleep(3)
        continue

    if payload.get("ready"):
        print(f"READY RESILIENCE_USED={int(resilience_used)}")
        sys.exit(0)

    if not resilience_used and time.time() >= restart_after:
        try:
            response = requests.post(
                f"{base}/restart",
                json={"services": ["core", "ucnrr"], "reason": "smoke_auto_recovery", "force": False},
                timeout=10,
            )
            response.raise_for_status()
            resilience_used = True
            last_error = "auto_recovery_attempted"
        except Exception as exc:  # pragma: no cover
            last_error = f"restart_error:{exc}"

    time.sleep(3)

print(f"ERROR {last_error}", file=sys.stderr)
sys.exit(1)
PY
)"
READINESS_EXIT=$?

if [[ $READINESS_EXIT -ne 0 ]]; then
  echo "$READINESS_OUTPUT" >&2
  exit $READINESS_EXIT
fi

if [[ "$READINESS_OUTPUT" == *"RESILIENCE_USED=1"* ]]; then
  echo "SMOKE OK (RESILIENCE)"
else
  echo "SMOKE OK"
fi
