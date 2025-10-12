# Operations Documentation Index

**Last Updated**: 2025-10-11
**Status**: Active

---

## 📋 Quick Links

### Start Here
- **[QUICK_START_AUTONOMOUS.md](../../QUICK_START_AUTONOMOUS.md)** - ⚡ 15-minute setup guide

### Daily Operations
- **[DAILY_HEALTH_REPORT.md](DAILY_HEALTH_REPORT.md)** - 📊 Latest system health status
- **[health_archive/](health_archive/)** - 📁 Historical health reports

### Guides
- **[AUTONOMOUS_MAINTENANCE_GUIDE.md](AUTONOMOUS_MAINTENANCE_GUIDE.md)** - 🤖 Complete automation guide
- **[GIT_HYGIENE_VALIDATION.md](GIT_HYGIENE_VALIDATION.md)** - 🧹 Git cleanup validation
- **[../GIT_HYGIENE_GUIDE.md](../GIT_HYGIENE_GUIDE.md)** - 📚 Git hygiene procedures

### Reports
- **[AUTONOMOUS_SESSION_SUMMARY_2025_10_11.md](AUTONOMOUS_SESSION_SUMMARY_2025_10_11.md)** - 📝 Session work summary
- **[GIT_STATUS_REPORT.md](GIT_STATUS_REPORT.md)** - 📈 Git repository analysis
- **[ROTATION_LOG.md](ROTATION_LOG.md)** - 🔄 Telemetry rotation log

---

## 🗂️ Directory Structure

```
docs/ops/
├── README.md                                    (this file)
├── AUTONOMOUS_MAINTENANCE_GUIDE.md              (complete guide)
├── AUTONOMOUS_SESSION_SUMMARY_2025_10_11.md     (session summary)
├── DAILY_HEALTH_REPORT.md                       (latest health)
├── GIT_HYGIENE_VALIDATION.md                    (hygiene audit)
├── GIT_STATUS_REPORT.md                         (git analysis)
├── GIT_STATUS_REPORT_CLAUDE.md                  (validation copy)
├── ROTATION_LOG.md                              (telemetry logs)
└── health_archive/                              (archived reports)
    └── health_2025-10-11.md
```

---

## 🚀 Common Tasks

### Check System Health
```bash
cat docs/ops/DAILY_HEALTH_REPORT.md
```

### Run Health Check
```bash
bash scripts/autonomous/daily_health_check.sh
```

### Review Git Status
```bash
python3 scripts/git_sanity/scan_status.py
cat docs/ops/GIT_STATUS_REPORT.md
```

### View Archived Reports
```bash
ls -lt docs/ops/health_archive/
cat docs/ops/health_archive/health_2025-10-11.md
```

---

## 📊 What Each Report Contains

### Daily Health Report
- Executive summary
- 7-category system validation
- Issue count and severity
- Recommended actions

### Git Status Report
- Total tracked/untracked count
- Top 30 noisy paths
- Disk usage hotspots

### Git Hygiene Validation
- Script infrastructure audit
- .gitignore coverage
- Hook verification
- Tracked file analysis

### Session Summary
- Work completed
- Issues found/fixed
- Artifacts created
- Next steps

---

## 🔧 Maintenance

### Daily
- Review `DAILY_HEALTH_REPORT.md`
- Check for critical issues

### Weekly
- Review archived reports in `health_archive/`
- Check trend in git status count

### Monthly
- Clean old archives (keep 3 months)
- Review and update guides

---

## 📞 Getting Help

1. **Check the guides** - All procedures documented
2. **Review latest health report** - System status
3. **See session summary** - What changed recently
4. **Run verification** - `bash scripts/autonomous/self_verify.sh`

---

## 🔗 Related Documentation

- [Git Hygiene Guide](../GIT_HYGIENE_GUIDE.md)
- [Quick Start Guide](../../QUICK_START_AUTONOMOUS.md)
- [Benchmark Roadmap](../Benchmark_Roadmap_v4.0.md)
- [DevX Guide](../DEVX_OVERVIEW.md)

---

**Maintained by**: Autonomous Health Check System
**Report Issues**: Create a GitHub issue or check health reports
