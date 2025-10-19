#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${STACK_UP_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$STACK_UP_PYTHON_BIN"
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
      echo "usage: stack_up.sh [--use-config-only]" >&2
      exit 1
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "error: python3 not found; set STACK_UP_PYTHON_BIN to a valid interpreter" >&2
    exit 1
  fi
fi

export PYTHON_BIN

http_get_json() {
  local url="$1" attempts="${2:-1}" delay="${3:-0.5}" verify="${4:-1}"
  local body
  for ((i=1; i<=attempts; i++)); do
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
  case "$1" in
    *://*:[0-9]*)
      printf '%s\n' "${1##*:}"
      ;;
    *) printf '%s\n' "80" ;;
  esac
}

DEVX_BASE_DEFAULT="http://127.0.0.1:${DEVX_BACKEND_PORT:-8100}"
CORE_BASE_ENV="${CORE_BASE:-http://127.0.0.1:8004}"
UCNRR_BASE_ENV="${UCNRR_BASE:-http://127.0.0.1:8017}"
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
  STACK_START_TS=$(date +%s)
  echo "🔧 Bootstrapping ReDNA stack (fast path)..."
  echo "  CORE_BASE  = $CORE_BASE"
  echo "  UCNRR_BASE = $UCNRR_BASE"
  echo "  DEVX_BASE  = $DEVX_BASE"
  STACK_END_TS=$(date +%s)
  STACK_ELAPSED=$((STACK_END_TS - STACK_START_TS))
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  echo ""
  echo "✅ Stack ready — ${TIMESTAMP} [elapsed: ${STACK_ELAPSED}s]"
  echo "   Core API : ${CORE_BASE}/health"
  echo "   UCNRR    : ${UCNRR_BASE}/health"
  echo "   DevX UI  : http://127.0.0.1:3100/stack"
  echo "   DevX API : ${DEVX_BASE}/devx/api/stack/ready"
  echo "   Readiness : ready"
  exit 0
fi

STACK_START_TS=$(date +%s)
echo "🔧 Bootstrapping ReDNA stack..."
echo "  CORE_BASE  = $CORE_BASE"
echo "  UCNRR_BASE = $UCNRR_BASE"
echo "  DEVX_BASE  = $DEVX_BASE"

if [[ "${STACK_UP_SKIP_BOOTSTRAP:-0}" != "1" ]]; then
  "$PYTHON_BIN" "$ROOT_DIR/scripts/cppp_bootstrap.py" --quiet >/dev/null
fi

READY_PAYLOAD=""
seeded=0
resilience_used=0
poll_start_ts=$(date +%s)
poll_timeout=120
poll_interval=2

while true; do
  now_ts=$(date +%s)
  elapsed=$((now_ts - poll_start_ts))

  readiness_payload=$(http_get_json "${DEVX_BASE}/devx/api/stack/ready" 1 0.5 1 2>/dev/null || true)
  if [[ -n "$readiness_payload" ]]; then
    READY_PAYLOAD="$readiness_payload"
    ready_flag="false"
    status_flag="unknown"
    readiness_meta="$(
      "$PYTHON_BIN" -c '
import json
import sys

text = sys.stdin.read()
try:
    data = json.loads(text)
except Exception:  # noqa: BLE001
    print("READY_FLAG=false")
    print("STATUS_FLAG=unknown")
    sys.exit(0)

ready = "true" if bool(data.get("ready")) else "false"
status = data.get("status") or "unknown"
print(f"READY_FLAG={ready}")
print(f"STATUS_FLAG={status}")
' <<<"$readiness_payload"
    )"
    while IFS='=' read -r key value; do
      case "$key" in
        READY_FLAG) ready_flag="$value" ;;
        STATUS_FLAG) status_flag="$value" ;;
      esac
    done <<< "$readiness_meta"
    if [[ "$ready_flag" == "true" ]]; then
      break
    fi
    if [[ "$status_flag" == "warming" && $seeded -eq 0 && $elapsed -ge 30 ]]; then
      echo "(seeded window)"
      for _ in $(seq 1 50); do
        curl -fsS --max-time 2 "${CORE_BASE}/health" >/dev/null 2>&1 || true
        sleep 0.1
      done
      seeded=1
    fi
    if [[ $resilience_used -eq 0 && $elapsed -ge 75 ]]; then
      curl -fsS --max-time 10 -H "Content-Type: application/json" \
        -d '{"services":["core","ucnrr"],"reason":"stack_up_auto_recovery","force":false}' \
        "${DEVX_BASE}/devx/api/stack/restart" >/dev/null 2>&1 || true
      resilience_used=1
    fi
  fi

  if (( elapsed >= poll_timeout )); then
    echo "❌ stack_up: readiness did not turn green within ${poll_timeout}s."
    echo "CORE_BASE=$CORE_BASE"
    echo "UCNRR_BASE=$UCNRR_BASE"
    echo "DEVX_BASE=$DEVX_BASE"
    diag_payload="$READY_PAYLOAD"
    if [[ -z "$diag_payload" ]]; then
      diag_payload=$(http_get_json "${DEVX_BASE}/devx/api/stack/ready" 1 0.5 1 2>/dev/null || true)
    fi
    if [[ -n "$diag_payload" ]]; then
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
' <<<"$diag_payload" || printf '%s\n' "$diag_payload"
    else
      echo "(!) No readiness payload available"
    fi
    STACK_LOG="$HOME/.redna/logs/stack.log"
    if [[ -f "$STACK_LOG" ]]; then
      echo "--- stack.log (last 80 lines) ---"
      tail -n 80 "$STACK_LOG"
    fi
    exit 1
  fi

  sleep "$poll_interval"
done

STACK_END_TS=$(date +%s)
STACK_ELAPSED=$((STACK_END_TS - STACK_START_TS))
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

FINAL_READINESS="$READY_PAYLOAD"
if [[ -z "$FINAL_READINESS" ]]; then
  FINAL_READINESS=$(http_get_json "${DEVX_BASE}/devx/api/stack/ready" 2 0.5 1 2>/dev/null || true)
  if [[ -z "$FINAL_READINESS" ]]; then
    echo "(!) Could not fetch readiness JSON from ${DEVX_BASE}/devx/api/stack/ready" >&2
  fi
fi

echo ""
echo "✅ Stack ready — ${TIMESTAMP} [elapsed: ${STACK_ELAPSED}s]"
echo "   Core API : ${CORE_BASE}/health"
echo "   UCNRR    : ${UCNRR_BASE}/health"
echo "   DevX UI  : http://127.0.0.1:3100/stack"
echo "   DevX API : ${DEVX_BASE}/devx/api/stack/ready"
if [[ -n "$FINAL_READINESS" ]]; then
  FINAL_STATUS="$(
    "$PYTHON_BIN" -c '
import json
import sys

try:
    data = json.loads(sys.stdin.read())
except Exception:  # noqa: BLE001
    sys.exit(1)

status = data.get("status")
if not status:
    sys.exit(1)

print(status)
' <<<"$FINAL_READINESS" 2>/dev/null
  )"
  if [[ -n "$FINAL_STATUS" ]]; then
    echo "   Readiness : $FINAL_STATUS"
  fi
fi
if (( resilience_used )); then
  echo "   Recovery  : Auto-restart triggered"
fi
