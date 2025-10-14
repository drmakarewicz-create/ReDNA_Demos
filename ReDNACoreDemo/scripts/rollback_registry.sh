#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="ReDNACoreDemo/core/ontology"
REGISTRY="${BACKUP_DIR}/dna_registry.json"

# Find most recent backup
LATEST_BACKUP=$(ls -t ${BACKUP_DIR}/dna_registry.json.bak.* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup found"
    exit 1
fi

echo "🔄 Rolling back to: $LATEST_BACKUP"
cp "$LATEST_BACKUP" "$REGISTRY"
echo "✅ Rollback complete"
