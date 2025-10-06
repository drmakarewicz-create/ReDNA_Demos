# ReDNA iCloud Backup System

## ✅ Setup Complete!

Your ReDNA project is now configured to backup to iCloud Drive automatically.

**Backup Location**: `~/Library/Mobile Documents/com~apple~CloudDocs/ReDNA_Backups/`

---

## Two Backup Scripts

### 1. Quick Backup (Recommended for Daily Use) ⚡

**Script**: `./quick_backup_to_icloud.sh`

**What it backs up**:
- ✅ All source code (`.py`, `.js`, `.ts`, `.tsx`)
- ✅ Configuration files (`.json`, `.yaml`, `.yml`)
- ✅ Documentation (`.md` files)
- ✅ Scripts (`.sh` files)

**What it excludes**:
- ❌ `node_modules/` (can reinstall)
- ❌ `.venv/` (can recreate)
- ❌ Large binary files
- ❌ Snapshots and full backups

**Size**: ~57MB
**Time**: ~10 seconds
**Retention**: Keeps last 10 backups

**Usage**:
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
./quick_backup_to_icloud.sh
```

---

### 2. Full Backup (For Complete Archives) 📦

**Script**: `./backup_to_icloud.sh`

**What it backs up**:
- ✅ Everything in the project (code, data, configs)
- ⚠️ Excludes only: `node_modules`, `.venv`, `__pycache__`, `.git`

**Size**: Variable (depends on data size)
**Time**: Several minutes
**Retention**: Keeps last 7 backups

**Usage**:
```bash
cd /Users/davidmakarewicz/Documents/ReDNA_Demos
./backup_to_icloud.sh
```

---

## Viewing Your Backups

### In Finder:
1. Open Finder
2. Click **iCloud Drive** in sidebar
3. Navigate to **ReDNA_Backups** folder

### In Terminal:
```bash
ls -lh ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/
```

---

## Restoring from Backup

### Quick Restore (Code Only):
```bash
cd ~/Downloads
unzip ReDNA_QuickBackup_YYYYMMDD_HHMMSS.zip -d ReDNA_Restored
cd ReDNA_Restored/ReDNA_Demos

# Reinstall dependencies
cd web && npm install
cd ../ReDNACoreDemo && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Full Restore:
```bash
cd ~/Downloads
unzip ReDNA_Backup_YYYYMMDD_HHMMSS.zip -d ReDNA_Restored
cd ReDNA_Restored/ReDNA_Demos

# May still need to reinstall node_modules and .venv (excluded from backup)
cd web && npm install
```

---

## Automatic Backups (Optional)

### Schedule Quick Backups Daily

**Using cron** (runs at 2 AM every day):
```bash
# Edit crontab
crontab -e

# Add this line:
0 2 * * * /Users/davidmakarewicz/Documents/ReDNA_Demos/quick_backup_to_icloud.sh > /tmp/redna_backup.log 2>&1
```

**Using launchd** (macOS preferred method):

Create `~/Library/LaunchAgents/com.redna.backup.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.redna.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/davidmakarewicz/Documents/ReDNA_Demos/quick_backup_to_icloud.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/redna_backup.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/redna_backup_error.log</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.redna.backup.plist
```

---

## Current Backup Status

### First Backup Completed ✅

**Quick Backup**:
- ✅ Created: October 4, 2025 @ 5:39 PM
- 📦 Size: 57MB
- 📁 File: `ReDNA_QuickBackup_20251004_173922.zip`
- 💾 Location: iCloud Drive > ReDNA_Backups

**Full Backup**:
- 🔄 In progress (running in background)
- 📊 Project size: 21GB
- ⏱️ Expected time: 5-10 minutes

---

## iCloud Sync Status

Your backups will automatically sync to:
- ☁️ iCloud.com (web access)
- 📱 Other Macs with iCloud Drive enabled
- 📲 iPhone/iPad (via Files app → iCloud Drive → ReDNA_Backups)

**Check sync status in Finder**:
- Small cloud icon next to file = syncing
- Green checkmark = synced to iCloud

---

## Best Practices

1. **Run quick backups frequently** (before major changes)
   ```bash
   ./quick_backup_to_icloud.sh
   ```

2. **Run full backups occasionally** (weekly or before major updates)
   ```bash
   ./backup_to_icloud.sh
   ```

3. **Verify backups work** (test restore once a month)

4. **Monitor iCloud storage**:
   - System Settings → Apple ID → iCloud → Manage Storage
   - Quick backups use minimal space (~57MB each)
   - Full backups may use several GB

---

## Troubleshooting

### "Backup too slow"
- Use quick backup instead of full backup
- Quick backup completes in ~10 seconds

### "iCloud Drive full"
- Delete old backups manually:
  ```bash
  ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/
  rm ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/ReDNA_Backup_YYYYMMDD_*.zip
  ```

### "Can't find backup folder"
```bash
open ~/Library/Mobile\ Documents/com~apple~CloudDocs/ReDNA_Backups/
```

### "Backup failed"
- Check iCloud storage available
- Ensure iCloud Drive is enabled (System Settings → Apple ID → iCloud)
- Check logs: `cat /tmp/backup_log.txt`

---

## Files Created

1. **`backup_to_icloud.sh`** - Full backup script
2. **`quick_backup_to_icloud.sh`** - Quick code-only backup (recommended)
3. **`BACKUP_README.md`** - This file

---

## Summary

✅ **You're all set!** Your ReDNA project can now be backed up to iCloud Drive with two simple scripts:

- **Daily**: Run `./quick_backup_to_icloud.sh` (10 sec, 57MB)
- **Weekly**: Run `./backup_to_icloud.sh` (5 min, full backup)

Both scripts automatically:
- Create timestamped backups
- Clean up old backups
- Sync to iCloud Drive
- Keep your most important work safe

**Next Step**: Consider scheduling automatic daily quick backups using cron or launchd (see "Automatic Backups" section above).

---

**Questions?** Check the troubleshooting section or run the scripts with verbose output to see what's happening.
