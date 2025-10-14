#!/usr/bin/env bash
set -euo pipefail

# Compress aged telemetry logs to keep working sets manageable.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "This script must be run inside a Git repository." >&2
  exit 1
fi

cd "${REPO_ROOT}"

OPS_DIR="docs/ops"
LOG_PATH="${OPS_DIR}/ROTATION_LOG.md"
CUTOFF_DAYS=30
HUGE_THRESHOLD=$((100 * 1024 * 1024)) # 100 MB

mkdir -p "${OPS_DIR}"
touch "${LOG_PATH}"

log_line() {
  echo "$1" | tee -a "${LOG_PATH}" >/dev/null
}

file_size_bytes() {
  local target="$1"
  stat -f%z "${target}" 2>/dev/null || stat -c%s "${target}"
}

file_mtime_date() {
  python3 - "$1" <<'PYCODE'
import os
import sys
from datetime import datetime

path = sys.argv[1]
try:
    mtime = os.path.getmtime(path)
except OSError:
    print("unknown")
else:
    print(datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"))
PYCODE
}

mapfile -t telemetry_dirs < <(
  find ReDNACoreDemo/data data -type d -name telemetry 2>/dev/null | sort -u
)

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
log_line("")
log_line("## Telemetry Rotation run @ ${timestamp}")

if [[ ${#telemetry_dirs[@]} -eq 0 ]]; then
  log_line("- No telemetry directories found.")
  exit 0
fi

log_line("- Telemetry directories scanned: ${#telemetry_dirs[@]}")

compressed_files=()
archived_files=()

for dir in "${telemetry_dirs[@]}"; do
  while IFS= read -r -d '' file; do
    gz_file="${file}.gz"
    if [[ ! -f "${gz_file}" ]]; then
      gzip -kf "${file}"
      compressed_files+=("${gz_file}")
    fi

    if [[ -f "${gz_file}" ]]; then
      size_bytes="$(file_size_bytes "${gz_file}")"
      if [[ "${size_bytes}" =~ ^[0-9]+$ ]] && (( size_bytes > HUGE_THRESHOLD )); then
        archive_date="$(file_mtime_date "${file}")"
        archive_dir="${dir}/archives/${archive_date}"
        mkdir -p "${archive_dir}"
        archive_target="${archive_dir}/$(basename "${gz_file}")"
        if [[ ! -f "${archive_target}" ]]; then
          cp "${gz_file}" "${archive_target}"
          archived_files+=("${archive_target}")
        fi
      fi
    fi
  done < <(find "${dir}" -maxdepth 1 -type f \( -name "*.jsonl" -o -name "agent_activity.jsonl" \) -mtime +${CUTOFF_DAYS} -print0)
done

if [[ ${#compressed_files[@]} -eq 0 && ${#archived_files[@]} -eq 0 ]]; then
  log_line("- No files older than ${CUTOFF_DAYS} days required rotation.")
else
  if [[ ${#compressed_files[@]} -gt 0 ]]; then
    log_line("- Compressed files:")
    for file in "${compressed_files[@]}"; do
      log_line("  - ${file}")
    done
  fi
  if [[ ${#archived_files[@]} -gt 0 ]]; then
    log_line("- Archived large artifacts:")
    for file in "${archived_files[@]}"; do
      log_line("  - ${file}")
    done
  fi
fi

echo "Rotation complete. See ${LOG_PATH} for details."
