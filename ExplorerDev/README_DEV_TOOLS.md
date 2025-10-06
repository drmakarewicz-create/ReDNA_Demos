# Developer Tools for ExplorerDev

**Version:** 1.0
**Status:** ✅ Production Ready
**Added:** 2025-10-04

---

## Overview

The **Developer Tools** section consolidates common development workflows into the ExplorerDev UI, eliminating context-switching between terminal, browser, and file explorer.

### What's Included

| Feature | Purpose | Time Saved |
|---------|---------|------------|
| 🧪 **Test Runner** | Run acceptance tests with one click | 5-10 min/day |
| 📜 **Log Tails** | Monitor backend logs in real-time | 2-5 min/day |
| 📁 **Artifact Browser** | Quick-open user data & automation logs | 2-5 min/day |
| 🌐 **HTTP Helpers** | Test API endpoints without Postman | 1-3 min/day |

**Total time saved:** 10-23 minutes per developer per day

---

## Quick Start

### 1. Launch Developer Tools

```bash
# Start backend (if not running)
uvicorn ReDNACoreDemo.core.api:app --port 8001 &

# Start ExplorerDev with helper script
./scripts/start_dev_explorer.sh

# Or manually
streamlit run ExplorerDev/explorer_dev.py
```

### 2. Navigate to Developer Tools

1. Open browser to ExplorerDev (usually `http://localhost:8502`)
2. Click **"Developer Tools"** in sidebar
3. Choose a tab: Test Runner / Log Tails / Artifact Browser / HTTP Helpers

### 3. Run Your First Test

1. Tab: **🧪 Test Runner**
2. Select: `test_hc_v2_sprint1c_acceptance.py`
3. Click: **▶️ Run All**
4. View: Results in Summary tab

---

## Features

### 🧪 Test Runner

**One-click pytest execution with visual results**

- **Test file selector** - Dropdown for all `test_*acceptance*.py` files
- **Test function selector** - Run specific test or all tests
- **Verbose mode** - Toggle `-v` flag for detailed output
- **Result tabs** - Summary / Full Output / Errors
- **Metrics** - Pass/fail counts, duration, exit code
- **History** - Last 10 test runs with timestamps

**Use cases:**
- Run smoke tests before committing
- Debug specific failing test repeatedly
- Track test execution history

**Docs:** [Test Runner Guide](#test-runner-guide)

---

### 📜 Log Tails

**Real-time log monitoring in split-view**

- **4 log sources:**
  - **Uvicorn Server** - Backend API logs (port 8001)
  - **Test Output** - Latest pytest execution
  - **Core Trace** - ReDNACore API trace (JSONL)
  - **Diagnostics** - ExplorerDev debug logs

- **Auto-refresh** - Poll every 5s (toggleable)
- **Server status** - Shows running uvicorn PIDs/ports
- **Actions** - Copy, Clear, Refresh

**Use cases:**
- Monitor API requests during manual testing
- Correlate logs with UI actions
- Verify backend is healthy before tests

**Docs:** [Log Tails Guide](#log-tails-guide)

---

### 📁 Artifact Browser

**Search and quick-open generated files**

- **Searchable** - Filter by filename or path
- **Categorized** - User Data / Automation Logs
- **Recent files** - Last 5 opened artifacts (quick access)
- **Syntax highlighting** - JSON, JSONL, Markdown
- **Metadata** - File size, modified time, category badge

**Artifact locations:**
- `data/users/*/` - conversation.jsonl, journal.jsonl, tasks.jsonl, baseline.json
- `docs/automation_log/` - Sprint summaries, changelogs

**Use cases:**
- Inspect conversation flow after test
- Review journal entries for debugging
- Browse Sprint automation logs

**Docs:** [Artifact Browser Guide](#artifact-browser-guide)

---

### 🌐 HTTP Helpers

**API endpoint testing with JSON editor**

- **8 pre-configured endpoints:**
  - POST `/hc/say` - Send user message
  - POST `/hc/tasks/queue` - Queue task
  - GET `/hc/tasks/list` - List tasks
  - POST `/hc/tasks/tick` - Process tasks
  - GET `/hc/playbooks/list` - List playbooks
  - POST `/hc/playbooks/run` - Run playbook
  - GET `/hc/conversation/history` - Get history
  - GET `/hc/state` - Get HC state

- **Request configuration** - User ID, base URL, JSON body
- **Response viewer** - Formatted JSON / Raw text tabs
- **Quick actions** - Shortcuts to common endpoints

**Use cases:**
- Test API without Postman/curl
- Manually trigger playbooks
- Inspect Head Coach state

**Docs:** [HTTP Helpers Guide](#http-helpers-guide)

---

## Documentation

### For Users
- **[Quick Reference Card](QUICK_REFERENCE.md)** - Cheat sheet for all features
- **[User Guide](DEV_TOOLS_README.md)** - Detailed workflows and tips
- **[Demo Walkthrough](DEMO_WALKTHROUGH.md)** - 5-minute guided tour

### For Developers
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Technical spec with UX sketch
- **[Sprint Summary](../DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md)** - Pain points and ROI analysis

---

## Common Workflows

### Daily Dev Startup

```bash
# 1. Start backend
uvicorn ReDNACoreDemo.core.api:app --port 8001 &

# 2. Start ExplorerDev
./scripts/start_dev_explorer.sh

# 3. Setup monitoring
# Developer Tools → Log Tails → Uvicorn Server → Auto-refresh ON
```

### Before Committing Code

```
1. Developer Tools → Test Runner
2. Select: test_hc_v2_sprint2a_acceptance.py
3. Click: ▶️ Run All
4. Verify: All tests pass ✅
5. Check: Recent Test Runs for flakiness
```

### Debugging Test Failure

```
1. Test Runner → Run failing test
2. Check: Errors tab for traceback
3. Log Tails → Uvicorn Server → Find error logs
4. Artifact Browser → Search test user ID
5. Open: conversation.jsonl or journal.jsonl
6. HTTP Helpers → Manually reproduce API call
7. Fix code → Re-run test
```

### API Integration Testing

```
1. HTTP Helpers → Select endpoint
2. Edit: JSON request body
3. Click: Send Request
4. Log Tails → Check backend logs
5. Artifact Browser → Verify artifacts created
```

---

## Architecture

### Module Structure

```
ExplorerDev/
├── explorer_dev.py              # Main UI (integration point)
├── dev_tools_ui.py              # Developer Tools UI (4 tabs)
├── test_runner_utils.py         # pytest execution & history
├── artifact_browser_utils.py    # File scanning & search
├── log_tail_utils.py            # Log sources & server detection
├── DEV_TOOLS_README.md          # User guide
├── IMPLEMENTATION_SUMMARY.md    # Technical spec
├── QUICK_REFERENCE.md           # Cheat sheet
└── DEMO_WALKTHROUGH.md          # Demo script
```

### Data Persistence

| Data | Path | Format |
|------|------|--------|
| Test history | `data/dev_logs/test_history.jsonl` | JSONL |
| Recent artifacts | `data/dev_logs/recent_artifacts.jsonl` | JSONL |
| Last test output | `data/dev_logs/last_test_output.log` | Text |
| Diagnostics | `data/dev_logs/diagnostics.log` | Text |

### Dependencies

**No new dependencies required** - uses Python stdlib:
- `subprocess` - pytest execution
- `json`, `pathlib` - File operations
- `re` - Test function extraction
- `requests` - HTTP client (already in requirements.txt)

---

## Testing

### Smoke Test

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from ExplorerDev import test_runner_utils, artifact_browser_utils, log_tail_utils
print('✅ All imports successful')
"
```

### Integration Test

1. Start ExplorerDev
2. Navigate to Developer Tools
3. Run each tab:
   - Test Runner → Run test → Check results
   - Log Tails → Check server status → View logs
   - Artifact Browser → Search files → Open artifact
   - HTTP Helpers → Send request → View response

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Test file not found" | Run ExplorerDev from repo root |
| "Server not running" | Start: `uvicorn ReDNACoreDemo.core.api:app --port 8001` |
| "No artifacts found" | Run a test first to generate user data |
| HTTP timeout | Check backend server running, verify port 8001 |
| Empty logs | Select different source, or trigger activity first |

### Debug Mode

Set environment variable for verbose output:
```bash
STREAMLIT_LOGGER_LEVEL=debug streamlit run ExplorerDev/explorer_dev.py
```

---

## Performance

### Benchmarks (Typical)

| Operation | Duration | Notes |
|-----------|----------|-------|
| Test run | 2-30s | Depends on test file size |
| Log tail refresh | <100ms | Last 200 lines |
| Artifact scan | <1s | ~50-200 files |
| HTTP request | 100ms-10s | Depends on endpoint |

### Optimization Tips

- **Test Runner:** Run specific test instead of all tests
- **Log Tails:** Disable auto-refresh when reading logs
- **Artifact Browser:** Use search to narrow results
- **HTTP Helpers:** Use Quick Actions for common endpoints

---

## Roadmap

### Upcoming Features (Prioritized by ROI)

**High Priority (Next Sprint):**
1. ✨ **Log line navigation** - Click traceback → jump to file:line (2h)
2. 📊 **Test history charts** - Pass/fail trends, flaky test detection (1.5h)
3. 🔄 **Artifact diff viewer** - Side-by-side comparison (2h)

**Medium Priority (Sprint 2):**
4. 🌐 **WebSocket log streaming** - Real-time logs without polling (3h)
5. 📈 **Test coverage** - Display coverage % in results (2h)
6. 📝 **Request templates** - Save/load HTTP request collections (1.5h)
7. 🎛️ **Server control** - Start/stop uvicorn from UI (2h)

**Nice to Have (Backlog):**
8. 🔍 **Artifact filters** - Date range, size, type (1h)
9. 🧪 **Test parameterization** - Run specific param combos (2h)
10. 📤 **CI report export** - JUnit XML from history (1h)

Full details: [Implementation Summary - Punch List](IMPLEMENTATION_SUMMARY.md#10-item-follow-up-punch-list)

---

## Contributing

### Adding a New Feature

1. Create utility module in `ExplorerDev/` (e.g., `my_feature_utils.py`)
2. Add UI component in `dev_tools_ui.py` or create `my_feature_ui.py`
3. Import in `explorer_dev.py` if adding new tab
4. Update this README and User Guide
5. Submit PR with tests

### Adding a Log Source

Edit `log_tail_utils.py`:
```python
LOG_SOURCES = {
    # ... existing sources
    "my_log": LogSource(
        name="My Log",
        description="Description of what this log shows",
        file_path=REPO_ROOT / "path" / "to" / "log.txt",
    ),
}
```

### Adding an HTTP Endpoint

Edit `dev_tools_ui.py` in `_render_http_helpers()`:
```python
endpoints = {
    # ... existing endpoints
    "/my/endpoint": {
        "method": "POST",
        "description": "My custom endpoint"
    },
}

# Add template
templates = {
    "/my/endpoint": '{"key": "value"}',
}
```

---

## Success Metrics

### Adoption (2 weeks post-launch)

- 80%+ of dev team uses Test Runner daily
- 50%+ reduction in "How do I run this test?" Slack questions

### Efficiency

- 5-10 min/day saved per developer (vs terminal switching)
- 30-60s saved per debug cycle (log navigation)

### Quality

- 20%+ increase in test runs before commit
- Earlier detection of flaky tests

### Tracking

Monitor these files:
- `data/dev_logs/test_history.jsonl` - Test run frequency
- `data/dev_logs/recent_artifacts.jsonl` - Artifact browser usage

Survey team after 2 weeks for qualitative feedback.

---

## FAQ

**Q: Can I use Developer Tools with other projects?**
A: Yes, but test runner expects `test_*acceptance*.py` pattern. Customize in `test_runner_utils.py`.

**Q: Does this work on Windows?**
A: Partially tested. Server detection (lsof/ps) may need Windows-specific implementation.

**Q: Can I add custom log sources?**
A: Yes, edit `LOG_SOURCES` in `log_tail_utils.py`. See [Contributing](#contributing).

**Q: How do I export test results?**
A: Currently manual (copy from Output tab). Export feature planned (punch list #10).

**Q: Can I run tests in parallel?**
A: Not yet. Test runner executes sequentially. Parallel execution planned for v2.0.

---

## Support

- **User Guide:** [DEV_TOOLS_README.md](DEV_TOOLS_README.md)
- **Quick Reference:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Demo:** [DEMO_WALKTHROUGH.md](DEMO_WALKTHROUGH.md)
- **Issues:** Create GitHub issue with label `dev-tools`
- **Questions:** Ping @david in Slack

---

**Last updated:** 2025-10-04
**Version:** 1.0
**Maintainer:** @david
