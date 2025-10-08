#!/bin/bash
# Validate cross-link network for ReDNA ontology
# Checks: schema, paths, duplicates, confidence ranges

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REGISTRY_PATH="$PROJECT_ROOT/core/ontology/dna_registry.json"
CROSS_LINKS_PATH="$PROJECT_ROOT/core/ontology/cross_links.yaml"
REPORT_PATH="$PROJECT_ROOT/core/ontology/reports/CROSS_LINK_VALIDATION.txt"

echo "🔗 Validating Cross-Link Network..."

# Step 1: Check files exist
if [ ! -f "$REGISTRY_PATH" ]; then
    echo "❌ Registry not found: $REGISTRY_PATH"
    exit 1
fi

if [ ! -f "$CROSS_LINKS_PATH" ]; then
    echo "❌ Cross-links not found: $CROSS_LINKS_PATH"
    exit 1
fi

# Step 2: Run Python validation
python3 <<EOF
import json
import yaml
import sys
from pathlib import Path

# Load files
with open('$REGISTRY_PATH') as f:
    registry = json.load(f)

with open('$CROSS_LINKS_PATH') as f:
    cross_links = yaml.safe_load(f)

# Build path index
paths = set(c['path'] for c in registry['containers'])

# Validation
errors = []
warnings = []
stats = {
    'total_edges': len(cross_links.get('edges', [])),
    'edge_types': {},
    'confidence_range': [1.0, 0.0],
    'missing_paths': [],
    'duplicate_edges': [],
    'invalid_confidence': [],
}

# Track seen edges for duplicate detection
seen_edges = set()

for i, edge in enumerate(cross_links.get('edges', [])):
    # Check required fields
    required = ['from', 'to', 'type', 'evidence', 'confidence']
    for field in required:
        if field not in edge:
            errors.append(f"Edge {i}: Missing required field '{field}'")

    # Check paths exist
    from_path = edge.get('from', '')
    to_path = edge.get('to', '')

    if from_path not in paths:
        errors.append(f"Edge {i}: 'from' path not found: {from_path}")
        stats['missing_paths'].append(from_path)

    if to_path not in paths:
        errors.append(f"Edge {i}: 'to' path not found: {to_path}")
        stats['missing_paths'].append(to_path)

    # Check for duplicates
    edge_key = (from_path, to_path)
    if edge_key in seen_edges:
        errors.append(f"Edge {i}: Duplicate edge {from_path} → {to_path}")
        stats['duplicate_edges'].append(edge_key)
    seen_edges.add(edge_key)

    # Check edge type
    edge_type = edge.get('type', '')
    valid_types = ['correlates_with', 'derived_from', 'influences', 'contradicts']
    if edge_type not in valid_types:
        warnings.append(f"Edge {i}: Unknown edge type '{edge_type}'")

    stats['edge_types'][edge_type] = stats['edge_types'].get(edge_type, 0) + 1

    # Check confidence
    confidence = edge.get('confidence', 0)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append(f"Edge {i}: Invalid confidence value: {confidence}")
        stats['invalid_confidence'].append((from_path, to_path, confidence))
    else:
        stats['confidence_range'][0] = min(stats['confidence_range'][0], confidence)
        stats['confidence_range'][1] = max(stats['confidence_range'][1], confidence)

    # Check evidence
    evidence = edge.get('evidence', '')
    if not evidence or len(evidence) < 10:
        warnings.append(f"Edge {i}: Evidence too short or missing")

# Generate report
report_lines = [
    "Cross-Link Network Validation Report",
    "=" * 60,
    "",
    f"Registry: {Path('$REGISTRY_PATH').name}",
    f"Cross-links: {Path('$CROSS_LINKS_PATH').name}",
    f"Total edges: {stats['total_edges']}",
    "",
]

if errors:
    report_lines.append(f"ERRORS ({len(errors)}):")
    for error in errors[:20]:  # Limit to first 20
        report_lines.append(f"  ❌ {error}")
    if len(errors) > 20:
        report_lines.append(f"  ... and {len(errors) - 20} more errors")
    report_lines.append("")

if warnings:
    report_lines.append(f"WARNINGS ({len(warnings)}):")
    for warning in warnings[:20]:
        report_lines.append(f"  ⚠️  {warning}")
    if len(warnings) > 20:
        report_lines.append(f"  ... and {len(warnings) - 20} more warnings")
    report_lines.append("")

report_lines.extend([
    "STATISTICS:",
    f"  Edge types:",
])

for edge_type, count in sorted(stats['edge_types'].items()):
    pct = count / stats['total_edges'] * 100 if stats['total_edges'] > 0 else 0
    report_lines.append(f"    {edge_type}: {count} ({pct:.1f}%)")

if stats['total_edges'] > 0:
    report_lines.extend([
        f"  Confidence range: {stats['confidence_range'][0]:.2f} - {stats['confidence_range'][1]:.2f}",
        f"  Average confidence: {sum(e.get('confidence', 0) for e in cross_links['edges']) / stats['total_edges']:.2f}",
    ])

report_lines.append("")

if errors:
    report_lines.append("Validation exit code: 1 (FAILED)")
    exit_code = 1
else:
    report_lines.append("✅ Validation passed (0 errors)")
    exit_code = 0

# Write report
Path('$REPORT_PATH').parent.mkdir(parents=True, exist_ok=True)
Path('$REPORT_PATH').write_text('\n'.join(report_lines))

# Print summary
print('\n'.join(report_lines))

sys.exit(exit_code)
EOF

VALIDATION_EXIT=$?

if [ $VALIDATION_EXIT -eq 0 ]; then
    echo ""
    echo "✅ Cross-link validation complete"
    echo "   Report: $REPORT_PATH"
    exit 0
else
    echo ""
    echo "❌ Cross-link validation failed"
    echo "   Report: $REPORT_PATH"
    exit 1
fi
