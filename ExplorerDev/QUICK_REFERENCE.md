# Developer Tools - Quick Reference Card

**Access:** ExplorerDev → Sidebar → "Developer Tools"

---

## 🧪 Test Runner

**Purpose:** Run acceptance tests without terminal

| Action | Steps |
|--------|-------|
| Run all tests in file | Select file → **▶️ Run All** |
| Run specific test | Select file → Select function → **▶️ Run Selected** |
| View results | Check Summary/Output/Errors tabs |
| See history | Scroll to "Recent Test Runs" |

**Tip:** Enable "Verbose (-v)" for detailed output

---

## 📜 Log Tails

**Purpose:** Monitor logs in real-time

| Log Source | What it shows |
|------------|---------------|
| Uvicorn Server | Backend API requests (port 8001) |
| Test Output | Latest pytest execution |
| Core Trace | ReDNACore API trace (JSONL) |
| Diagnostics | ExplorerDev debug logs |

**Actions:**
- ☑️ **Auto-refresh** - Poll every 5s
- 🔄 **Refresh** - Manual update
- 📋 **Copy** - Display for copy/paste
- 🗑️ **Clear View** - Empty display

**Tip:** Check "Server Status" panel to verify uvicorn is running

---

## 📁 Artifact Browser

**Purpose:** Quick access to generated files

**Search locations:**
- `data/users/*/` - User data (conversation.jsonl, journal.jsonl, tasks.jsonl)
- `docs/automation_log/` - Sprint summaries, changelogs

**Actions:**
1. **Search** - Filter by filename/path
2. **Category** - User Data / Automation Logs / All
3. **Recent Artifacts** - Last 5 opened files
4. **Click file** - View with syntax highlighting

**Common files:**
- `conversation.jsonl` - User↔️Assistant messages
- `journal.jsonl` - Timestamped events
- `tasks.jsonl` - Queued tasks
- `baseline.json` - User trait snapshot
- `hc-v2-sprint*.md` - Sprint summaries

---

## 🌐 HTTP Helpers

**Purpose:** Test backend endpoints without curl/Postman

**Pre-configured endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/hc/say` | POST | Send user message |
| `/hc/tasks/queue` | POST | Queue a task |
| `/hc/tasks/list` | GET | List tasks |
| `/hc/tasks/tick` | POST | Process tasks |
| `/hc/playbooks/list` | GET | List playbooks |
| `/hc/playbooks/run` | POST | Run playbook |
| `/hc/conversation/history` | GET | Get chat history |
| `/hc/state` | GET | Get HC state |

**Steps:**
1. Select endpoint
2. Enter User ID (default: "bstest")
3. Edit JSON body (POST only)
4. Click **🚀 Send Request**
5. View Formatted/Raw response

**Quick Actions:**
- 📊 Get HC State
- 💬 Say Hello
- 📋 List Tasks

---

## ⚡ Common Workflows

### Daily Startup
```bash
./scripts/start_dev_explorer.sh
# Navigate to: Developer Tools → Log Tails
# Select: Uvicorn Server
# Enable: Auto-refresh
```

### Before Commit
```
Developer Tools → Test Runner
Select: test_hc_v2_sprint2a_acceptance.py
Click: ▶️ Run All
Verify: All PASSED ✅
```

### Debug API Issue
```
1. HTTP Helpers → POST /hc/say → Send request
2. Log Tails → Uvicorn Server → Check logs
3. Artifact Browser → Search user ID → Open conversation.jsonl
```

### Inspect Test Results
```
1. Test Runner → Run test
2. Artifact Browser → Search "test_sprint*"
3. Open conversation.jsonl or journal.jsonl
4. Compare with expected behavior
```

---

## 🔧 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+R` | Refresh Streamlit app |
| `Ctrl+C` | Stop server (in terminal) |
| `Ctrl+F` | Find in browser (for log search) |

---

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Test file not found" | Run from repo root, check file exists |
| "Server not running" | Start: `uvicorn ReDNACoreDemo.core.api:app --port 8001` |
| "File not found" in browser | Run a test first to generate artifacts |
| HTTP timeout | Check server running, increase timeout if needed |
| Empty log | Select different source, or run test/API call first |

---

## 📊 File Tracking

**Logs persisted to:**
- Test history: `data/dev_logs/test_history.jsonl`
- Recent artifacts: `data/dev_logs/recent_artifacts.jsonl`
- Last test output: `data/dev_logs/last_test_output.log`

**Max items:**
- Test history: 50 runs
- Recent artifacts: 20 files

---

## 🎯 ROI Metrics

**Time saved per day (estimated):**
- Test Runner: 5-10 min (no terminal switching)
- Log Tails: 2-5 min (centralized monitoring)
- Artifact Browser: 2-5 min (instant file access)
- HTTP Helpers: 1-3 min (no Postman/curl setup)

**Total:** 10-23 min/day per developer

---

## 📚 Full Docs

- User Guide: [DEV_TOOLS_README.md](DEV_TOOLS_README.md)
- Technical Spec: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Sprint Summary: [../DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md](../DEVELOPER_EXPLORER_UX_IMPROVEMENTS.md)

---

**Version:** 1.0 (2025-10-04)
