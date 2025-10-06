#!/bin/bash
################################################################################
# ReDNA Quick Backup to iCloud Drive (Code & Config Only)
#
# This script creates a lightweight backup containing only:
# - Source code (.py, .js, .ts, .tsx, .json, .yaml, .yml, .md, .sh)
# - Configuration files
# - Documentation
# - Small data files (< 1MB)
#
# Excludes:
# - node_modules, .venv, __pycache__
# - Large binary files, images, models
# - Snapshots and full backups
#
# Usage:
#   ./quick_backup_to_icloud.sh
################################################################################

# Configuration
PROJECT_DIR="/Users/davidmakarewicz/Documents/ReDNA_Demos"
ICLOUD_BACKUP_DIR="/Users/davidmakarewicz/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups"
BACKUP_NAME="ReDNA_QuickBackup_$(date +%Y%m%d_%H%M%S).zip"
KEEP_LAST_N=10  # Keep last 10 quick backups

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  ReDNA Quick Backup (Code & Config Only)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Create backup directory if needed
mkdir -p "$ICLOUD_BACKUP_DIR"

echo "📦 Creating lightweight backup (code + config only)..."
echo ""

cd "$PROJECT_DIR" || exit 1

BACKUP_PATH="$ICLOUD_BACKUP_DIR/$BACKUP_NAME"

# Create backup including only essential files
echo "🔄 Archiving essential files..."
zip -r -q "$BACKUP_PATH" \
    "." \
    -i "*.py" "*.js" "*.ts" "*.tsx" "*.json" "*.yaml" "*.yml" "*.md" "*.sh" "*.txt" \
    -i "*.html" "*.css" "*.env.example" "*.toml" "*.ini" "*.conf" "*.cfg" \
    -x "*/node_modules/*" \
    -x "*/.venv/*" \
    -x "*/venv/*" \
    -x "*/__pycache__/*" \
    -x "*/.next/*" \
    -x "*/dist/*" \
    -x "*/build/*" \
    -x "*/snapshots/full_backup_*/*" \
    -x "*/snapshots/*_broken_*/*" \
    -x "*/.git/*" \
    -x "*/web/public/portraits/*" \
    -x "*.pyc" \
    -x ".DS_Store"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -sh "$BACKUP_PATH" 2>/dev/null | awk '{print $1}')
    echo -e "${GREEN}✓ Quick backup created successfully!${NC}"
    echo "   File: $BACKUP_NAME"
    echo "   Size: $BACKUP_SIZE"
    echo ""
else
    echo -e "${YELLOW}⚠ Backup completed with warnings${NC}"
    echo ""
fi

# Clean up old quick backups
echo "🗑️  Cleaning up old quick backups (keeping last $KEEP_LAST_N)..."
cd "$ICLOUD_BACKUP_DIR" || exit 1

BACKUP_COUNT=$(ls -1 ReDNA_QuickBackup_*.zip 2>/dev/null | wc -l | tr -d ' ')

if [ "$BACKUP_COUNT" -gt "$KEEP_LAST_N" ]; then
    BACKUPS_TO_DELETE=$((BACKUP_COUNT - KEEP_LAST_N))
    ls -t ReDNA_QuickBackup_*.zip | tail -n "$BACKUPS_TO_DELETE" | xargs rm -f
    echo -e "${GREEN}✓ Removed $BACKUPS_TO_DELETE old backup(s)${NC}"
else
    echo "   No cleanup needed ($BACKUP_COUNT backups)"
fi

echo ""
echo "📋 Recent quick backups:"
ls -lth "$ICLOUD_BACKUP_DIR"/ReDNA_QuickBackup_*.zip 2>/dev/null | head -5 | awk '{print "   " $9 " (" $5 ")"}'

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Quick Backup Complete! ✓${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "💡 What was backed up:"
echo "   ✓ All source code (.py, .js, .ts, etc.)"
echo "   ✓ Configuration files (.json, .yaml, .env.example)"
echo "   ✓ Documentation (.md files)"
echo "   ✓ Scripts (.sh files)"
echo ""
echo "   ✗ node_modules (excluded - can reinstall)"
echo "   ✗ .venv (excluded - can recreate)"
echo "   ✗ Large data files and snapshots"
echo ""
