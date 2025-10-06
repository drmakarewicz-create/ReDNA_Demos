# Developer Tools - Demo Walkthrough

**Goal:** Demonstrate all 4 Developer Tools features in 5 minutes

---

## Setup (30 seconds)

```bash
# 1. Start backend (if not already running)
uvicorn ReDNACoreDemo.core.api:app --port 8001 &

# 2. Start Developer Explorer
./scripts/start_dev_explorer.sh

# 3. Navigate in browser to: http://localhost:8502
# 4. Click "Developer Tools" in sidebar
```

---

## Demo 1: Test Runner (90 seconds)

**Scenario:** Run acceptance tests before committing code

### Steps:

1. **Click "🧪 Test Runner" tab**

2. **Select test file:**
   ```
   Dropdown: test_hc_v2_sprint1c_acceptance.py
   ```

3. **Enable verbose mode:**
   ```
   ☑️ Verbose (-v)
   ```

4. **Run all tests:**
   ```
   Click: ▶️ Run All
   ```

5. **View results:**
   ```
   Status: ✅ PASSED
   Passed: 5
   Failed: 0
   Duration: 12.3s
   ```

6. **Check summary:**
   ```
   📊 Summary tab shows:
   - test_1_conversation_ui_flow... PASSED [12%]
   - test_2_playbook_button... PASSED [25%]
   - test_3_task_priorities... PASSED [37%]
   - test_4_ucnrr_toggle... PASSED [50%]
   - test_5_end_to_end_flow... PASSED [100%]
   ```

7. **Review history:**
   ```
   Scroll down to "Recent Test Runs"
   See: test_hc_v2_sprint1c... 2025-10-04T10:30 ✅
   ```

**Outcome:** ✅ All tests pass, safe to commit

---

## Demo 2: Log Tails (60 seconds)

**Scenario:** Monitor backend API during manual testing

### Steps:

1. **Click "📜 Log Tails" tab**

2. **Select log source:**
   ```
   Dropdown: Uvicorn Server
   ```

3. **Enable auto-refresh:**
   ```
   ☑️ Auto-refresh (5s)
   ```

4. **Check server status:**
   ```
   Server Status panel shows:
   ✅ Uvicorn running on port 8001 (PID: 15013)
   ```

5. **View live logs:**
   ```
   INFO: 127.0.0.1:52341 - "POST /hc/say HTTP/1.1" 200 OK
   INFO: Conversation logged for user: bstest
   INFO: LLM reply generated in 1.2s
   ```

6. **Switch to test output:**
   ```
   Dropdown: Test Output
   See: Latest pytest execution from Demo 1
   ```

7. **Copy logs:**
   ```
   Click: 📋 Copy
   Content displayed for browser copy
   ```

**Outcome:** ✅ Real-time visibility into backend behavior

---

## Demo 3: Artifact Browser (90 seconds)

**Scenario:** Inspect user conversation after test run

### Steps:

1. **Click "📁 Artifact Browser" tab**

2. **Search for test user:**
   ```
   Search box: "test_sprint1c"
   ```

3. **View filtered results:**
   ```
   Found 8 artifacts
   - data/users/test_sprint1c_1728036420/conversation.jsonl
   - data/users/test_sprint1c_1728036420/journal.jsonl
   - data/users/test_sprint1c_1728036420/tasks.jsonl
   ```

4. **Open conversation:**
   ```
   Click: data/users/test_sprint1c_1728036420/conversation.jsonl
   ```

5. **View content:**
   ```json
   {"role": "user", "content": "What should I do next?", "ts": 1728036420}
   {"role": "assistant", "content": "Based on your goals...", "ts": 1728036421}
   ```

6. **Browse automation logs:**
   ```
   Category dropdown: Automation Logs
   Click: docs/automation_log/hc-v2-sprint1c.md
   ```

7. **Use recent artifacts:**
   ```
   Click: [conversation.jsonl] in Recent Artifacts
   Jump back to previously opened file
   ```

**Outcome:** ✅ Instant access to user data and logs

---

## Demo 4: HTTP Helpers (60 seconds)

**Scenario:** Test API endpoint manually

### Steps:

1. **Click "🌐 HTTP Helpers" tab**

2. **Select endpoint:**
   ```
   Dropdown: POST /hc/say - Send user message
   ```

3. **Configure request:**
   ```
   User ID: bstest
   Base URL: http://localhost:8001 (default)
   ```

4. **Edit JSON body:**
   ```json
   {
     "message": "Show me my task list",
     "role": "user"
   }
   ```

5. **Send request:**
   ```
   Click: 🚀 Send POST Request
   ```

6. **View response:**
   ```json
   {
     "logged": true,
     "ts": 1728036500,
     "reply_logged": true
   }
   ```

7. **Switch to raw view:**
   ```
   Click: Raw tab
   See raw JSON response
   ```

8. **Use quick action:**
   ```
   Click: 📊 Get HC State
   Auto-selects /hc/state endpoint
   Click: Send → View state
   ```

**Outcome:** ✅ API tested without Postman/curl

---

## Full Workflow Demo (3 minutes)

**Scenario:** Debug failing test end-to-end

### Problem:
```
test_5_end_to_end_flow is failing intermittently
Need to understand what's happening
```

### Solution Steps:

1. **Start monitoring (Log Tails):**
   ```
   Tab: Log Tails
   Source: Uvicorn Server
   Auto-refresh: ON
   ```

2. **Run failing test (Test Runner):**
   ```
   Tab: Test Runner
   File: test_hc_v2_sprint1c_acceptance.py
   Function: test_5_end_to_end_flow
   Click: ▶️ Run Selected
   ```

3. **Check result:**
   ```
   Status: ❌ FAILED
   Errors tab shows: AssertionError: Expected 3 tasks, got 2
   ```

4. **Inspect logs (Log Tails):**
   ```
   View Uvicorn logs during test:
   ERROR: Task queue failed for user: test_sprint1c_*
   ERROR: Priority calculation returned None
   ```

5. **Check user artifacts (Artifact Browser):**
   ```
   Search: test_sprint1c_
   Open: tasks.jsonl
   See: Only 2 tasks queued (missing 1)
   ```

6. **Manual API test (HTTP Helpers):**
   ```
   Endpoint: POST /hc/tasks/queue
   User ID: bstest
   Body: {"description": "Test task", "priority": 5}
   Send → Check if priority calculation works
   ```

7. **Identify root cause:**
   ```
   Priority calculation returns None when user has no baseline
   Test user needs baseline.json seeded
   ```

8. **Fix & re-run:**
   ```
   Fix code → Test Runner → Run Selected → ✅ PASSED
   ```

**Outcome:** ✅ Bug identified and fixed in 3 minutes (vs 10-15 min without tools)

---

## Pro Tips

### Test Runner
- Use **Verbose mode** for debugging
- Check **Recent Test Runs** to spot flaky tests (alternating ✅/❌)
- Run specific test repeatedly to confirm fix

### Log Tails
- **Pause auto-refresh** when you need to read logs carefully
- Use browser **Ctrl+F** to search within logs
- Switch between sources to correlate (Uvicorn ↔️ Core Trace)

### Artifact Browser
- Use **Recent Artifacts** for quick file switching
- **Search is fuzzy** - partial matches work (e.g., "conv" finds conversation.jsonl)
- Filter by **Category** to reduce noise

### HTTP Helpers
- **Quick Actions** pre-fill common requests
- **Copy request body** from Raw tab for CI scripts
- Test with different **User IDs** to compare behavior

---

## Next Steps

After this demo:

1. **Try it yourself** with your own test files
2. **Bookmark** the Quick Reference card
3. **Suggest improvements** based on your workflow
4. **Check punch list** for upcoming features

---

## Feedback

What worked well?
- [ ] Test Runner saves time
- [ ] Log Tails are useful for debugging
- [ ] Artifact Browser helps find files quickly
- [ ] HTTP Helpers replace Postman/curl

What needs improvement?
- [ ] Missing feature: _____________
- [ ] UI issue: _____________
- [ ] Performance: _____________
- [ ] Documentation: _____________

**Submit feedback:** Create GitHub issue or ping @david

---

**Demo script version:** 1.0 (2025-10-04)
