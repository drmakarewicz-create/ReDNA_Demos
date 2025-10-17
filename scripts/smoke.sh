#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${SMOKE_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$SMOKE_PYTHON_BIN"
else
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

USE_CONFIG_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --use-config-only)
      USE_CONFIG_ONLY=1
      shift
      ;;
    *)
      echo "usage: smoke.sh [--use-config-only]" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "error: python3 not found; set SMOKE_PYTHON_BIN to a valid interpreter" >&2
    exit 1
  fi
fi

export PYTHON_BIN

http_get_json() {
  local url="$1" attempts="${2:-1}" delay="${3:-0.5}" verify="${4:-1}"
  local body
  for ((i=1; i<=attempts; i++)); do
    echo "→ fetching JSON from $url (attempt $i/$attempts)"
    body="$(curl -fsS --max-time 5 --retry 2 --retry-delay 0 "$url" || true)"
    if [[ -n "$body" ]]; then
      if (( verify )); then
        if "$PYTHON_BIN" -c 'import json, sys; json.loads(sys.stdin.read())' >/dev/null 2>&1 <<<"$body"; then
          printf '%s' "$body"
          return 0
        fi
        echo "(!) Invalid JSON from $url (attempt $i/$attempts)" >&2
      else
        printf '%s' "$body"
        return 0
      fi
    else
      echo "(!) Empty response from $url (attempt $i/$attempts)" >&2
    fi
    if (( i < attempts )); then
      sleep "$delay"
    fi
  done
  return 1
}

extract_port() {
  local url=$1
  "$PYTHON_BIN" - "$url" <<'PY'
import sys
from urllib.parse import urlparse

parsed = urlparse(sys.argv[1])
if parsed.port:
    print(parsed.port)
elif parsed.scheme == "https":
    print(443)
else:
    print(80)
PY
}

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

wait_for_http() {  # wait_for_http URL LABEL [tries] [sleep]
  local url="$1" label="$2" tries="${3:-40}" sleep_s="${4:-0.5}"
  echo "→ waiting for $label at $url"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      echo "✓ $label ready"
      return 0
    fi
    printf '.'
    sleep "$sleep_s"
  done
  echo
  echo "✖ timeout waiting for $label ($url)"
  return 1
}

# Base URLs (allow overrides)
DEVX_BASE_DEFAULT="http://127.0.0.1:${DEVX_BACKEND_PORT:-8100}"
CORE_BASE_ENV="${CORE_BASE:-http://127.0.0.1:8001}"
UCNRR_BASE_ENV="${UCNRR_BASE:-http://127.0.0.1:8011}"
DEVX_BASE_ENV="${DEVX_BASE:-$DEVX_BASE_DEFAULT}"

CORE_BASE_ENV="${CORE_BASE_ENV%/}"
UCNRR_BASE_ENV="${UCNRR_BASE_ENV%/}"
DEVX_BASE_ENV="${DEVX_BASE_ENV%/}"

CONFIG_PAYLOAD=""
CONFIG_CONTEXT=""
FAST_DEFAULT=0

if [[ "${STACK_CONFIG_ONLY_FAST:-0}" == "1" && -z "${STACK_CONFIG_JSON:-}" ]]; then
  FAST_DEFAULT=1
fi

if (( ! FAST_DEFAULT )); then
  if [[ -n "${STACK_CONFIG_JSON:-}" ]]; then
    CONFIG_PAYLOAD="$STACK_CONFIG_JSON"
    CONFIG_CONTEXT="STACK_CONFIG_JSON"
  elif [[ -f "$ROOT_DIR/scripts/stack_config.py" ]]; then
    HELPER_JSON="$("$PYTHON_BIN" "$ROOT_DIR/scripts/stack_config.py" --devx-base "$DEVX_BASE_ENV" --print=json 2>/dev/null || true)"
    if [[ -n "$HELPER_JSON" ]]; then
      CONFIG_PAYLOAD="$HELPER_JSON"
      CONFIG_CONTEXT="${DEVX_BASE_ENV}/devx/api/stack/config"
    fi
  fi
fi

CORE_BASE=""
UCNRR_BASE=""
DEVX_BASE=""
CORE_PORT=""
UCNRR_PORT=""
DEVX_PORT=""
CORE_SOURCE=""
UCNRR_SOURCE=""
DEVX_SOURCE=""
WARNINGS_TEXT=""
HAS_PORT_MISMATCH="false"

if [[ -n "$CONFIG_PAYLOAD" ]]; then
  PARSED_CONFIG="$(
    __STACK_CONFIG_JSON="$CONFIG_PAYLOAD" "$PYTHON_BIN" - <<'PY' 2>/dev/null
import json
import os

cfg = json.loads(os.environ["__STACK_CONFIG_JSON"])
fields = [
    ("CORE_BASE", "core_base"),
    ("UCNRR_BASE", "ucnrr_base"),
    ("DEVX_BASE", "devx_base"),
    ("CORE_PORT", "core_port"),
    ("UCNRR_PORT", "ucnrr_port"),
    ("DEVX_PORT", "devx_port"),
]
for key, attr in fields:
    value = cfg.get(attr)
    print(f"{key}={value}")

source = cfg.get("source") or {}
print(f"CORE_SOURCE={source.get('core_base', '')}")
print(f"UCNRR_SOURCE={source.get('ucnrr_base', '')}")
print(f"DEVX_SOURCE={source.get('devx_base', '')}")

warnings = cfg.get("warnings") or []
print("WARNINGS_TEXT=" + ", ".join(str(item) for item in warnings))
print("HAS_PORT_MISMATCH=" + ("true" if any(str(item).endswith('_port_mismatch') for item in warnings) else "false"))
PY
  )"
  if [[ -z "$PARSED_CONFIG" ]]; then
    echo "error: failed to parse stack config JSON" >&2
    exit 1
  fi
  while IFS='=' read -r key value; do
    case "$key" in
      CORE_BASE) CORE_BASE="$value" ;;
      UCNRR_BASE) UCNRR_BASE="$value" ;;
      DEVX_BASE) DEVX_BASE="$value" ;;
      CORE_PORT) CORE_PORT="$value" ;;
      UCNRR_PORT) UCNRR_PORT="$value" ;;
      DEVX_PORT) DEVX_PORT="$value" ;;
      CORE_SOURCE) CORE_SOURCE="${value:-CONFIG}" ;;
      UCNRR_SOURCE) UCNRR_SOURCE="${value:-CONFIG}" ;;
      DEVX_SOURCE) DEVX_SOURCE="${value:-CONFIG}" ;;
      WARNINGS_TEXT) WARNINGS_TEXT="$value" ;;
      HAS_PORT_MISMATCH) HAS_PORT_MISMATCH="$value" ;;
    esac
  done <<< "$PARSED_CONFIG"
else
  if (( USE_CONFIG_ONLY )); then
    echo "error: --use-config-only requires STACK_CONFIG_JSON or scripts/stack_config.py" >&2
    exit 1
  fi
  CORE_BASE="$CORE_BASE_ENV"
  UCNRR_BASE="$UCNRR_BASE_ENV"
  DEVX_BASE="$DEVX_BASE_ENV"
  CORE_PORT="$(extract_port "$CORE_BASE")"
  UCNRR_PORT="$(extract_port "$UCNRR_BASE")"
  DEVX_PORT="$(extract_port "$DEVX_BASE")"
  CORE_SOURCE="ENV"
  UCNRR_SOURCE="ENV"
  DEVX_SOURCE="ENV"
  CONFIG_CONTEXT="environment"
fi

CORE_BASE="${CORE_BASE%/}"
UCNRR_BASE="${UCNRR_BASE%/}"
DEVX_BASE="${DEVX_BASE%/}"

DEVX_BACKEND_PORT="$DEVX_PORT"
DEVX_CORE_BASE="$CORE_BASE"
DEVX_UCNRR_BASE="$UCNRR_BASE"

export CORE_BASE UCNRR_BASE DEVX_BASE CORE_PORT UCNRR_PORT DEVX_PORT DEVX_BACKEND_PORT DEVX_CORE_BASE DEVX_UCNRR_BASE

if [[ -z "$CONFIG_CONTEXT" ]]; then
  CONFIG_CONTEXT="${DEVX_BASE_ENV}/devx/api/stack/config"
fi

echo "🧭 Resolved stack config (${CONFIG_CONTEXT})"
printf '  core_base : %s (port %s, source %s)\n' "$CORE_BASE" "$CORE_PORT" "$CORE_SOURCE"
printf '  ucnrr_base: %s (port %s, source %s)\n' "$UCNRR_BASE" "$UCNRR_PORT" "$UCNRR_SOURCE"
printf '  devx_base : %s (port %s, source %s)\n' "$DEVX_BASE" "$DEVX_PORT" "$DEVX_SOURCE"
if [[ -n "$WARNINGS_TEXT" ]]; then
  printf '  warnings  : %s\n' "$WARNINGS_TEXT"
fi
if [[ "$HAS_PORT_MISMATCH" == "true" ]]; then
  printf '\033[31m⚠  Port mismatch warnings detected – using resolved config values.\033[0m\n'
fi
if [[ "$USE_CONFIG_ONLY" -eq 1 ]]; then
  echo "--use-config-only: shell environment overrides ignored."
fi

if [[ "${STACK_CONFIG_ONLY_FAST:-0}" == "1" ]]; then
  SMOKE_START_TS=$(date +%s)
  echo ""
  echo "SMOKE OK — $(date '+%Y-%m-%d %H:%M:%S') [elapsed: 0s]"
  exit 0
fi

SMOKE_START_TS=$(date +%s)

# 1) Start DevX backend if not listening
if ! lsof -iTCP:"$DEVX_PORT" -sTCP:LISTEN -nP >/dev/null 2>&1; then
  "$PYTHON_BIN" -m uvicorn ReDNACoreDemo.devx.backend.api:app \
    --host 127.0.0.1 --port "$DEVX_PORT" >/dev/null 2>&1 &
  wait_for_port "$DEVX_PORT"
  if ! wait_for_http "${DEVX_BASE}/health" "DevX /health"; then
    echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
    tail -n 80 ~/.redna/logs/stack.log || true
    exit 1
  fi
fi

# 2) Start UCNRR if not listening
if ! lsof -iTCP:"$UCNRR_PORT" -sTCP:LISTEN -nP >/dev/null 2>&1; then
  "$PYTHON_BIN" -m uvicorn UCN_RR_Demo.ucnrr_app:app \
    --host 127.0.0.1 --port "$UCNRR_PORT" >/dev/null 2>&1 &
  wait_for_port "$UCNRR_PORT"
  if ! wait_for_http "${UCNRR_BASE}/health" "UCNRR /health"; then
    echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
    tail -n 80 ~/.redna/logs/stack.log || true
    exit 1
  fi
fi

# 3) Start Core if not listening
if ! lsof -iTCP:"$CORE_PORT" -sTCP:LISTEN -nP >/dev/null 2>&1; then
  "$PYTHON_BIN" -m uvicorn ReDNACoreDemo.core.api:app \
    --host 127.0.0.1 --port "$CORE_PORT" >/dev/null 2>&1 &
  wait_for_port "$CORE_PORT"
  if ! wait_for_http "${CORE_BASE}/health" "Core /health"; then
    echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
    tail -n 80 ~/.redna/logs/stack.log || true
    exit 1
  fi
  echo "(started core $CORE_PORT)"
fi

# 4) Health probes
if ! wait_for_http "${UCNRR_BASE}/health" "UCNRR /health"; then
  echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
  tail -n 80 ~/.redna/logs/stack.log || true
  exit 1
fi
if ! wait_for_http "${CORE_BASE}/health" "Core /health"; then
  echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
  tail -n 80 ~/.redna/logs/stack.log || true
  exit 1
fi
if ! wait_for_http "${DEVX_BASE}/health" "DevX /health"; then
  echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
  tail -n 80 ~/.redna/logs/stack.log || true
  exit 1
fi

# 5) Contracts
"$PYTHON_BIN" - <<'PY'
import os
import httpx

core_base = os.getenv("CORE_BASE", "http://127.0.0.1:8001").rstrip("/")

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

r1 = httpx.post(
    f"{core_base}/core/api/ingest_evidence",
    json=good,
    timeout=5,
)
assert r1.status_code == 200 and r1.json().get("ok") is True, r1.text

r2 = httpx.post(
    f"{core_base}/core/api/ingest_evidence",
    json=bad,
    timeout=5,
)
assert r2.status_code == 400 and r2.json().get("error") == "EVIDENCE_VALIDATION_FAILED", r2.text
PY

# 6) Readiness + resilience check via DevX
READINESS_OUTPUT="$("$PYTHON_BIN" <<'PY'
import json
import os
import subprocess
import sys

import httpx

from ReDNACoreDemo.devx.backend.readiness_client import poll_stack_readiness

devx_base = os.getenv("DEVX_BASE", "http://127.0.0.1:8100").rstrip("/")
core_base = os.getenv("CORE_BASE", "http://127.0.0.1:8001").rstrip("/")

client = httpx.Client(timeout=httpx.Timeout(connect=1.0, read=2.5, write=2.5, pool=2.5))

def seed_window() -> None:
    cmd = f'for i in {{1..50}}; do curl -s "{core_base}/health" >/dev/null; sleep 0.1; done'
    subprocess.run(["bash", "-lc", cmd], check=False)
    print("(seeded window)")

def trigger_restart() -> None:
    response = client.post(
        f"{devx_base}/devx/api/stack/restart",
        json={"services": ["core", "ucnrr"], "reason": "smoke_auto_recovery", "force": False},
        timeout=10,
    )
    response.raise_for_status()

result = poll_stack_readiness(
    devx_base=devx_base,
    core_base=core_base,
    session=client,
    seed_func=seed_window,
    restart_func=trigger_restart,
)

if result.ready:
    print(f"READY {int(result.resilience_used)} {int(result.seeded)}")
    client.close()
    sys.exit(0)

print("FAIL")
print(json.dumps(result.last_payload or {}))
print(result.last_error or "")
client.close()
sys.exit(1)
PY
)"
READINESS_EXIT=$?

mapfile -t readiness_lines <<< "$READINESS_OUTPUT"

if [[ $READINESS_EXIT -ne 0 ]]; then
  echo "CORE_BASE=$CORE_BASE UCNRR_BASE=$UCNRR_BASE DEVX_BASE=$DEVX_BASE"
  fail_json="${readiness_lines[1]:-"{}"}"
  fail_reason="${readiness_lines[2]:-}"
  if [[ -n "$fail_json" ]]; then
    if ! "$PYTHON_BIN" -c '
import json
import sys

text = sys.stdin.read()
try:
    data = json.loads(text)
except Exception:  # noqa: BLE001
    raise SystemExit(1)

json.dump(data, sys.stdout, indent=2)
sys.stdout.write("\n")
' <<<"$fail_json"; then
      printf '%s\n' "$fail_json"
    fi
  fi
  if [[ -n "$fail_reason" ]]; then
    echo "$fail_reason" >&2
  fi
  if readiness_payload=$(http_get_json "${DEVX_BASE}/devx/api/stack/ready" 2 0.5 1 2>/dev/null); then
    echo "--- latest readiness payload ---"
    "$PYTHON_BIN" -c '
import json
import sys

text = sys.stdin.read()
try:
    data = json.loads(text)
except Exception:  # noqa: BLE001
    raise SystemExit(1)

json.dump(data, sys.stdout, indent=2)
sys.stdout.write("\n")
' <<<"$readiness_payload" || printf '%s\n' "$readiness_payload"
  fi
  echo "--- stack.log (last 80 lines) ---"
  tail -n 80 ~/.redna/logs/stack.log || true
  exit $READINESS_EXIT
fi

for line in "${readiness_lines[@]}"; do
  if [[ "$line" == "(seeded window)" ]]; then
    echo "$line"
  fi
done

ready_line="${readiness_lines[${#readiness_lines[@]}-1]}"
read -r _ RESILIENCE_USED SEEDED_FLAG <<< "$ready_line"

END_TS=$(date +%s)
ELAPSED=$((END_TS - SMOKE_START_TS))
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

if [[ "$RESILIENCE_USED" == "1" ]]; then
  echo "SMOKE OK (RESILIENCE) — ${TIMESTAMP} [elapsed: ${ELAPSED}s]"
else
  echo "SMOKE OK — ${TIMESTAMP} [elapsed: ${ELAPSED}s]"
fi
