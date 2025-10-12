# Autonomous Maintenance Guide

**Version**: 1.0
**Created**: 2025-10-11
**Status**: Active

---

## Overview

This guide documents the autonomous maintenance infrastructure for the ReDNA project. These systems can run without human intervention to monitor health, detect issues, and maintain code quality.

---

## 🤖 Automated Systems

### 1. Daily Health Check

**Location**: `scripts/autonomous/daily_health_check.sh`

**Purpose**: Comprehensive daily validation of system health

**What it checks**:
- Directory structure integrity
- Python cache levels
- Import validation
- Test suite smoke tests
- Service port availability
- Git repository status
- Disk usage

**Output**: `docs/ops/DAILY_HEALTH_REPORT.md`

**Manual execution**:
```bash
bash scripts/autonomous/daily_health_check.sh
```

**Cron setup** (runs daily at 9 AM):
```bash
0 9 * * * cd /path/to/ReDNA_Demos && bash scripts/autonomous/daily_health_check.sh
```

**GitHub Actions**: `.github/workflows/daily-health-check.yml`
- Runs automatically every day at 9 AM UTC
- Creates GitHub issues if failures detected
- Archives reports for 90 days

---

### 2. Import Verification

**Location**: `scripts/autonomous/verify_imports.py`

**Purpose**: Validates Python import structure and detects issues

**What it checks**:
- Syntax errors in Python files
- Critical module imports
- Circular import patterns
- Orphaned modules

**Manual execution**:
```bash
python3 scripts/autonomous/verify_imports.py
```

**Integration**: Called automatically by daily health check

---

### 3. Self-Verification System

**Location**: `scripts/autonomous/self_verify.sh`

**Purpose**: Quick verification script with visual output

**What it checks**:
- All critical systems
- Color-coded pass/fail status
- Exit codes for CI integration

**Manual execution**:
```bash
bash scripts/autonomous/self_verify.sh
```

---

### 4. Git Hygiene Monitor

**Location**: `scripts/git_sanity/scan_status.py`

**Purpose**: Tracks git repository cleanliness

**What it reports**:
- Total tracked/untracked files
- Noisy directory paths
- Disk usage hotspots

**Manual execution**:
```bash
python3 scripts/git_sanity/scan_status.py
```

**Integrated into**: Daily health check (section 6)

---

## 📅 Scheduling Options

### Option 1: GitHub Actions (Recommended)

**Advantages**:
- No local machine needed
- Runs on GitHub infrastructure
- Automatic issue creation on failure
- Artifact archiving
- Email notifications

**Setup**:
1. Workflows already created in `.github/workflows/`
2. Push to GitHub repository
3. Enable Actions in repository settings
4. Configure notification preferences

**Workflows**:
- `daily-health-check.yml` - Daily at 9 AM UTC
- `test-suite.yml` - On push, PR, and every 6 hours

---

### Option 2: Local Cron Jobs

**Advantages**:
- Runs on your machine
- Access to local services
- No GitHub Actions minutes used

**Setup**:

1. Open crontab:
   ```bash
   crontab -e
   ```

2. Add entries:
   ```cron
   # Daily health check at 9 AM
   0 9 * * * cd /Users/davidmakarewicz/Documents/ReDNA_Demos && bash scripts/autonomous/daily_health_check.sh >> logs/cron_health.log 2>&1

   # Import verification every 12 hours
   0 */12 * * * cd /Users/davidmakarewicz/Documents/ReDNA_Demos && python3 scripts/autonomous/verify_imports.py >> logs/cron_imports.log 2>&1

   # Git status scan weekly on Mondays
   0 10 * * 1 cd /Users/davidmakarewicz/Documents/ReDNA_Demos && python3 scripts/git_sanity/scan_status.py >> logs/cron_git.log 2>&1
   ```

3. Create logs directory:
   ```bash
   mkdir -p logs
   ```

---

### Option 3: launchd (macOS)

**Advantages**:
- Better than cron on macOS
- Can run on wake/login
- More reliable scheduling

**Setup**:

1. Create plist file at `~/Library/LaunchAgents/com.redna.health.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.redna.health</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/davidmakarewicz/Documents/ReDNA_Demos/scripts/autonomous/daily_health_check.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/davidmakarewicz/Documents/ReDNA_Demos</string>
    <key>StandardOutPath</key>
    <string>/Users/davidmakarewicz/Documents/ReDNA_Demos/logs/health.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/davidmakarewicz/Documents/ReDNA_Demos/logs/health.error.log</string>
</dict>
</plist>
```

2. Load the agent:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.redna.health.plist
   ```

3. Start immediately (optional):
   ```bash
   launchctl start com.redna.health
   ```

---

## 📊 Reports & Artifacts

### Daily Health Report

**Location**: `docs/ops/DAILY_HEALTH_REPORT.md`

**Contains**:
- Executive summary
- System status breakdown
- Issue count
- Recommended actions

**Archive**: `docs/ops/health_archive/health_YYYY-MM-DD.md`

---

### Git Status Report

**Location**: `docs/ops/GIT_STATUS_REPORT.md`

**Contains**:
- Total entry count
- Top 30 noisy paths
- Disk usage hotspots

---

### Import Verification Output

Printed to stdout, captured in logs

**Contains**:
- Syntax errors
- Import failures
- Circular dependencies
- Orphaned modules

---

## 🚨 Alerting & Notifications

### GitHub Actions Notifications

**Email alerts**:
1. Go to GitHub Settings → Notifications
2. Enable "Actions" notifications
3. Choose email or web notifications

**Slack integration**:
Add to workflow:
```yaml
- name: Slack Notification
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: 'Daily health check completed'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
  if: always()
```

---

### Local Notifications (macOS)

Add to cron script:
```bash
# After health check runs
if [ $? -ne 0 ]; then
    osascript -e 'display notification "Health check failed!" with title "ReDNA Alert"'
fi
```

---

## 🔧 Maintenance Tasks

### Weekly

- Review health reports in `docs/ops/health_archive/`
- Check git status count trend
- Review import verification warnings

### Monthly

- Run full test suite: `PYTHONPATH=.:ReDNACoreDemo python3 -m pytest ReDNACoreDemo/tests/ -v`
- Review disk usage trends
- Clean old archived reports (keep last 3 months)
- Update dependencies

### Quarterly

- Review and update health check criteria
- Audit GitHub Actions usage
- Update documentation
- Review and remove orphaned modules

---

## 📈 Metrics to Track

### Health Indicators

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Import Failures | 0 | 1-2 | 3+ |
| Test Failures | 0 | 1-5 | 6+ |
| Git Status Count | <500 | 500-1000 | 1000+ |
| Python Cache | <25K files | 25K-30K | 30K+ |
| Disk Usage (ReDNA) | <500MB | 500MB-1GB | 1GB+ |

---

## 🛠️ Troubleshooting

### Health Check Fails

1. Check logs: `cat docs/ops/DAILY_HEALTH_REPORT.md`
2. Identify failing section
3. Run component manually:
   ```bash
   PYTHONPATH=.:ReDNACoreDemo python3 -c "from ReDNACoreDemo.core import api"
   ```
4. Review error messages
5. Fix and re-run: `bash scripts/autonomous/daily_health_check.sh`

---

### Import Verification Issues

1. Run with verbose output:
   ```bash
   python3 scripts/autonomous/verify_imports.py | tee /tmp/import_report.txt
   ```
2. Review syntax errors first
3. Check for missing dependencies:
   ```bash
   pip list | grep -i <module_name>
   ```
4. Fix circular imports by refactoring

---

### GitHub Actions Not Running

1. Check workflow status: Repository → Actions tab
2. Verify cron syntax: [crontab.guru](https://crontab.guru/)
3. Check repository permissions: Settings → Actions → General
4. Review workflow logs for errors
5. Test workflow manually: Actions → Run workflow

---

## 📝 Adding New Checks

To add a new automated check:

1. **Create script** in `scripts/autonomous/`
2. **Make executable**: `chmod +x script_name.sh`
3. **Test locally**: Run manually and verify output
4. **Add to health check**: Edit `daily_health_check.sh`
5. **Update documentation**: Add section here
6. **Commit and push**: Let GitHub Actions pick it up

**Example**:
```bash
# In daily_health_check.sh, add:

echo "9️⃣  New Custom Check"
cat >> "$REPORT_FILE" << 'EOF'

## 9. New Custom Check

EOF

if ./scripts/autonomous/custom_check.sh; then
    echo "  ✅ Custom check passed" >> "$REPORT_FILE"
else
    echo "  ❌ Custom check failed" >> "$REPORT_FILE"
    OVERALL_STATUS="❌ UNHEALTHY"
    ((ISSUES_FOUND++))
fi
```

---

## 🎯 Best Practices

1. **Review reports regularly** - Don't let alerts pile up
2. **Fix warnings promptly** - They become errors eventually
3. **Keep scripts simple** - Easier to debug and maintain
4. **Archive old reports** - Keep history for trend analysis
5. **Test changes locally** - Before pushing to automation
6. **Monitor resource usage** - GitHub Actions has limits
7. **Document customizations** - Update this guide

---

## 🔗 Related Documentation

- [Git Hygiene Guide](../GIT_HYGIENE_GUIDE.md)
- [Git Hygiene Validation](GIT_HYGIENE_VALIDATION.md)
- [Daily Health Reports](health_archive/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

**Last Updated**: 2025-10-11
**Maintainer**: ReDNA Development Team
**Questions**: Create an issue in the repository
