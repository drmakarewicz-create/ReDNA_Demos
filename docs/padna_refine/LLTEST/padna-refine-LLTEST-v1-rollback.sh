#!/usr/bin/env bash
# Rollback script for padna-refine-LLTEST-v1
# Timestamp: 2025-10-03T20:30:00Z
# Reverts all changes made during this refinement batch

set -euo pipefail

REPO_ROOT="$HOME/Documents/ReDNA_Demos"
cd "$REPO_ROOT"

echo "=== Rolling back padna-refine-LLTEST-v1 ==="

# 1. Remove traits registry patch
echo "Removing traits_registry.patch.yaml..."
if [ -f "ReDNACoreDemo/data/config/traits_registry.patch.yaml" ]; then
  rm "ReDNACoreDemo/data/config/traits_registry.patch.yaml"
  echo "  ✓ Removed traits_registry.patch.yaml"
else
  echo "  ⚠ traits_registry.patch.yaml not found (already removed?)"
fi

# 2. Revert trait-to-prompt.ts changes
echo "Reverting trait-to-prompt.ts..."
git checkout HEAD -- web/src/server/trait-to-prompt.ts 2>/dev/null && \
  echo "  ✓ Reverted trait-to-prompt.ts" || \
  echo "  ⚠ Could not revert trait-to-prompt.ts (not in git or already reverted)"

# 3. Remove refinement artifacts
echo "Removing refinement artifacts..."
if [ -d "docs/padna_refine/LLTEST" ]; then
  rm -f "docs/padna_refine/LLTEST/padna-refine-LLTEST-v1-delta.json"
  rm -f "docs/padna_refine/LLTEST/padna-refine-LLTEST-v1-observations.json"
  rm -f "docs/padna_refine/LLTEST/padna-refine-LLTEST-v1-rollback.sh"
  rm -f "docs/padna_refine/LLTEST/progress.json"
  echo "  ✓ Removed refinement artifacts"
else
  echo "  ⚠ Refinement directory not found"
fi

# 4. Revert automation logs (if committed with this batch)
echo "Reverting automation logs..."
git checkout HEAD -- docs/automation_log/changes.jsonl 2>/dev/null && \
  echo "  ✓ Reverted changes.jsonl" || \
  echo "  ⚠ Could not revert changes.jsonl (manual check recommended)"

git checkout HEAD -- docs/automation_log/latest.md 2>/dev/null && \
  echo "  ✓ Reverted latest.md" || \
  echo "  ⚠ Could not revert latest.md (manual check recommended)"

# 5. Remove any merged registry changes (if patch was applied)
echo ""
echo "=== Manual Steps Required ==="
echo "If traits_registry.patch.yaml was already merged into traits_registry.yaml:"
echo "  1. Manually remove the 'padna-refine-LLTEST-v1' section from traits_registry.yaml"
echo "  2. Or revert entire file: git checkout HEAD -- ReDNACoreDemo/data/config/traits_registry.yaml"
echo ""
echo "If LLTEST resolved.json was updated with new containers:"
echo "  1. Re-run import with original LLTEST-clean.json to restore previous state"
echo "  2. Or restore from backup: cp data/users/LLTEST/resolved.json.backup data/users/LLTEST/resolved.json"
echo ""

echo "=== Rollback Complete ==="
echo "Batch padna-refine-LLTEST-v1 artifacts removed."
echo "Check manual steps above if deeper rollback needed."
