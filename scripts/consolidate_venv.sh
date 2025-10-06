#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/consolidate_venv.sh

Consolidate Python virtual environments by merging package requirements into the
root .venv, backing up nested venvs, and updating requirements.lock.
USAGE
}

if [[ "${1-}" == "-h" || "${1-}" == "--help" ]]; then
  usage
  exit 0
fi

ROOT="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
ROOT_VENV="$ROOT/.venv"
SUB_VENV="$ROOT/PhotoRefinementCoach/.venv"
ARCHIVE="$ROOT/archive"
DO_RUN="${RUN:-0}"

log() {
  printf '[consolidate_venv] %s\n' "$*"
}

err() {
  printf '[consolidate_venv][ERROR] %s\n' "$*" >&2
}

mkdir -p "$ROOT/scripts" "$ARCHIVE"

FREEZE_ROOT="$ARCHIVE/_freeze_root.txt"
FREEZE_SUB="$ARCHIVE/_freeze_photoref.txt"
MERGED_REQ="$ARCHIVE/requirements.merge.txt"

log "Root repo: $ROOT"
log "Root venv: $ROOT_VENV"
log "Nested venv: $SUB_VENV"
log "Archive: $ARCHIVE"

if [[ "$DO_RUN" != "1" ]]; then
  log "Dry run (set RUN=1 to execute). Planned steps:"
  log "  1. Freeze packages from root and nested venvs (if present)."
  log "  2. Recreate/refresh root venv and install merged requirements."
  log "  3. Freeze consolidated environment to requirements.lock."
  log "  4. Backup nested venv to archive/venv_backup_<timestamp>/ and remove the original."
  exit 0
fi

log "Executing consolidation (RUN=1)."

mkdir -p "$ROOT/scripts" "$ARCHIVE"

: > "$FREEZE_ROOT"
: > "$FREEZE_SUB"

if [[ -x "$ROOT_VENV/bin/pip" ]]; then
  log "Freezing packages from root venv"
  if ! "$ROOT_VENV/bin/pip" freeze > "$FREEZE_ROOT"; then
    err "Failed to freeze root venv packages"
    exit 1
  fi
else
  log "Root venv pip not found; will bootstrap a new one"
fi

if [[ -x "$SUB_VENV/bin/pip" ]]; then
  log "Freezing packages from nested venv"
  if ! "$SUB_VENV/bin/pip" freeze > "$FREEZE_SUB"; then
    err "Failed to freeze nested venv packages"
    exit 1
  fi
else
  log "Nested venv not present (nothing to merge)"
fi

log "Merging frozen requirements"
cat "$FREEZE_ROOT" "$FREEZE_SUB" 2>/dev/null | sort -u > "$MERGED_REQ"

if [[ ! -d "$ROOT_VENV" ]]; then
  log "Creating root venv at $ROOT_VENV"
  python3 -m venv "$ROOT_VENV"
fi

if [[ ! -x "$ROOT_VENV/bin/activate" ]]; then
  err "Root venv activate script missing at $ROOT_VENV/bin/activate"
  exit 1
fi

# shellcheck disable=SC1090
source "$ROOT_VENV/bin/activate"

log "Upgrading pip & wheel"
pip install -U pip wheel

if [[ -f "$ROOT/requirements.txt" ]]; then
  log "Installing requirements.txt"
  pip install -r "$ROOT/requirements.txt" || log "requirements.txt install returned non-zero; continuing"
fi

if [[ -s "$MERGED_REQ" ]]; then
  log "Installing merged requirements"
  pip install -r "$MERGED_REQ" || log "Merged requirements install returned non-zero; continuing"
else
  log "No additional merged requirements to install"
fi

log "Freezing final environment to requirements.lock"
pip freeze > "$ROOT/requirements.lock"

deactivate || true

if [[ -d "$SUB_VENV" ]]; then
  STAMP=$(date +%Y%m%dT%H%M%S)
  BACKUP="$ARCHIVE/venv_backup_$STAMP"
  log "Backing up nested venv to $BACKUP"
  mv "$SUB_VENV" "$BACKUP"
  log "Nested venv moved to $BACKUP"
fi

PY_BIN="$ROOT_VENV/bin/python"
if ! "$PY_BIN" -c 'import sys; print(sys.executable)' >/dev/null 2>&1; then
  err "Root python interpreter check failed at $PY_BIN"
  err "Please inspect logs and rerun consolidate_venv.sh"
  exit 1
fi

log "Consolidation complete. Root interpreter: $PY_BIN"
exit 0
