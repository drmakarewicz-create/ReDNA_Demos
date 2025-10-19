#!/bin/bash

# Coach Configuration Verification Script
# Checks that backend coaches match frontend configuration

set -e

echo "========================================="
echo "  Coach Configuration Verification"
echo "========================================="
echo ""

# Check if Core API is running
if ! curl -s http://127.0.0.1:8015/health > /dev/null 2>&1; then
  echo "❌ ERROR: Core API is not running on port 8015"
  echo "   Start it first, then run this script again."
  exit 1
fi

echo "✅ Core API is running"
echo ""

# Get backend coaches
echo "=== BACKEND COACHES (from /ui/coach-catalog) ==="
BACKEND_COACHES=$(curl -s http://127.0.0.1:8015/ui/coach-catalog 2>/dev/null | \
  python3 -c "import sys, json; data=json.load(sys.stdin); print('\\n'.join(sorted([c['id'] for c in data['coaches']])))" 2>/dev/null)

if [ -z "$BACKEND_COACHES" ]; then
  echo "❌ ERROR: Failed to fetch coaches from backend"
  exit 1
fi

echo "$BACKEND_COACHES"
BACKEND_COUNT=$(echo "$BACKEND_COACHES" | wc -l | tr -d ' ')
echo ""
echo "Total: $BACKEND_COUNT coaches"
echo ""

# Get frontend CANONICAL_ORDER
echo "=== FRONTEND CANONICAL_ORDER (from api.ts) ==="
CANONICAL_ORDER=$(grep -A 20 "const CANONICAL_ORDER" web/src/lib/api.ts | \
  grep "'" | \
  sed "s/.*'\\([^']*\\)'.*/\\1/" | \
  sort)

echo "$CANONICAL_ORDER"
CANONICAL_COUNT=$(echo "$CANONICAL_ORDER" | wc -l | tr -d ' ')
echo ""
echo "Total: $CANONICAL_COUNT coaches"
echo ""

# Get normalizePersonaKey return type
echo "=== normalizePersonaKey RETURN TYPE (from page-client.tsx) ==="
NORMALIZE_TYPES=$(grep "function normalizePersonaKey" web/src/app/page-client.tsx | \
  sed "s/.*): //;s/ {.*//" | \
  tr '|' '\n' | \
  sed "s/[' ]//g" | \
  grep -v '^$' | \
  sort)

echo "$NORMALIZE_TYPES"
NORMALIZE_COUNT=$(echo "$NORMALIZE_TYPES" | wc -l | tr -d ' ')
echo ""
echo "Total: $NORMALIZE_COUNT types"
echo ""

# Compare counts
echo "========================================="
echo "  VERIFICATION RESULTS"
echo "========================================="
echo ""

if [ "$BACKEND_COUNT" -eq "$CANONICAL_COUNT" ] && [ "$CANONICAL_COUNT" -eq "$NORMALIZE_COUNT" ]; then
  echo "✅ COUNTS MATCH: All three layers have $BACKEND_COUNT coaches"
else
  echo "❌ COUNT MISMATCH:"
  echo "   Backend:          $BACKEND_COUNT coaches"
  echo "   CANONICAL_ORDER:  $CANONICAL_COUNT coaches"
  echo "   normalizePersonaKey: $NORMALIZE_COUNT types"
  echo ""
  echo "⚠️  This will cause coach switching failures!"
fi

echo ""
echo "========================================="
echo "  DETAILED COMPARISON"
echo "========================================="
echo ""

# Note about normalization
echo "📝 NOTE: Backend uses '_' (e.g., photo_coach, padna_coach)"
echo "         Frontend normalizes to short form (photo, padna)"
echo "         This is expected and correct."
echo ""

# Show which coaches are in backend but missing from frontend
echo "🔍 Checking for missing coaches..."
echo ""

MISSING_FROM_CANONICAL=()
MISSING_FROM_NORMALIZE=()

while IFS= read -r coach; do
  # Normalize backend coach ID for comparison (photo_coach -> photo, padna_coach -> padna)
  normalized_coach="$coach"
  if [ "$coach" = "photo_coach" ]; then
    normalized_coach="photo"
  elif [ "$coach" = "padna_coach" ]; then
    normalized_coach="padna"
  fi

  if ! echo "$CANONICAL_ORDER" | grep -q "^${normalized_coach}$"; then
    MISSING_FROM_CANONICAL+=("$coach (should be $normalized_coach)")
  fi

  if ! echo "$NORMALIZE_TYPES" | grep -q "^${normalized_coach}$"; then
    MISSING_FROM_NORMALIZE+=("$coach (should be $normalized_coach)")
  fi
done <<< "$BACKEND_COACHES"

if [ ${#MISSING_FROM_CANONICAL[@]} -gt 0 ]; then
  echo "❌ MISSING FROM CANONICAL_ORDER:"
  for coach in "${MISSING_FROM_CANONICAL[@]}"; do
    echo "   - $coach"
  done
  echo ""
  echo "   Fix: Add to web/src/lib/api.ts CANONICAL_ORDER"
  echo ""
else
  echo "✅ All backend coaches present in CANONICAL_ORDER"
  echo ""
fi

if [ ${#MISSING_FROM_NORMALIZE[@]} -gt 0 ]; then
  echo "❌ MISSING FROM normalizePersonaKey RETURN TYPE:"
  for coach in "${MISSING_FROM_NORMALIZE[@]}"; do
    echo "   - $coach"
  done
  echo ""
  echo "   Fix: Add to web/src/app/page-client.tsx normalizePersonaKey() return type"
  echo ""
else
  echo "✅ All backend coaches present in normalizePersonaKey return type"
  echo ""
fi

# Final summary
echo "========================================="
echo "  SUMMARY"
echo "========================================="
echo ""

if [ ${#MISSING_FROM_CANONICAL[@]} -eq 0 ] && [ ${#MISSING_FROM_NORMALIZE[@]} -eq 0 ]; then
  echo "✅ ALL CHECKS PASSED"
  echo ""
  echo "Coach switching should work correctly."
  echo "If coaches still don't switch, check COACH_SWITCHING_CHECKLIST.md"
  echo "for the remaining 5 layers."
  exit 0
else
  echo "❌ CONFIGURATION ERRORS DETECTED"
  echo ""
  echo "Coach switching WILL NOT WORK until these are fixed."
  echo ""
  echo "📖 See: web/COACH_SWITCHING_CHECKLIST.md for complete fix instructions"
  exit 1
fi
