#!/bin/bash
# Validate all ChatDNA persona bundles against JSON schema
# Exit code 0 if all valid, 1 if any validation fails

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUNDLES_DIR="$PROJECT_ROOT/fixtures/chatdna/personas"
SCHEMA_PATH="$PROJECT_ROOT/fixtures/chatdna/schema/chatdna_style_bundle.schema.json"

echo "🔍 Validating ChatDNA Persona Bundles"
echo "   Schema: $SCHEMA_PATH"
echo "   Bundles: $BUNDLES_DIR"
echo ""

# Check if jsonschema is available
if ! python3 -c "import jsonschema" 2>/dev/null; then
    echo "⚠️  jsonschema not installed. Installing..."
    pip install jsonschema
fi

TOTAL=0
PASSED=0
FAILED=0

for bundle_path in "$BUNDLES_DIR"/*.bundle.json; do
    if [ ! -f "$bundle_path" ]; then
        continue
    fi

    TOTAL=$((TOTAL + 1))
    bundle_name=$(basename "$bundle_path")

    echo -n "   $bundle_name ... "

    # Validate using Python jsonschema
    if python3 -c "
import json, sys
from jsonschema import validate, ValidationError

with open('$SCHEMA_PATH') as f:
    schema = json.load(f)
with open('$bundle_path') as f:
    bundle = json.load(f)

try:
    validate(bundle, schema)
    sys.exit(0)
except ValidationError as e:
    print(f'Validation error: {e.message}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        echo "✅ PASS"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAIL"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "📊 Summary:"
echo "   Total:  $TOTAL"
echo "   Passed: $PASSED"
echo "   Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "❌ Validation failed for $FAILED bundle(s)"
    exit 1
fi

echo ""
echo "✅ All bundles valid!"
exit 0
