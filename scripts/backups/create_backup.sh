#!/usr/bin/env bash
set -euo pipefail

# ReDNA Backup Script with iCloud Mirroring
# Creates timestamped backups of critical system files
# Automatically mirrors to iCloud Drive for cloud redundancy

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Backup directories
BACKUP_DIR="$PROJECT_ROOT/backups"
ICLOUD_BACKUP_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups"

# Create timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_NAME="redna_backup_$TIMESTAMP"

echo "🗄️  ReDNA Backup System"
echo "======================="
echo ""
echo "Timestamp: $TIMESTAMP"
echo "Local backup: $BACKUP_DIR"
echo "iCloud mirror: $ICLOUD_BACKUP_DIR"
echo ""

# Ensure backup directories exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$ICLOUD_BACKUP_DIR"

echo "📦 Creating backup archive..."

# Create temporary directory for backup staging
TEMP_BACKUP_DIR="/tmp/$BACKUP_NAME"
mkdir -p "$TEMP_BACKUP_DIR"

# Copy critical files to staging area
echo "  → Copying core configuration..."
[ -f ".cp_state.json" ] && cp ".cp_state.json" "$TEMP_BACKUP_DIR/" || true
[ -f ".cpplusplus_env.json" ] && cp ".cpplusplus_env.json" "$TEMP_BACKUP_DIR/" || true

echo "  → Copying docs..."
[ -d "docs/ops" ] && cp -r "docs/ops" "$TEMP_BACKUP_DIR/" || true
[ -f "README.md" ] && cp "README.md" "$TEMP_BACKUP_DIR/" || true

echo "  → Copying coach configurations..."
[ -f "ReDNACoreDemo/core/coach_registry.yaml" ] && mkdir -p "$TEMP_BACKUP_DIR/core" && cp "ReDNACoreDemo/core/coach_registry.yaml" "$TEMP_BACKUP_DIR/core/" || true

echo "  → Copying prompts..."
[ -d "prompts" ] && cp -r "prompts" "$TEMP_BACKUP_DIR/" || true

echo "  → Copying scripts..."
[ -d "scripts/autonomous" ] && mkdir -p "$TEMP_BACKUP_DIR/scripts" && cp -r "scripts/autonomous" "$TEMP_BACKUP_DIR/scripts/" || true

echo "  → Copying data system state..."
[ -f "data/system/registry.json" ] && mkdir -p "$TEMP_BACKUP_DIR/data/system" && cp "data/system/registry.json" "$TEMP_BACKUP_DIR/data/system/" || true

# Create tarball
echo "  → Compressing archive..."
BACKUP_FILE="$BACKUP_NAME.tar.gz"
tar -czf "$BACKUP_DIR/$BACKUP_FILE" -C /tmp "$BACKUP_NAME"

# Clean up staging area
rm -rf "$TEMP_BACKUP_DIR"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
echo "✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"

# Mirror to iCloud
echo ""
echo "☁️  Mirroring to iCloud Drive..."

# Use rsync to copy only new backups
if command -v rsync > /dev/null 2>&1; then
    rsync -av --ignore-existing "$BACKUP_DIR/"*.tar.gz "$ICLOUD_BACKUP_DIR/" 2>/dev/null || {
        echo "⚠️  Warning: iCloud sync encountered issues (iCloud may not be ready)"
    }

    # Verify the backup exists in iCloud
    if [ -f "$ICLOUD_BACKUP_DIR/$BACKUP_FILE" ]; then
        ICLOUD_SIZE=$(du -h "$ICLOUD_BACKUP_DIR/$BACKUP_FILE" | cut -f1)
        echo "✅ iCloud mirror confirmed: $BACKUP_FILE ($ICLOUD_SIZE)"
    else
        echo "⚠️  Warning: iCloud mirror not yet visible (may be syncing in background)"
    fi
else
    echo "⚠️  Warning: rsync not available, falling back to cp"
    cp "$BACKUP_DIR/$BACKUP_FILE" "$ICLOUD_BACKUP_DIR/" 2>/dev/null || {
        echo "⚠️  Warning: iCloud copy failed (iCloud may not be ready)"
    }
fi

echo ""
echo "📊 Backup Summary"
echo "=================="
echo "Local backups:"
ls -lh "$BACKUP_DIR" | grep ".tar.gz" | tail -5 | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo "iCloud backups:"
ls -lh "$ICLOUD_BACKUP_DIR" 2>/dev/null | grep ".tar.gz" | tail -5 | awk '{print "  " $9 " (" $5 ")"}' || echo "  (iCloud not yet synced)"

echo ""
echo "✅ Backup complete!"
echo ""
echo "To restore from backup:"
echo "  tar -xzf $BACKUP_DIR/$BACKUP_FILE -C /tmp"
echo ""

exit 0
