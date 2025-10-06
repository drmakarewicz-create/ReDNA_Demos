#!/bin/bash
################################################################################
# ReDNA Project Backup to iCloud Drive
#
# This script creates automated backups of the ReDNA project to iCloud Drive.
# It excludes large/regenerable files and keeps the last 7 backups.
#
# Usage:
#   ./backup_to_icloud.sh
#
# Schedule with cron (daily at 2 AM):
#   0 2 * * * /Users/davidmakarewicz/Documents/ReDNA_Demos/backup_to_icloud.sh
################################################################################

# Configuration
PROJECT_DIR="/Users/davidmakarewicz/Documents/ReDNA_Demos"
ICLOUD_BACKUP_DIR="/Users/davidmakarewicz/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups"
BACKUP_NAME="ReDNA_Backup_$(date +%Y%m%d_%H%M%S).zip"
KEEP_LAST_N=7  # Keep last 7 backups

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ReDNA Project Backup to iCloud Drive${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}✗ Project directory not found: $PROJECT_DIR${NC}"
    exit 1
fi

# Check if iCloud backup directory exists
if [ ! -d "$ICLOUD_BACKUP_DIR" ]; then
    echo -e "${YELLOW}⚠ iCloud backup directory not found. Creating it...${NC}"
    mkdir -p "$ICLOUD_BACKUP_DIR"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Created iCloud backup directory${NC}"
    else
        echo -e "${RED}✗ Failed to create iCloud backup directory${NC}"
        exit 1
    fi
fi

# Create temporary exclusion list
EXCLUDE_FILE=$(mktemp)
cat > "$EXCLUDE_FILE" << 'EOF'
node_modules/*
.venv/*
venv/*
__pycache__/*
*.pyc
.DS_Store
.git/*
*.log
.next/*
.turbo/*
dist/*
build/*
.cache/*
*.swp
*.swo
*~
.env.local
snapshots/full_backup_*/*
snapshots/*_broken_*/*
web/public/portraits/*
*.tmp
*.temp
EOF

echo "📦 Creating backup archive..."
echo "   Source: $PROJECT_DIR"
echo "   Destination: $ICLOUD_BACKUP_DIR"
echo ""

# Calculate size before backup (approximation)
echo "📊 Calculating project size (excluding ignored files)..."
TOTAL_SIZE=$(du -sh "$PROJECT_DIR" 2>/dev/null | awk '{print $1}')
echo "   Total project size: $TOTAL_SIZE"
echo ""

# Create backup with exclusions
cd "$PROJECT_DIR/.." || exit 1

BACKUP_PATH="$ICLOUD_BACKUP_DIR/$BACKUP_NAME"

# Use zip with exclusions
echo "🔄 Creating zip archive..."
zip -r -q "$BACKUP_PATH" "ReDNA_Demos" \
    -x@"$EXCLUDE_FILE" \
    -x "*/node_modules/*" \
    -x "*/.venv/*" \
    -x "*/__pycache__/*" \
    -x "*/.*" \
    -x "*/.next/*" \
    -x "*/snapshots/full_backup_*/*" \
    2>/dev/null

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -sh "$BACKUP_PATH" 2>/dev/null | awk '{print $1}')
    echo -e "${GREEN}✓ Backup created successfully!${NC}"
    echo "   File: $BACKUP_NAME"
    echo "   Size: $BACKUP_SIZE"
    echo ""
else
    echo -e "${RED}✗ Backup failed${NC}"
    rm -f "$EXCLUDE_FILE"
    exit 1
fi

# Clean up exclusion file
rm -f "$EXCLUDE_FILE"

# Remove old backups (keep last N)
echo "🗑️  Cleaning up old backups (keeping last $KEEP_LAST_N)..."
cd "$ICLOUD_BACKUP_DIR" || exit 1

# Count existing backups
BACKUP_COUNT=$(ls -1 ReDNA_Backup_*.zip 2>/dev/null | wc -l | tr -d ' ')
echo "   Found $BACKUP_COUNT total backup(s)"

if [ "$BACKUP_COUNT" -gt "$KEEP_LAST_N" ]; then
    # Delete oldest backups
    BACKUPS_TO_DELETE=$((BACKUP_COUNT - KEEP_LAST_N))
    echo "   Removing $BACKUPS_TO_DELETE old backup(s)..."

    ls -t ReDNA_Backup_*.zip | tail -n "$BACKUPS_TO_DELETE" | while read -r old_backup; do
        echo "   - Deleting: $old_backup"
        rm -f "$old_backup"
    done

    echo -e "${GREEN}✓ Cleanup complete${NC}"
else
    echo "   No cleanup needed"
fi

echo ""
echo "📋 Current backups in iCloud:"
ls -lth "$ICLOUD_BACKUP_DIR"/ReDNA_Backup_*.zip 2>/dev/null | head -n "$KEEP_LAST_N" | awk '{print "   " $9 " (" $5 ")"}'

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Backup Complete! ✓${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "💡 Tip: Schedule automatic backups with cron:"
echo "   crontab -e"
echo "   Add: 0 2 * * * $PROJECT_DIR/backup_to_icloud.sh"
echo ""
