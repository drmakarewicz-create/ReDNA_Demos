# Developer Tools - Quick Start Guide

The **Developer Tools** section in ExplorerDev consolidates common development workflows into a single UI. This replaces manual terminal operations with one-click actions.

## Location

Open ExplorerDev and navigate to **Developer Tools** in the sidebar.

```bash
# Start ExplorerDev
streamlit run ExplorerDev/explorer_dev.py
```

Then select **"Developer Tools"** from the sidebar navigation.

## Features Overview

### 1. 🧪 Test Runner

**Purpose:** Run acceptance tests without switching to terminal.

**How to use:**

1. Select a test file from the dropdown (e.g., `test_hc_v2_sprint1c_acceptance.py`)
2. Optionally select a specific test function, or leave as "[All Tests]"
3. Click **▶️ Run All** or **▶️ Run Selected**
4. View results in tabs:
   - **📊 Summary**: Pass/fail counts and key output
   - **📝 Full Output**: Complete pytest output
   - **⚠️ Errors**: Stderr and error messages

**Recent Test Runs** section shows history of the last 10 test executions with pass/fail status and timing.

**Use cases:**
- Quick smoke test after code changes
- Run specific failing test repeatedly during debugging
- Verify acceptance criteria before committing

---

### 2. 📜 Log Tails

**Purpose:** Monitor server logs and test output in real-time.

**Available log sources:**

- **Uvicorn Server** (port 8001): Backend API logs
- **Test Output**: Latest pytest execution
- **Core Trace**: ReDNACore API trace (JSONL)
- **Diagnostics**: ExplorerDev diagnostic logs

**How to use:**

1. Select a log source from dropdown
2. Enable **Auto-refresh (5s)** for live tailing
3. Use **🔄 Refresh** to manually update
4. **📋 Copy** displays content for browser copy
5. **🗑️ Clear View** empties the display

**Server Status panel** shows running uvicorn processes with PID and port.

**Use cases:**
- Monitor API requests during manual testing
- Watch test output as it streams
- Debug API errors by correlating logs with UI actions
- Verify server is running before tests

---

### 3. 📁 Artifact Browser

**Purpose:** Quick navigation to generated JSON/JSONL artifacts.

**Artifact categories:**

- **User Data**: `data/users/*/journal.jsonl`, `conversation.jsonl`, `tasks.jsonl`, etc.
- **Automation Logs**: `docs/automation_log/*.md`, `*.jsonl`

**How to use:**

1. Use **Search** to filter by filename or path
2. Filter by **Category** (All / User Data / Automation Logs)
3. **Recent Artifacts** quick-access buttons show last 5 opened files
4. Click any artifact to view with syntax highlighting

**File viewer** shows:
- Full path
- File size and last modified time
- Content with JSON/JSONL/Markdown syntax highlighting
- Auto-truncates to first 500 lines for large files

**Use cases:**
- Inspect conversation history after test run
- Review journal entries for specific user
- Browse automation logs from Sprint summaries
- Quick diff between user states

---

### 4. 🌐 HTTP Helpers

**Purpose:** Send HTTP requests to backend endpoints without Postman/curl.

**Pre-configured endpoints:**

- `POST /hc/say` - Send user message
- `POST /hc/tasks/queue` - Queue a task
- `GET /hc/tasks/list` - List tasks
- `POST /hc/tasks/tick` - Process tasks
- `GET /hc/playbooks/list` - List playbooks
- `POST /hc/playbooks/run` - Run playbook
- `GET /hc/conversation/history` - Get history
- `GET /hc/state` - Get HC state

**How to use:**

1. Select endpoint from dropdown
2. Enter **User ID** (default: "bstest")
3. Adjust **Base URL** if needed (default: `http://localhost:8001`)
4. For POST requests, edit JSON body in text area
5. Click **🚀 Send {METHOD} Request**
6. View response in tabs:
   - **📄 Formatted**: Pretty-printed JSON
   - **📝 Raw**: Raw response text

**Quick Actions** buttons provide shortcuts to common endpoints.

**Use cases:**
- Test API endpoints during development
- Manually trigger playbooks for debugging
- Inspect Head Coach state before/after operations
- Verify API responses match expectations

---

## Common Workflows

### Daily Dev Flow

**Morning startup:**

1. Open **Developer Tools → Log Tails**
2. Select "Uvicorn Server" and enable Auto-refresh
3. Verify server is running in **Server Status** panel
4. If not running, start via terminal: `uvicorn ReDNACoreDemo.core.api:app --port 8001`

**Before committing:**

1. Open **Developer Tools → Test Runner**
2. Select `test_hc_v2_sprint2a_acceptance.py` (or current sprint)
3. Click **▶️ Run All**
4. Verify all tests pass
5. Review **Recent Test Runs** for any flakiness

**After test failure:**

1. Check **Log Tails → Test Output** for pytest traceback
2. Open **Artifact Browser** and search for failing user's data (e.g., `test_sprint2a_`)
3. Inspect `conversation.jsonl` or `tasks.jsonl` to see what went wrong
4. Use **HTTP Helpers** to manually reproduce the failing API call
5. Fix code, then re-run specific test function

### Debugging API Routes

1. Open **Developer Tools → HTTP Helpers**
2. Select endpoint (e.g., `/hc/say`)
3. Enter test user ID
4. Edit request body JSON
5. Send request and inspect response
6. Switch to **Log Tails → Uvicorn Server** to see backend logs
7. If error, check **Log Tails → Core Trace** for full request/response cycle

### Artifact Inspection

1. Open **Developer Tools → Artifact Browser**
2. Search for user ID (e.g., "bstest")
3. Click `data/users/bstest/conversation.jsonl`
4. Review conversation flow with syntax highlighting
5. Click **Recent Artifacts** to jump between related files
6. Compare `journal.jsonl` to verify events were logged

---

## Tips & Tricks

### Test Runner

- Use **Verbose (-v)** checkbox for detailed pytest output
- **Recent Test Runs** tracks timing - use to spot performance regressions
- Test output is auto-saved to `data/dev_logs/last_test_output.log` for log viewer

### Log Tails

- **Auto-refresh** polls every 5 seconds - disable when you need stable view
- **Server Status** panel uses `lsof` to detect running processes
- On macOS, live log capture from PID is limited - check terminal for full logs

### Artifact Browser

- **Recent Artifacts** tracks last 20 opened files in `data/dev_logs/recent_artifacts.jsonl`
- Search is case-insensitive and matches both filename and path
- Files are auto-truncated to 500 lines to prevent UI lag

### HTTP Helpers

- Request templates are pre-filled based on endpoint
- Response JSON is auto-formatted for readability
- **Quick Actions** buttons auto-select common endpoints

---

## Troubleshooting

### "Test file not found"

- Ensure you're running ExplorerDev from repo root
- Test files must match pattern `test_*acceptance*.py` in repo root

### "Server not running" in Log Tails

- Start uvicorn manually: `uvicorn ReDNACoreDemo.core.api:app --port 8001`
- Check **Server Status** panel for running processes

### "File not found" in Artifact Browser

- Artifacts are generated during test runs or API calls
- Run a test first to populate `data/users/*`
- Check that user ID exists in `data/users/` directory

### HTTP request timeout

- Verify backend server is running (check Log Tails → Server Status)
- Increase timeout if needed (currently 10s)
- Check `CORE_API_URL` env var matches **Base URL**

---

## File Locations

- Test history: `data/dev_logs/test_history.jsonl`
- Recent artifacts: `data/dev_logs/recent_artifacts.jsonl`
- Last test output: `data/dev_logs/last_test_output.log`
- Diagnostics log: `data/dev_logs/diagnostics.log`
- Core trace: `ReDNACoreDemo/data/dev_logs/trace_core.jsonl`

---

## Integration with Existing Tools

Developer Tools **complements** existing ExplorerDev features:

- **Diagnostics → Loop Test**: Full data-cycle integration test
- **Diagnostics → Audit Viewer**: Historical log analysis
- **Developer Tools → Test Runner**: Fast acceptance test execution

Use **Diagnostics** for deep system analysis, **Developer Tools** for rapid iteration.

---

## Future Enhancements

See **Follow-Up Punch List** (below) for planned improvements:

1. Clickable log line navigation (jump to file:line)
2. Test coverage reporting
3. Diff viewer for artifacts (before/after comparison)
4. WebSocket live log streaming
5. Test result history charts

---

For questions or feature requests, see main repo README.
