# ReDNA Backup Retention Policy

**Status**: Active
**Last Updated**: 2025-10-11
**Owner**: DevOps / Autonomous Systems

---

## Overview

ReDNA implements **automated backup retention** with configurable policies for both local and iCloud storage. The system uses a **dry-run by default** approach to ensure safety, requiring explicit confirmation before deleting any files.

### Key Principles

1. **Safety First**: Dry-run mode by default, never deletes without `--apply`
2. **Always Keep Newest**: The most recent backup is never deleted, regardless of age
3. **24-Hour Protection**: Won't delete backups < 24h old unless `--force` is used
4. **Configurable Retention**: Different policies for local vs. iCloud storage
5. **Transparent Reporting**: Shows exactly what would/will be deleted

---

## Retention Policies

### Default Retention Periods

| Location | Retention Period | Rationale |
|----------|-----------------|-----------|
| **Local** | 30 days | Fast local access for recent restores |
| **iCloud** | 60 days | Longer cloud retention for disaster recovery |

### What Gets Deleted

Files matching these criteria are candidates for deletion:

- ✅ Filename pattern: `redna_backup_*.tar.gz`
- ✅ Older than retention period (30/60 days)
- ✅ NOT the newest file in the directory
- ✅ Older than 24 hours (unless `--force`)

### What's NEVER Deleted

- ❌ The newest backup file (by modification time)
- ❌ Files newer than 24 hours (unless `--force`)
- ❌ Files that don't match the backup pattern
- ❌ Anything in dry-run mode (default)

---

## Usage

### Script Location

```bash
scripts/backups/retention_cleanup.sh
```

### Modes of Operation

#### 1. Dry-Run Mode (Default)

Shows what would be deleted without actually deleting anything:

```bash
bash scripts/backups/retention_cleanup.sh
```

**Example Output:**

```console
🗑️  ReDNA Backup Retention & Cleanup
====================================

Mode: DRY-RUN (no files will be deleted)

Configuration:
  Local retention:  30 days
  iCloud retention: 60 days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Local Backups
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊 Summary:
     Total backups: 5 (size: 4.2M)
     Newest backup: 0d ago
     Oldest backup: 45d ago
     Keep: 4 backups
     Would delete: 1 backups (size: 850K)

  📋 Candidates for deletion:
     - redna_backup_2025-08-27_10-15-30.tar.gz (45d old, 850K)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
iCloud Backups
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📊 Summary:
     Total backups: 3 (size: 2.5M)
     Newest backup: 0d ago
     Oldest backup: 70d ago
     Keep: 2 backups
     Would delete: 1 backups (size: 800K)

  📋 Candidates for deletion:
     - redna_backup_2025-08-02_09-20-15.tar.gz (70d old, 800K)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Final Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: DRY-RUN
  No files were deleted
  Run with --apply to actually delete files

Status: ✅ SUCCESS

Exit code: 0
```

#### 2. Apply Mode

Actually deletes old backups:

```bash
bash scripts/backups/retention_cleanup.sh --apply
```

**Example Output:**

```console
🗑️  ReDNA Backup Retention & Cleanup
====================================

Mode: APPLY (files will be deleted)

Configuration:
  Local retention:  30 days
  iCloud retention: 60 days

[... scan output ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deleting Files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ Deleted: redna_backup_2025-08-27_10-15-30.tar.gz
  ✅ Deleted: redna_backup_2025-08-02_09-20-15.tar.gz

  Summary: 2 deleted, 0 failed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Final Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Mode: APPLY
  Files have been deleted

Status: ✅ SUCCESS

Exit code: 0
```

#### 3. Force Mode

Allows deletion of files < 24h old (still keeps newest):

```bash
bash scripts/backups/retention_cleanup.sh --apply --force
```

⚠️ **Use with caution**: This bypasses the 24-hour safety check.

---

## Configuration

### Environment Variables

Customize retention policies using environment variables:

```bash
# Local backup directory
export REDNA_BACKUP_LOCAL_DIR="$HOME/Documents/ReDNA_Demos/backups"

# iCloud backup directory
export REDNA_BACKUP_ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups"

# Retention periods (in days)
export REDNA_BACKUP_LOCAL_DAYS=30
export REDNA_BACKUP_ICLOUD_DAYS=60

# Run with custom settings
bash scripts/backups/retention_cleanup.sh
```

### Example: Custom Retention

Keep local backups for 14 days, iCloud for 90 days:

```bash
REDNA_BACKUP_LOCAL_DAYS=14 REDNA_BACKUP_ICLOUD_DAYS=90 \
  bash scripts/backups/retention_cleanup.sh --apply
```

---

## Integration with Daily Health Check

The retention cleanup script is automatically run in **dry-run mode** by the daily health check:

```bash
bash scripts/autonomous/daily_health_check.sh
```

This provides a daily report showing:

- Total backup counts (local & iCloud)
- Age of newest and oldest backups
- How many backups would be deleted
- Total size of deletable backups

**Example Health Report Section:**

```markdown
## 9. Backup Retention Summary

  **Local Backups** (`~/Documents/ReDNA_Demos/backups`):
  - Total: 5 backups
  - Newest: 0d ago | Oldest: 45d ago
  - Keep: 4 | Would delete: 1 (size: 850K)

  **iCloud Backups** (`~/Library/Mobile Documents/.../ReDNA_Backups`):
  - Total: 3 backups
  - Newest: 0d ago | Oldest: 70d ago
  - Keep: 2 | Would delete: 1 (size: 800K)

  **Retention Policy**:
  - Local: Keep 30 days
  - iCloud: Keep 60 days
  - Always keeps newest backup regardless of age

  ✅ Retention status: OK

  **Next Action**: Run `bash scripts/backups/retention_cleanup.sh --apply` to delete old backups
```

---

## Scheduling Automatic Cleanup

### Option 1: Manual Weekly Cleanup

Run retention cleanup manually once per week:

```bash
# Every Monday at 10 AM
bash scripts/backups/retention_cleanup.sh --apply
```

### Option 2: Automated via Cron

Schedule automatic cleanup via cron:

```bash
# Edit crontab
crontab -e

# Add weekly cleanup (Mondays at 3 AM)
0 3 * * 1 /Users/$(whoami)/Documents/ReDNA_Demos/scripts/backups/retention_cleanup.sh --apply >> /tmp/redna_retention.log 2>&1
```

### Option 3: Conditional Cleanup

Only run cleanup when backups exceed a certain count:

```bash
#!/usr/bin/env bash
# scripts/backups/conditional_cleanup.sh

BACKUP_COUNT=$(find ~/Documents/ReDNA_Demos/backups -name "redna_backup_*.tar.gz" | wc -l)

if [ "$BACKUP_COUNT" -gt 50 ]; then
    echo "Backup count ($BACKUP_COUNT) exceeds threshold, running cleanup..."
    bash scripts/backups/retention_cleanup.sh --apply
else
    echo "Backup count ($BACKUP_COUNT) within limits, skipping cleanup"
fi
```

---

## Exit Codes

The script uses standard exit codes for automation:

| Exit Code | Status | Meaning |
|-----------|--------|---------|
| `0` | ✅ Success | All operations completed successfully |
| `2` | ⚠️ Warning | Minor issues (e.g., directory not found) |
| `3` | ❌ Error | Critical failures (e.g., deletion failed) |

### Using Exit Codes in Scripts

```bash
#!/usr/bin/env bash

bash scripts/backups/retention_cleanup.sh --apply

case $? in
    0)
        echo "✅ Cleanup successful"
        ;;
    2)
        echo "⚠️  Cleanup completed with warnings"
        ;;
    3)
        echo "❌ Cleanup failed"
        exit 1
        ;;
esac
```

---

## Troubleshooting

### Issue: iCloud Directory Not Found

**Symptom:**
```
⚠️  Directory not found: ~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups
```

**Solutions:**

1. Check if iCloud Drive is enabled:
   ```bash
   ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/
   ```

2. Create the directory manually:
   ```bash
   mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups
   ```

3. Run initial backup to populate directory:
   ```bash
   bash scripts/backups/create_backup.sh
   ```

### Issue: Permission Denied

**Symptom:**
```
❌ Failed to delete: redna_backup_2025-08-01_10-15-30.tar.gz
```

**Solutions:**

1. Check file permissions:
   ```bash
   ls -la ~/Documents/ReDNA_Demos/backups/
   ```

2. Verify ownership:
   ```bash
   whoami
   ls -l ~/Documents/ReDNA_Demos/backups/*.tar.gz
   ```

3. Fix permissions if needed:
   ```bash
   chmod 644 ~/Documents/ReDNA_Demos/backups/*.tar.gz
   ```

### Issue: Spaces in Paths

**Symptom:**
Script fails with path errors when using custom directories with spaces.

**Solution:**

Always quote environment variables:

```bash
export REDNA_BACKUP_LOCAL_DIR="$HOME/My Custom Backup Path"
bash scripts/backups/retention_cleanup.sh
```

### Issue: Wrong Files Being Deleted

**Symptom:**
Script targets files that shouldn't be deleted.

**Verification:**

1. Run in dry-run mode first:
   ```bash
   bash scripts/backups/retention_cleanup.sh
   ```

2. Check the filename pattern in the script:
   ```bash
   grep "pattern=" scripts/backups/retention_cleanup.sh
   ```

3. Ensure only `redna_backup_*.tar.gz` files are targeted.

---

## Safety Features

### 1. Dry-Run Default

The script **never deletes** unless you explicitly use `--apply`:

```bash
# Safe - shows candidates only
bash scripts/backups/retention_cleanup.sh

# Dangerous - actually deletes
bash scripts/backups/retention_cleanup.sh --apply
```

### 2. Newest File Protection

The newest backup is **always kept**, even if older than retention period:

```bash
# Even if only one backup exists and it's 365 days old, it won't be deleted
bash scripts/backups/retention_cleanup.sh --apply
```

### 3. 24-Hour Safety Window

Backups newer than 24 hours are protected unless `--force`:

```bash
# Won't delete anything < 24h old
bash scripts/backups/retention_cleanup.sh --apply

# Will delete < 24h old (but still keeps newest)
bash scripts/backups/retention_cleanup.sh --apply --force
```

### 4. Pattern Matching

Only files matching `redna_backup_*.tar.gz` are considered:

```bash
# Safe - won't touch these:
# - ontology_v5_2025-10-11.tar.gz
# - manual_backup_2025-10-11.tar.gz
# - README.md
```

---

## Best Practices

### 1. Run Dry-Run First

Always preview deletions before applying:

```bash
# Step 1: Preview
bash scripts/backups/retention_cleanup.sh

# Step 2: Review output

# Step 3: Apply if satisfied
bash scripts/backups/retention_cleanup.sh --apply
```

### 2. Monitor Health Reports

Check daily health reports for retention summaries:

```bash
cat docs/ops/DAILY_HEALTH_REPORT.md | grep -A 20 "Retention Summary"
```

### 3. Adjust Policies Based on Usage

If you frequently restore old backups, increase retention:

```bash
# Keep local backups for 60 days instead of 30
export REDNA_BACKUP_LOCAL_DAYS=60
bash scripts/backups/retention_cleanup.sh --apply
```

### 4. Test with Fake Backups

Test retention logic with dummy files:

```bash
# Create test backups
touch ~/Documents/ReDNA_Demos/backups/redna_backup_2025-01-01_00-00-00.tar.gz

# Run dry-run to see if it would be deleted
bash scripts/backups/retention_cleanup.sh

# Delete test file
rm ~/Documents/ReDNA_Demos/backups/redna_backup_2025-01-01_00-00-00.tar.gz
```

### 5. Archive Important Backups

Before retention cleanup, manually archive important backups outside the retention directories:

```bash
# Archive a specific backup
mkdir -p ~/Documents/ReDNA_Archives
cp ~/Documents/ReDNA_Demos/backups/redna_backup_2025-09-15_12-00-00.tar.gz \
   ~/Documents/ReDNA_Archives/
```

---

## Related Documentation

- [iCloud Backup Setup Guide](./ICLOUD_BACKUP_SETUP.md)
- [Daily Health Check Guide](./DAILY_HEALTH_REPORT.md)
- [Backup Creation Script](../../scripts/backups/create_backup.sh)

---

## FAQ

**Q: What happens if I run `--apply` by mistake?**
A: As long as you didn't use `--force`, only backups older than the retention period (and > 24h) will be deleted. The newest backup is always kept.

**Q: Can I recover deleted backups?**
A: If you have Time Machine enabled, you can restore deleted backups. Otherwise, deleted backups are permanent. This is why dry-run is the default.

**Q: Why separate retention policies for local vs. iCloud?**
A: Local backups are fast to access but use local disk space. iCloud backups are slower to retrieve but provide cloud redundancy. The 30/60 day split balances speed vs. safety.

**Q: Does retention cleanup run automatically?**
A: No. The daily health check runs it in dry-run mode (reporting only). You must manually run `--apply` to delete files, or schedule it via cron.

**Q: What if I want to keep ALL backups forever?**
A: Set retention to a very high number:
```bash
export REDNA_BACKUP_LOCAL_DAYS=36500   # 100 years
export REDNA_BACKUP_ICLOUD_DAYS=36500
```

**Q: Can I use this script with other cloud providers (Dropbox, Google Drive)?**
A: Yes! Just set `REDNA_BACKUP_ICLOUD_DIR` to your cloud provider's sync folder:
```bash
export REDNA_BACKUP_ICLOUD_DIR="$HOME/Dropbox/ReDNA_Backups"
export REDNA_BACKUP_ICLOUD_DIR="$HOME/Google Drive/ReDNA_Backups"
```

---

**Document Version**: 1.0
**Implementation Date**: 2025-10-11
**Next Review**: 2025-11-11
