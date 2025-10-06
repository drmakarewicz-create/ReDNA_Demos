#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$1"
}

result_pass() {
  printf '\n✅ CI quick checks PASSED\n'
}

result_fail() {
  printf '\n❌ CI quick checks FAILED\n' >&2
}

trap 'result_fail' ERR

log "Python bytecode compile"
python3 -m compileall ReDNACoreDemo ExplorerDev ExplorerFinal

log "Python unit tests"
python3 -m unittest discover -s ReDNACoreDemo/tests -t .

log "Dev Explorer bytecode smoke"
python3 -m compileall ExplorerDev/ui ExplorerDev/tests >/dev/null

if command -v npm >/dev/null 2>&1 && [ -f "$ROOT_DIR/web/package.json" ]; then
  log "npm lint"
  (cd "$ROOT_DIR/web" && npm run lint)
  log "npm build"
  (cd "$ROOT_DIR/web" && npm run build)
else
  log "Skipping web lint/build (npm not available)"
fi

trap - ERR
result_pass()
