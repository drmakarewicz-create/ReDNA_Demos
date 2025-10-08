#!/bin/bash
# Validate all coach manifests for schema compliance
# Usage: ./scripts/validate_coach_manifests.sh

set -e

echo "🔍 Coach Manifest Validation"
echo "=============================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COACHES_DIR="$PROJECT_ROOT/ReDNACoreDemo/coaches"

EXIT_CODE=0
TOTAL_MANIFESTS=0
VALID_MANIFESTS=0
INVALID_MANIFESTS=0

# Find all coach_ui_manifest.yaml files
for manifest_path in "$COACHES_DIR"/*/coach_ui_manifest.yaml; do
    if [ -f "$manifest_path" ]; then
        TOTAL_MANIFESTS=$((TOTAL_MANIFESTS + 1))
        coach_dir=$(basename "$(dirname "$manifest_path")")

        echo "Validating: $coach_dir"

        # Required fields check
        has_schema_version=$(grep -c "^schema_version:" "$manifest_path" || true)
        has_coach_id=$(grep -c "^coach_id:" "$manifest_path" || true)
        has_widgets=$(grep -c "^widgets:" "$manifest_path" || true)

        errors=""

        if [ "$has_schema_version" -eq 0 ]; then
            errors="${errors}\n  ❌ Missing: schema_version"
        fi

        if [ "$has_coach_id" -eq 0 ]; then
            errors="${errors}\n  ❌ Missing: coach_id"
        fi

        if [ "$has_widgets" -eq 0 ]; then
            errors="${errors}\n  ❌ Missing: widgets array"
        fi

        # Check YAML syntax
        if ! python3 -c "import yaml; yaml.safe_load(open('$manifest_path'))" 2>/dev/null; then
            errors="${errors}\n  ❌ Invalid YAML syntax"
        fi

        # Widget validation
        widget_count=$(grep -c "^  - id:" "$manifest_path" || true)
        if [ "$widget_count" -eq 0 ]; then
            errors="${errors}\n  ❌ No widgets defined"
        fi

        # Zone validation (if layout_mode is zones)
        layout_mode=$(grep "^layout_mode:" "$manifest_path" | awk '{print $2}' || echo "")
        if [ "$layout_mode" = "zones" ]; then
            # Check that widgets have zone field
            widgets_with_zone=$(grep -c "^    zone:" "$manifest_path" || true)
            if [ "$widgets_with_zone" -eq 0 ]; then
                errors="${errors}\n  ⚠️  layout_mode=zones but no widgets have zone field"
            fi
        fi

        if [ -z "$errors" ]; then
            echo "  ✅ Valid ($widget_count widgets)"
            VALID_MANIFESTS=$((VALID_MANIFESTS + 1))
        else
            echo -e "$errors"
            echo ""
            INVALID_MANIFESTS=$((INVALID_MANIFESTS + 1))
            EXIT_CODE=1
        fi
    fi
done

echo ""
echo "=============================="
echo "Summary:"
echo "  Total:   $TOTAL_MANIFESTS"
echo "  Valid:   $VALID_MANIFESTS"
echo "  Invalid: $INVALID_MANIFESTS"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All manifests are valid!"
else
    echo "❌ Some manifests have errors"
fi

exit $EXIT_CODE
