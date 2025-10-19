#!/bin/bash
# Validate ChatDNA Gap Logging System
# Checks feature map, schema, log size, and proposals

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔍 Validating ChatDNA Gap Logging System"
echo "========================================="
echo ""

TOTAL=0
PASSED=0
FAILED=0

# Test 1: Validate feature map YAML
TOTAL=$((TOTAL + 1))
FEATURE_MAP="$PROJECT_ROOT/ReDNACoreDemo/core/feature_map/language_feature_map.yaml"
echo -n "Test 1: Feature map YAML structure ... "

if python3 -c "
import yaml
with open('$FEATURE_MAP') as f:
    data = yaml.safe_load(f)
    assert 'features' in data, 'Missing features key'
    assert 'unmapped_features' in data, 'Missing unmapped_features key'
    assert 'governance' in data, 'Missing governance key'
    assert 'schema_version' in data, 'Missing schema_version'
" 2>&1; then
    echo "✅ PASS"
    PASSED=$((PASSED + 1))
else
    echo "❌ FAIL"
    FAILED=$((FAILED + 1))
fi

# Test 2: Validate candidate container schema
TOTAL=$((TOTAL + 1))
SCHEMA_FILE="$PROJECT_ROOT/ReDNACoreDemo/schemas/candidate_container.schema.json"
echo -n "Test 2: Candidate container JSON schema ... "

if python3 -c "
import json
with open('$SCHEMA_FILE') as f:
    schema = json.load(f)
    assert schema.get('type') == 'object', 'Schema must be object type'
    assert 'properties' in schema, 'Missing properties'
    assert 'required' in schema, 'Missing required fields'
" 2>&1; then
    echo "✅ PASS"
    PASSED=$((PASSED + 1))
else
    echo "❌ FAIL"
    FAILED=$((FAILED + 1))
fi

# Test 3: Check gap log size (alert if > 50MB/day)
TOTAL=$((TOTAL + 1))
LOG_FILE="$PROJECT_ROOT/ReDNACoreDemo/core/gap_logs/chatdna_unmet_features.jsonl"
echo -n "Test 3: Gap log size check ... "

if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo "0")
    MAX_SIZE=$((50 * 1024 * 1024))  # 50MB

    if [ "$LOG_SIZE" -lt "$MAX_SIZE" ]; then
        echo "✅ PASS ($(($LOG_SIZE / 1024))KB)"
        PASSED=$((PASSED + 1))
    else
        echo "⚠️  WARNING ($(($LOG_SIZE / 1024 / 1024))MB > 50MB limit)"
        echo "   Consider running log rotation"
        PASSED=$((PASSED + 1))
    fi
else
    echo "✅ PASS (no log file yet)"
    PASSED=$((PASSED + 1))
fi

# Test 4: Validate proposer config YAML
TOTAL=$((TOTAL + 1))
PROPOSER_CONFIG="$PROJECT_ROOT/ReDNACoreDemo/core/proposer/proposer_config.yaml"
echo -n "Test 4: Proposer config YAML ... "

if python3 -c "
import yaml
with open('$PROPOSER_CONFIG') as f:
    data = yaml.safe_load(f)
    assert 'thresholds' in data, 'Missing thresholds'
    assert 'weights' in data, 'Missing weights'
    assert 'max_proposals_per_night' in data, 'Missing max_proposals_per_night'
" 2>&1; then
    echo "✅ PASS"
    PASSED=$((PASSED + 1))
else
    echo "❌ FAIL"
    FAILED=$((FAILED + 1))
fi

# Test 5: Validate latest proposals (if exist)
TOTAL=$((TOTAL + 1))
PROPOSALS_DIR="$PROJECT_ROOT/ReDNACoreDemo/core/proposer/proposals"
echo -n "Test 5: Latest proposals validation ... "

LATEST_PROPOSAL=$(ls -t "$PROPOSALS_DIR"/*.json 2>/dev/null | head -n 1)

if [ -n "$LATEST_PROPOSAL" ]; then
    if python3 -c "
import json
import jsonschema

with open('$SCHEMA_FILE') as f:
    schema = json.load(f)
with open('$LATEST_PROPOSAL') as f:
    data = json.load(f)

# Validate each proposal against schema
for proposal in data.get('proposals', []):
    jsonschema.validate(proposal, schema)
" 2>&1; then
        echo "✅ PASS"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAIL (invalid proposal structure)"
        FAILED=$((FAILED + 1))
    fi
else
    echo "⏭️  SKIP (no proposals yet)"
    PASSED=$((PASSED + 1))
fi

# Test 6: Check unknown features in feature map
TOTAL=$((TOTAL + 1))
echo -n "Test 6: Feature map unknown keys ... "

UNKNOWN_KEYS=$(python3 -c "
import yaml
with open('$FEATURE_MAP') as f:
    data = yaml.safe_load(f)

known_top_level = {'schema_version', 'version', 'last_updated', 'features', 'unmapped_features', 'governance'}
actual_keys = set(data.keys())
unknown = actual_keys - known_top_level

if unknown:
    print(','.join(unknown))
    exit(1)
" 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ PASS"
    PASSED=$((PASSED + 1))
else
    echo "⚠️  WARNING (unknown keys: $UNKNOWN_KEYS)"
    PASSED=$((PASSED + 1))
fi

# Summary
echo ""
echo "========================================="
echo "Summary:"
echo "  Total:  $TOTAL"
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo "❌ Validation failed"
    echo "========================================="
    exit 1
fi

echo ""
echo "✅ All validations passed!"
echo "========================================="
exit 0
