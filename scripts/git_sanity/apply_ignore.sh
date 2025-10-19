#!/usr/bin/env bash
set -euo pipefail

# Apply or preview git ignore hygiene for runtime artifacts.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${REPO_ROOT}" ]]; then
  echo "This script must be run inside a Git repository." >&2
  exit 1
fi

cd "${REPO_ROOT}"

TARGET_BRANCH="chore/git-hygiene"
OPS_DIR="docs/ops"
UNTRACK_FILE="${OPS_DIR}/UNTRACK_DRYRUN.txt"
REVERT_DOC="${OPS_DIR}/GIT_HYGIENE_REVERT.md"
start_branch=""
IGNORE_BLOCK=$'# >>> git-sanity ignore block >>>\n# --- deps & caches ---\n.venv/\nPhotoRefinementCoach/.venv/\n**/node_modules/\n**/.venv/\n__pycache__/\n**/__pycache__/\n*.pyc\n**/.pytest_cache/\n.DS_Store\n**/.DS_Store\n\n# --- build outputs ---\n**/dist/\n**/.vite/\n**/coverage/\nweb/.next/\nsnapshots/full_backup_*\n\n# --- runtime data (ReDNA) ---\nReDNACoreDemo/data/**\nbackups/**\ndata/telemetry/**\nprompts/insights/**\ncontrol_panel_logs/*\n# keep docs in these dirs\n!ReDNACoreDemo/data/README.md\n!backups/README.md\n!data/telemetry/README.md\n!prompts/insights/README.md\n\n# --- generated media ---\n**/*.mp3\n**/*.wav\n**/*.zip\n**/*.gz\n\n*.tar.gz\n# <<< git-sanity ignore block <<<'

show_help() {
  cat <<'EOF'
Usage: apply_ignore.sh [--dry-run] [--apply] [--local]

  --dry-run   Generate docs/ops/UNTRACK_DRYRUN.txt without staging changes.
  --apply     Remove ignored files from the index (git rm --cached) and commit.
  --local     Write patterns to .git/info/exclude instead of .gitignore.

The recommended workflow is:
  1. bash scripts/git_sanity/apply_ignore.sh --dry-run --local
  2. bash scripts/git_sanity/apply_ignore.sh --apply
EOF
}

local_mode=false
do_apply=false
do_dry_run=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      local_mode=true
      ;;
    --apply)
      do_apply=true
      ;;
    --dry-run)
      do_dry_run=true
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      show_help >&2
      exit 1
      ;;
  esac
  shift
done

mkdir -p "${OPS_DIR}"

ensure_ignore_block() {
  local target_file="$1"
  if [[ ! -f "${target_file}" ]]; then
    touch "${target_file}"
  fi
  if ! grep -Fq ">>> git-sanity ignore block >>>" "${target_file}"; then
    printf '\n%s\n' "${IGNORE_BLOCK}" >> "${target_file}"
    echo "Updated ignore patterns in ${target_file}"
  else
    echo "Ignore patterns already present in ${target_file}"
  fi
}

if "${local_mode}"; then
  ensure_ignore_block "$(git rev-parse --git-path info/exclude)"
else
  ensure_ignore_block ".gitignore"
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  start_branch="${current_branch}"
  if [[ "${current_branch}" != "${TARGET_BRANCH}" ]]; then
    if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
      git switch "${TARGET_BRANCH}"
    else
      git switch -c "${TARGET_BRANCH}"
    fi
  fi
fi

echo "Collecting current git status details..."
git status --porcelain | awk '{print $2}' | sed '/^$/d' > "${UNTRACK_FILE}"
echo "Dry-run status written to ${UNTRACK_FILE}"

if ! "${do_apply}"; then
  if ! "${local_mode}"; then
    echo "Dry-run complete on branch $(git rev-parse --abbrev-ref HEAD)."
  else
    echo "Dry-run complete in local ignore mode."
  fi
  exit 0
fi

if "${local_mode}"; then
  echo "--apply cannot be combined with --local; aborting." >&2
  exit 1
fi

before_sha="$(git rev-parse HEAD)"

echo "Removing ignored files from the index (files remain on disk)..."
tracked_ignored="$(git ls-files -z --cached --exclude-standard --ignored)"
if [[ -n "${tracked_ignored}" ]]; then
  printf '%s' "${tracked_ignored}" | xargs -0 git rm -r --cached --ignore-unmatch
else
  echo "No tracked files matched the ignore patterns."
fi

git add .gitignore

cat > "${REVERT_DOC}" <<EOF
# Git Hygiene Revert Instructions

- Created on: $(date '+%Y-%m-%d %H:%M:%S')
- Hygiene branch: \`${TARGET_BRANCH}\`
- Previous branch: \`${start_branch:-unknown}\`
- Pre-hygiene commit: \`${before_sha}\`

## Quick revert

1. \`git switch ${start_branch:-main}\`
2. \`git reset --hard ${before_sha}\`
3. \`git branch -D ${TARGET_BRANCH}\` (if you want to discard the hygiene branch)

Alternatively, you can undo the commit directly:

- \`git reset --hard ${before_sha}\`

Always ensure you have no uncommitted work before running these commands.
EOF

git add "${REVERT_DOC}"

if git diff --cached --quiet; then
  echo "No staged changes detected; nothing to commit."
  exit 0
fi

git commit -m "chore: ignore runtime/build artifacts; keep files on disk."
echo "Commit created on ${TARGET_BRANCH}."
printf 'Review revert instructions in %s\n' "${REVERT_DOC}"
