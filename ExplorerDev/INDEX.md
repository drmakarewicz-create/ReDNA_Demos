# Developer Tools - Documentation Index

**Last Updated:** 2025-10-04
**Status:** ✅ Production Ready

---

## 📖 Documentation Quick Links

### Getting Started (Start Here)

1. **[README_DEV_TOOLS.md](README_DEV_TOOLS.md)** - Main README
   - Overview & features
   - Quick start guide
   - Architecture & troubleshooting
   - FAQ

2. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Cheat Sheet
   - One-page reference for all features
   - Keyboard shortcuts
   - Common workflows
   - Quick troubleshooting

3. **[DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md)** - Interactive Demo
   - 5-minute guided tour
   - Step-by-step walkthroughs
   - Full debugging workflow example

---

### User Documentation

4. **[DEV_TOOLS_README.md](DEV_TOOLS_README.md)** - Comprehensive User Guide
   - Feature details for each tab
   - Daily workflows
   - Tips & tricks
   - Troubleshooting guide

5. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick Reference Card
   - Command summary
   - Common operations
   - File locations
   - ROI metrics

---

### Developer Documentation

6. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical Spec
   - UX sketch & wireframes
   - Implementation details
   - PR-style diff summary
   - 10-item follow-up punch list

7. **[../DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md](../DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md)** - Sprint Summary
   - Pain points identified
   - Solution overview
   - Success metrics
   - Requirements vs delivered

---

## 🧭 Navigation by Use Case

### "I want to get started quickly"
→ Start: [README_DEV_TOOLS.md - Quick Start](README_DEV_TOOLS.md#quick-start)
→ Then: [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md)

### "I need help with a specific feature"
→ Go to: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
→ Or: [DEV_TOOLS_README.md - Features](DEV_TOOLS_README.md#features)

### "I want to understand how it works"
→ Read: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
→ Check: [Architecture section](README_DEV_TOOLS.md#architecture)

### "I want to contribute a new feature"
→ See: [README_DEV_TOOLS.md - Contributing](README_DEV_TOOLS.md#contributing)
→ Review: [Follow-up punch list](IMPLEMENTATION_SUMMARY.md#10-item-follow-up-punch-list)

### "I'm having trouble with something"
→ Check: [QUICK_REFERENCE.md - Troubleshooting](QUICK_REFERENCE.md#troubleshooting)
→ Or: [DEV_TOOLS_README.md - Troubleshooting](DEV_TOOLS_README.md#troubleshooting)

---

## 📂 Source Code Files

| File | Purpose | Lines |
|------|---------|-------|
| [test_runner_utils.py](test_runner_utils.py) | pytest execution & history | 280 |
| [artifact_browser_utils.py](artifact_browser_utils.py) | File scanning & search | 260 |
| [log_tail_utils.py](log_tail_utils.py) | Log sources & server detection | 220 |
| [dev_tools_ui.py](dev_tools_ui.py) | Streamlit UI (4 tabs) | 530 |
| [explorer_dev.py](explorer_dev.py) | Main integration point | +6 |

---

## 🎯 Feature-Specific Docs

### Test Runner
- Overview: [README_DEV_TOOLS.md - Test Runner](README_DEV_TOOLS.md#-test-runner)
- Guide: [DEV_TOOLS_README.md - Test Runner](DEV_TOOLS_README.md#test-runner)
- Reference: [QUICK_REFERENCE.md - Test Runner](QUICK_REFERENCE.md#-test-runner)
- Demo: [DEMO_WALKTHROUGH.md - Demo 1](DEMO_WALKTHROUGH.md#demo-1-test-runner-90-seconds)

### Log Tails
- Overview: [README_DEV_TOOLS.md - Log Tails](README_DEV_TOOLS.md#-log-tails)
- Guide: [DEV_TOOLS_README.md - Log Tails](DEV_TOOLS_README.md#log-tails)
- Reference: [QUICK_REFERENCE.md - Log Tails](QUICK_REFERENCE.md#-log-tails)
- Demo: [DEMO_WALKTHROUGH.md - Demo 2](DEMO_WALKTHROUGH.md#demo-2-log-tails-60-seconds)

### Artifact Browser
- Overview: [README_DEV_TOOLS.md - Artifact Browser](README_DEV_TOOLS.md#-artifact-browser)
- Guide: [DEV_TOOLS_README.md - Artifact Browser](DEV_TOOLS_README.md#artifact-browser)
- Reference: [QUICK_REFERENCE.md - Artifact Browser](QUICK_REFERENCE.md#-artifact-browser)
- Demo: [DEMO_WALKTHROUGH.md - Demo 3](DEMO_WALKTHROUGH.md#demo-3-artifact-browser-90-seconds)

### HTTP Helpers
- Overview: [README_DEV_TOOLS.md - HTTP Helpers](README_DEV_TOOLS.md#-http-helpers)
- Guide: [DEV_TOOLS_README.md - HTTP Helpers](DEV_TOOLS_README.md#http-helpers)
- Reference: [QUICK_REFERENCE.md - HTTP Helpers](QUICK_REFERENCE.md#-http-helpers)
- Demo: [DEMO_WALKTHROUGH.md - Demo 4](DEMO_WALKTHROUGH.md#demo-4-http-helpers-60-seconds)

---

## 🔗 External Resources

- **Startup Script:** [../scripts/start_dev_explorer.sh](../scripts/start_dev_explorer.sh)
- **Main Project README:** [../README.md](../README.md)
- **Test Files:** [../test_*acceptance*.py](../)
- **User Data:** [../data/users/](../data/users/)
- **Automation Logs:** [../docs/automation_log/](../docs/automation_log/)

---

## 📊 Metrics & Analytics

- **Test History:** `../data/dev_logs/test_history.jsonl`
- **Recent Artifacts:** `../data/dev_logs/recent_artifacts.jsonl`
- **Last Test Output:** `../data/dev_logs/last_test_output.log`
- **Diagnostics Log:** `../data/dev_logs/diagnostics.log`

---

## 🚀 Quick Commands

```bash
# Start Developer Explorer
./scripts/start_dev_explorer.sh

# Or manually with custom port
streamlit run ExplorerDev/explorer_dev.py --server.port=8502

# Run smoke test
python3 -c "from ExplorerDev import test_runner_utils; print('✅ OK')"

# Check server status
lsof -i :8001

# View recent test runs
tail -f data/dev_logs/test_history.jsonl
```

---

## 📝 Change Log

### v1.0 (2025-10-04)
- ✅ Initial release
- ✅ Test Runner with history
- ✅ Log Tails with 4 sources
- ✅ Artifact Browser with search
- ✅ HTTP Helpers with 8 endpoints
- ✅ Comprehensive documentation suite

---

## 🔮 Roadmap

See [IMPLEMENTATION_SUMMARY.md - Follow-Up Punch List](IMPLEMENTATION_SUMMARY.md#10-item-follow-up-punch-list) for upcoming features prioritized by ROI.

**Next Sprint (High ROI):**
1. Log line navigation to source code
2. Test history trend charts
3. Artifact diff viewer

---

## 🆘 Support

- **Questions:** Create GitHub issue or ping @david
- **Bug Reports:** Use label `dev-tools`
- **Feature Requests:** See punch list first, then create issue

---

**Happy Testing! 🧪**
