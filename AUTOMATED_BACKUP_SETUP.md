# Automated Backup Setup Guide

**Status**: ✅ Ready to Install
**Date**: October 11, 2025

---

## Quick Start

### One-Command Setup
```bash
bash scripts/backups/setup_cron.sh
```

This will:
1. ✅ Verify backup scripts exist
2. ✅ Make scripts executable
3. ✅ Install cron jobs for automated backups
4. ✅ Create backup and cleanup schedules

---

## Schedule

Once installed, backups will run automatically:

| Task | Schedule | Command |
|------|----------|---------|
| **Daily Backup** | 9:00 AM | `create_backup.sh` |
| **Weekly Cleanup** | Sundays 10:00 AM | `retention_cleanup.sh --apply` |

---

## What Gets Backed Up

### Included
- ✅ All Python source code (`ReDNACoreDemo/`)
- ✅ Web frontend (`web/src/`)
- ✅ Documentation (`docs/`)
- ✅ Scripts (`scripts/`)
- ✅ Configuration files
- ✅ User data (`data/users/`)
- ✅ Ontology registry (`core/ontology/`)

### Excluded
- ❌ `node_modules/` (can be regenerated)
- ❌ `.next/` (build artifacts)
- ❌ `.venv/` (Python virtual environment)
- ❌ `__pycache__/` (Python cache)
- ❌ `.git/` (version control)
- ❌ Large binary files

---

## Backup Locations

### Primary Location
```
/Users/davidmakarewicz/Documents/ReDNA_Demos/backups/
```

### iCloud Mirror (Auto-sync)
```
~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups/
```

**Benefits**:
- Automatic cloud sync
- Access from all Apple devices
- Protection against local disk failure
- 60-day retention (vs 30-day local)

---

## Retention Policy

| Location | Retention Period | Always Keep |
|----------|-----------------|-------------|
| Local | 30 days | Newest backup |
| iCloud | 60 days | Newest backup |

**Safety Features**:
- 24-hour minimum age before cleanup
- Always keeps newest backup
- Dry-run by default (requires `--apply`)
- Exit codes for monitoring

---

## Manual Operations

### Create Backup Now
```bash
bash scripts/backups/create_backup.sh
```

Creates timestamped backup:
```
backups/backup_2025-10-11_183045.tar.gz
```

### Preview Cleanup (Dry Run)
```bash
bash scripts/backups/retention_cleanup.sh
```

Shows what would be deleted without actually deleting.

### Apply Cleanup
```bash
bash scripts/backups/retention_cleanup.sh --apply
```

Actually removes old backups per retention policy.

---

## Monitoring

### View Backup Logs
```bash
tail -f backups/backup.log
```

### View Cleanup Logs
```bash
tail -f backups/cleanup.log
```

### Check Recent Backups
```bash
ls -lht backups/*.tar.gz | head -10
```

### Check iCloud Status
```bash
ls -lht ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/*.tar.gz | head -10
```

---

## Troubleshooting

### Issue: Cron jobs not running

**Check cron is running**:
```bash
sudo launchctl list | grep cron
```

**Check cron logs** (macOS):
```bash
log show --predicate 'process == "cron"' --last 1h
```

**Verify cron jobs installed**:
```bash
crontab -l
```

### Issue: Backups not appearing

**Check script permissions**:
```bash
ls -l scripts/backups/*.sh
# Should show: -rwxr-xr-x
```

**Test manually**:
```bash
bash scripts/backups/create_backup.sh
echo "Exit code: $?"
# Should be 0
```

**Check disk space**:
```bash
df -h
```

### Issue: iCloud not syncing

**Check iCloud Drive is enabled**:
- System Settings → Apple ID → iCloud → iCloud Drive

**Check folder exists**:
```bash
ls -la ~/Library/Mobile\ Documents/com~apple~CloudDocs/
```

**Manually trigger sync** (if needed):
```bash
# iCloud syncs automatically, but you can check status:
brctl log --wait --shorten
```

---

## Advanced Configuration

### Change Backup Schedule

Edit crontab:
```bash
crontab -e
```

Cron syntax:
```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sun=0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

Examples:
```bash
# Every 6 hours
0 */6 * * * /path/to/create_backup.sh

# Twice daily (9 AM and 9 PM)
0 9,21 * * * /path/to/create_backup.sh

# Weekdays only at 8 AM
0 8 * * 1-5 /path/to/create_backup.sh
```

### Change Retention Period

Edit `retention_cleanup.sh`:
```bash
# Line ~20
LOCAL_RETENTION_DAYS=30    # Change to desired value
ICLOUD_RETENTION_DAYS=60   # Change to desired value
```

### Disable iCloud Sync

Edit `create_backup.sh`:
```bash
# Comment out the iCloud sync section (lines ~60-80)
# if [ -d "$ICLOUD_DIR" ]; then
#   ...
# fi
```

---

## Backup Restoration

### Restore from Local Backup
```bash
# 1. Navigate to project parent directory
cd ~/Documents

# 2. Extract backup
tar -xzf ReDNA_Demos/backups/backup_2025-10-11_183045.tar.gz

# 3. This creates ReDNA_Demos_backup_2025-10-11_183045/

# 4. Copy files as needed
cp -r ReDNA_Demos_backup_2025-10-11_183045/* ReDNA_Demos/
```

### Restore from iCloud
```bash
# 1. Copy backup from iCloud
cp ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/backup_2025-10-11_183045.tar.gz ~/Documents/

# 2. Follow local restoration steps above
```

### Full System Recovery
```bash
# If ReDNA_Demos is completely lost:

# 1. Get latest backup from iCloud
cd ~/Documents
cp ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/backup_*.tar.gz ./

# 2. Extract
tar -xzf backup_*.tar.gz

# 3. Rename to ReDNA_Demos
mv ReDNA_Demos_backup_* ReDNA_Demos

# 4. Reinstall dependencies
cd ReDNA_Demos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd web && npm install

# 5. Restart services
bash scripts/start_all_services.sh
```

---

## Best Practices

### Do's ✅
- ✅ Test backups monthly
- ✅ Monitor backup logs
- ✅ Verify iCloud sync
- ✅ Keep cron jobs enabled
- ✅ Test restoration process

### Don'ts ❌
- ❌ Don't disable backups without reason
- ❌ Don't manually delete recent backups
- ❌ Don't ignore failed backup notifications
- ❌ Don't skip cleanup (disk space)
- ❌ Don't rely on backups alone (use git too)

---

## Backup Size Reference

| Component | Typical Size |
|-----------|-------------|
| Python code | ~5 MB |
| Web frontend | ~2 MB |
| Documentation | ~1 MB |
| User data | ~10 MB |
| Ontology registry | ~4 MB |
| **Total (compressed)** | ~15-25 MB |

**Note**: Actual size varies based on user data volume.

---

## Integration with Git

**Backups complement git, not replace it**:

| System | Purpose | What It Protects |
|--------|---------|-----------------|
| **Git** | Version control | Code changes, history |
| **Backups** | Disaster recovery | User data, config, entire state |

**Strategy**:
1. Use git for code changes
2. Use backups for complete system snapshots
3. Commit to git daily
4. Backups run automatically

---

## Security Considerations

### Backup Contents
- ❌ Backups may contain sensitive user data
- ❌ Backups may contain API keys/secrets
- ✅ Stored locally and in personal iCloud
- ✅ Not shared publicly

### Best Practices
1. ✅ Review `.gitignore` (backups excluded)
2. ✅ Don't commit backups to git
3. ✅ Secure iCloud account with 2FA
4. ✅ Encrypt backups if sharing (future enhancement)

---

## Status Check Commands

Quick reference for checking backup system health:

```bash
# Are cron jobs installed?
crontab -l | grep -i backup

# When was last backup created?
ls -lt backups/*.tar.gz | head -1

# How many backups exist locally?
ls backups/*.tar.gz | wc -l

# How many backups in iCloud?
ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/*.tar.gz | wc -l

# Disk usage of backups?
du -sh backups/

# Full health check
bash scripts/autonomous/daily_health_check.sh
```

---

## Uninstallation

To remove automated backups:

### Remove Cron Jobs
```bash
crontab -e
# Delete the ReDNA_Demos backup lines
```

Or remove entire crontab:
```bash
crontab -r
```

### Keep Existing Backups
Backups remain in:
- `backups/`
- `~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups/`

### Delete All Backups (if desired)
```bash
# Local
rm backups/*.tar.gz

# iCloud (careful!)
rm ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/*.tar.gz
```

---

## Support

### Documentation
- [docs/ops/ICLOUD_BACKUP_SETUP.md](docs/ops/ICLOUD_BACKUP_SETUP.md:1)
- [docs/ops/BACKUP_RETENTION_POLICY.md](docs/ops/BACKUP_RETENTION_POLICY.md:1)
- [docs/ops/DAILY_HEALTH_REPORT.md](docs/ops/DAILY_HEALTH_REPORT.md:1)

### Scripts
- [scripts/backups/create_backup.sh](scripts/backups/create_backup.sh:1)
- [scripts/backups/retention_cleanup.sh](scripts/backups/retention_cleanup.sh:1)
- [scripts/backups/setup_cron.sh](scripts/backups/setup_cron.sh:1)

---

## Summary

The automated backup system provides:
- ✅ Daily backups at 9 AM
- ✅ Weekly cleanup on Sundays
- ✅ Dual locations (local + iCloud)
- ✅ 30-day local retention
- ✅ 60-day iCloud retention
- ✅ Comprehensive logging
- ✅ Easy restoration

**Installation**: `bash scripts/backups/setup_cron.sh`
**Verification**: `crontab -l`
**Testing**: `bash scripts/backups/create_backup.sh`

---

**Document Version**: 1.0
**Last Updated**: 2025-10-11
**Status**: ✅ Ready for Production
