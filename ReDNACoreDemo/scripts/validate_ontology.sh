#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Validating DNA Registry & Cross-Link Network..."

# 1. JSON Schema validation
echo "  Step 1: Schema validation..."
python3 -m jsonschema \
  -i ReDNACoreDemo/core/ontology/dna_registry.json \
  ReDNACoreDemo/schemas/dna_registry.schema.json

# 2. Linter rules
echo "  Step 2: Linter rules..."
python3 ReDNACoreDemo/core/ontology/linter.py \
  --registry ReDNACoreDemo/core/ontology/dna_registry.json \
  --report ReDNACoreDemo/core/ontology/reports/LINT_V2.txt

# 3. Generate stats
echo "  Step 3: Generate stats..."
python3 ReDNACoreDemo/core/ontology/tools/report_stats.py > \
  ReDNACoreDemo/core/ontology/reports/STATS_V2.json

# 4. Validate cross-links
echo "  Step 4: Cross-link validation..."
./ReDNACoreDemo/scripts/validate_cross_links.sh > /dev/null 2>&1

# 5. Network analysis
echo "  Step 5: Network analysis..."
python3 ReDNACoreDemo/scripts/analyze_network.py > /dev/null 2>&1

echo "✅ Ontology & cross-link validation complete"
