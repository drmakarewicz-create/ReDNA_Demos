#!/bin/bash
#
# Setup automated backups via cron
# Run this script to install the cron jobs for automated backups
#

set -e

# Get the absolute path to the ReDNA_Demos directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔧 Setting up automated backups for ReDNA_Demos"
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if scripts exist
if [ ! -f "$SCRIPT_DIR/create_backup.sh" ]; then
  echo "❌ Error: create_backup.sh not found"
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/retention_cleanup.sh" ]; then
  echo "❌ Error: retention_cleanup.sh not found"
  exit 1
fi

# Make scripts executable
chmod +x "$SCRIPT_DIR/create_backup.sh"
chmod +x "$SCRIPT_DIR/retention_cleanup.sh"

echo "✅ Backup scripts are executable"
echo ""

# Create temporary cron file
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l > "$TEMP_CRON" 2>/dev/null || true

# Check if backups are already scheduled
if grep -q "create_backup.sh" "$TEMP_CRON" 2>/dev/null; then
  echo "⚠️  Backup cron jobs already exist. Showing current configuration:"
  echo ""
  grep "create_backup.sh\|retention_cleanup.sh" "$TEMP_CRON"
  echo ""
  read -p "Do you want to replace them? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled. No changes made."
    rm "$TEMP_CRON"
    exit 0
  fi

  # Remove old backup cron jobs
  grep -v "create_backup.sh\|retention_cleanup.sh" "$TEMP_CRON" > "$TEMP_CRON.new"
  mv "$TEMP_CRON.new" "$TEMP_CRON"
fi

echo "📅 Adding cron jobs..."
echo ""

# Add new cron jobs
cat >> "$TEMP_CRON" << EOF

# ReDNA_Demos Automated Backups
# Generated: $(date)

# Daily backup at 9:00 AM
0 9 * * * $SCRIPT_DIR/create_backup.sh >> $PROJECT_DIR/backups/backup.log 2>&1

# Weekly cleanup on Sundays at 10:00 AM (with --apply flag)
0 10 * * 0 $SCRIPT_DIR/retention_cleanup.sh --apply >> $PROJECT_DIR/backups/cleanup.log 2>&1
EOF

# Install new crontab
crontab "$TEMP_CRON"

# Cleanup
rm "$TEMP_CRON"

echo "✅ Cron jobs installed successfully!"
echo ""
echo "📋 Current cron configuration:"
echo ""
crontab -l | grep -A 2 "ReDNA_Demos Automated Backups" || true
echo ""
echo "📊 Schedule:"
echo "  • Daily backup: 9:00 AM"
echo "  • Weekly cleanup: Sundays at 10:00 AM"
echo ""
echo "📁 Logs will be written to:"
echo "  • Backups: $PROJECT_DIR/backups/backup.log"
echo "  • Cleanup: $PROJECT_DIR/backups/cleanup.log"
echo ""
echo "🧪 Test the setup:"
echo "  bash $SCRIPT_DIR/create_backup.sh"
echo "  bash $SCRIPT_DIR/retention_cleanup.sh"
echo ""
echo "🗑️  To remove cron jobs, run:"
echo "  crontab -e"
echo "  (then delete the ReDNA_Demos backup lines)"
echo ""
echo "✨ Done!"
