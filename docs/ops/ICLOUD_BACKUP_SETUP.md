# iCloud Backup Setup for ReDNA

**Status**: Active
**Last Updated**: 2025-10-11
**Owner**: DevOps / Autonomous Systems

---

## Overview

ReDNA now supports **dual-location backups** with automatic mirroring to iCloud Drive. Every backup is stored both locally and in your iCloud account for redundancy and accessibility across devices.

### Why iCloud Mirroring?

- **Cloud Redundancy**: Protects against local disk failure
- **Cross-Device Access**: Access backups from any Mac synced to your iCloud account
- **Automatic Sync**: iCloud handles syncing automatically in the background
- **Space Efficient**: Uses `rsync --ignore-existing` to avoid duplicate uploads

---

## Backup Locations

### Local Backup Directory
```
~/Documents/ReDNA_Demos/backups/
```

- Primary backup location
- Fast local access
- Included in Time Machine backups (if enabled)
- Git-ignored to avoid polluting repository

### iCloud Backup Directory
```
~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups/
```

- Automatic cloud mirror
- Synced across all devices using the same iCloud account
- Created automatically on first backup
- Not tracked by Git (external to repository)

---

## How It Works

### 1. Creating Backups

Run the backup script manually:

```bash
bash scripts/backups/create_backup.sh
```

Or use the autonomous health check (includes verification):

```bash
bash scripts/autonomous/daily_health_check.sh
```

### 2. What Gets Backed Up

The backup includes:

- Core configuration files (`.cp_state.json`, `.cpplusplus_env.json`)
- Documentation (`docs/ops/`, `README.md`)
- Coach configurations (`ReDNACoreDemo/core/coach_registry.yaml`)
- Prompts directory
- Autonomous scripts
- System state data

### 3. Backup Workflow

```
┌─────────────────────────┐
│  Run create_backup.sh   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Create staging area    │
│  in /tmp/               │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Copy critical files    │
│  to staging             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Compress to .tar.gz    │
│  with timestamp         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Save to local backups/ │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Mirror to iCloud Drive │
│  using rsync            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Verify both locations  │
└─────────────────────────┘
```

### 4. Mirroring Strategy

The script uses `rsync -av --ignore-existing`:

- `--ignore-existing`: Only copy new backups (no duplicates)
- `-a`: Archive mode (preserves permissions, timestamps)
- `-v`: Verbose output for transparency

This means:
- ✅ New backups are copied to iCloud
- ✅ Existing backups are skipped (no re-upload)
- ✅ Bandwidth is conserved

---

## Monitoring & Verification

### Daily Health Check

The autonomous health check (`scripts/autonomous/daily_health_check.sh`) monitors:

1. **Directory Exists**: Verifies iCloud backup directory is present
2. **Backup Count**: Reports total number of backups
3. **Freshness Check**: Ensures latest backup is < 24 hours old
4. **Size Report**: Shows backup file sizes

### Health Report Output

Green status (up to date):
```
## 8. iCloud Backup Status

✅ iCloud backup directory exists
- Total backups: 5
✅ Latest backup is up to date (2h ago)
- Latest: `redna_backup_2025-10-11_15-30-45.tar.gz` (1.2M)
```

Warning status (outdated):
```
## 8. iCloud Backup Status

⚠️  iCloud backup directory not found
- Expected: `~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups`
- Run `bash scripts/backups/create_backup.sh` to create initial backup
```

### Self-Verification

The self-verification script (`scripts/autonomous/self_verify.sh`) includes backup checks:

```bash
bash scripts/autonomous/self_verify.sh
```

Output example:
```
9️⃣  Backup System
---
✅ Backup script present
✅ iCloud backups present (5 backups)
✅ Latest backup is fresh (2h ago)
```

---

## Example Console Output

### Creating a Backup

```console
$ bash scripts/backups/create_backup.sh

🗄️  ReDNA Backup System
=======================

Timestamp: 2025-10-11_15-30-45
Local backup: /Users/davidmakarewicz/Documents/ReDNA_Demos/backups
iCloud mirror: /Users/davidmakarewicz/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups

📦 Creating backup archive...
  → Copying core configuration...
  → Copying docs...
  → Copying coach configurations...
  → Copying prompts...
  → Copying scripts...
  → Copying data system state...
  → Compressing archive...
✅ Backup created: redna_backup_2025-10-11_15-30-45.tar.gz (1.2M)

☁️  Mirroring to iCloud Drive...
✅ iCloud mirror confirmed: redna_backup_2025-10-11_15-30-45.tar.gz (1.2M)

📊 Backup Summary
==================
Local backups:
  redna_backup_2025-10-09_10-15-30.tar.gz (1.1M)
  redna_backup_2025-10-10_09-20-15.tar.gz (1.2M)
  redna_backup_2025-10-11_15-30-45.tar.gz (1.2M)

iCloud backups:
  redna_backup_2025-10-09_10-15-30.tar.gz (1.1M)
  redna_backup_2025-10-10_09-20-15.tar.gz (1.2M)
  redna_backup_2025-10-11_15-30-45.tar.gz (1.2M)

✅ Backup complete!

To restore from backup:
  tar -xzf /Users/davidmakarewicz/Documents/ReDNA_Demos/backups/redna_backup_2025-10-11_15-30-45.tar.gz -C /tmp
```

---

## Restoring from Backup

### From Local Backup

```bash
# List available backups
ls -lh ~/Documents/ReDNA_Demos/backups/*.tar.gz

# Extract to temporary directory
tar -xzf ~/Documents/ReDNA_Demos/backups/redna_backup_YYYY-MM-DD_HH-MM-SS.tar.gz -C /tmp

# Review extracted files
ls -la /tmp/redna_backup_YYYY-MM-DD_HH-MM-SS/

# Restore specific files
cp /tmp/redna_backup_YYYY-MM-DD_HH-MM-SS/.cp_state.json ~/Documents/ReDNA_Demos/
```

### From iCloud Backup

```bash
# List iCloud backups
ls -lh ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/*.tar.gz

# Extract (same process as local)
tar -xzf ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/redna_backup_YYYY-MM-DD_HH-MM-SS.tar.gz -C /tmp
```

---

## Configuration

### Disabling iCloud Mirroring

To disable iCloud mirroring temporarily, comment out the mirroring section in `scripts/backups/create_backup.sh`:

```bash
# Mirror to iCloud
# echo ""
# echo "☁️  Mirroring to iCloud Drive..."
# rsync -av --ignore-existing "$BACKUP_DIR/"*.tar.gz "$ICLOUD_BACKUP_DIR/" 2>/dev/null || true
```

### Changing iCloud Backup Location

Edit the `ICLOUD_BACKUP_DIR` variable in:
- `scripts/backups/create_backup.sh`
- `scripts/autonomous/daily_health_check.sh`
- `scripts/autonomous/self_verify.sh`

```bash
# Change this line in all three scripts:
ICLOUD_BACKUP_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/YOUR_CUSTOM_PATH"
```

### Scheduling Automatic Backups

To run backups automatically via cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 9 AM
0 9 * * * /Users/davidmakarewicz/Documents/ReDNA_Demos/scripts/backups/create_backup.sh >> /tmp/redna_backup.log 2>&1
```

---

## Troubleshooting

### Issue: iCloud Directory Not Created

**Symptom**: Script reports iCloud directory not found

**Solution**:
```bash
# Manually create the directory
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups

# Verify it exists
ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups
```

### Issue: Backup Not Appearing in iCloud

**Symptom**: Local backup succeeds but iCloud mirror shows warning

**Causes**:
1. iCloud Drive not enabled in System Settings
2. iCloud Drive paused or offline
3. Insufficient iCloud storage space

**Solutions**:
1. Check System Settings → Apple ID → iCloud → iCloud Drive (must be ON)
2. Check iCloud sync status in Finder sidebar
3. Check iCloud storage: System Settings → Apple ID → iCloud → Manage Storage

### Issue: rsync Not Available

**Symptom**: Script falls back to `cp` command

**Solution**:
```bash
# Install rsync via Homebrew
brew install rsync

# Verify installation
which rsync
rsync --version
```

### Issue: Permission Denied

**Symptom**: Cannot write to iCloud directory

**Solution**:
```bash
# Check permissions
ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/

# If needed, recreate directory
rm -rf ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups
```

---

## Maintenance

### Automated Backup Retention

ReDNA includes an **automated retention cleanup system** with dry-run safety. For detailed information, see the [Backup Retention Policy](./BACKUP_RETENTION_POLICY.md).

**Quick Commands:**

```bash
# Preview what would be deleted (dry-run)
bash scripts/backups/retention_cleanup.sh

# Actually delete old backups
bash scripts/backups/retention_cleanup.sh --apply
```

### Retention Policy Summary

Default retention periods:
- **Local**: 30 days
- **iCloud**: 60 days (longer retention in cloud)
- **Safety**: Newest backup always kept, regardless of age

The retention script:
- ✅ Dry-run by default (safe)
- ✅ Never deletes the newest backup
- ✅ Won't delete backups < 24h old (unless `--force`)
- ✅ Integrated with daily health check
- ✅ Configurable via environment variables

See [BACKUP_RETENTION_POLICY.md](./BACKUP_RETENTION_POLICY.md) for complete documentation including:
- Usage examples
- Configuration options
- Scheduling automatic cleanup
- Troubleshooting
- Safety features

---

## Security & Privacy

### What's NOT Backed Up

The following are explicitly excluded:
- User data (`data/users/*/`)
- Test user data
- Telemetry logs
- Large generated files
- API keys or secrets (if stored separately)

### iCloud Security

- Backups in iCloud are encrypted in transit and at rest
- Only accessible from devices signed into your iCloud account
- Not accessible to Anthropic or third parties
- Subject to Apple's iCloud security policies

---

## Related Documentation

- [Daily Health Check Guide](./DAILY_HEALTH_REPORT.md)
- [Autonomous Systems Overview](../../scripts/autonomous/README.md)
- [Git Hygiene Guide](../GIT_HYGIENE_GUIDE.md)

---

## FAQ

**Q: Do I need to do anything after running the backup script?**
A: No. The script handles everything automatically, including iCloud mirroring.

**Q: How much iCloud storage do backups use?**
A: Each backup is typically 1-2 MB. With a 30-day retention, expect ~30-60 MB total.

**Q: Can I access backups from my iPhone or iPad?**
A: Yes, via the Files app. Navigate to iCloud Drive → ReDNA_Backups. However, you'll need a Mac to extract and restore the `.tar.gz` files.

**Q: What happens if iCloud is offline when I run a backup?**
A: The local backup still succeeds. The script will show a warning about iCloud, but won't fail. iCloud will sync automatically once connectivity is restored.

**Q: Can I use a different cloud provider instead of iCloud?**
A: Yes. Edit the `ICLOUD_BACKUP_DIR` variable to point to any mounted cloud drive (Dropbox, Google Drive, OneDrive, etc.).

---

**Document Version**: 1.0
**Implementation Date**: 2025-10-11
**Next Review**: 2025-11-11
