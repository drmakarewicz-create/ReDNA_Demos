# CP++ ↔ Developer Explorer Integration

**Added:** 2025-10-04
**Feature:** Quick-launch button for Developer Explorer in CP++ sidebar

---

## What's New

Added a convenient **"🚀 Open Developer Explorer"** button to the CP++ (Control Panel Plus Plus) sidebar that:

1. **Always visible** - No need to launch services first
2. **Smart URL detection** - Uses configured port or defaults to 8502
3. **Status indicator** - Shows if Dev Explorer is running (🟢 green = running, ⚪ white = not detected)
4. **One-click open** - Opens Dev Explorer in new browser tab

---

## Location

The button appears in the **CP++ left sidebar**, right below the title and before the main controls:

```
┌─────────────────────────┐
│ Control Panel Plus Plus │
│ Experimental orchestrator│
├─────────────────────────┤
│ 🛠️ Quick Launch         │
│                         │
│ [🚀 Open Dev Explorer] 🟢│
│ ✅ Running on port 8502 │
├─────────────────────────┤
│ ☐ Force root .venv      │
│ ...                     │
└─────────────────────────┘
```

---

## How It Works

### 1. Port Detection

The button automatically detects the correct port:

1. **Service URL** - If Dev Explorer is managed by CP++ (via environment), uses that URL
2. **Environment variable** - Checks `dev_explorer_port` in CP++ environment
3. **Default fallback** - Uses port `8502` if nothing configured

### 2. Status Check

On each page load, CP++ checks if Dev Explorer is running:

- **HTTP HEAD request** to Dev Explorer URL (0.5s timeout)
- **Green dot (🟢)** = Service is responding
- **White dot (⚪)** = Service not detected

### 3. Open Action

Clicking the button:

1. Opens Dev Explorer URL in **new browser tab** (using `webbrowser` module)
2. Shows success message briefly
3. Does **not** start Dev Explorer (just opens the URL)

---

## Usage

### From CP++

1. **Start CP++:**
   ```bash
   streamlit run control_panel_plus_plus.py
   ```

2. **In the sidebar**, look for "🛠️ Quick Launch" section

3. **Click "🚀 Open Developer Explorer"**
   - If Dev Explorer is running → Opens in new tab ✅
   - If not running → Opens URL anyway (will show connection error)

### With Dev Explorer Already Running

If you started Dev Explorer separately:

```bash
streamlit run ExplorerDev/explorer_dev.py --server.port=8502
```

CP++ will:
- Detect it's running (🟢 green status)
- Show "✅ Running on port 8502"
- Open correct URL when clicked

### Custom Port Configuration

To use a different port for Dev Explorer:

1. Go to **CP++ → Environment & Ports** tab
2. Set `dev_explorer_port` to your desired port (e.g., `8503`)
3. Save environment
4. Quick Launch button will use that port

---

## Visual Reference

### When Dev Explorer is Running

```
🛠️ Quick Launch

[🚀 Open Developer Explorer] 🟢

✅ Running on port 8502
```

### When Dev Explorer is NOT Running

```
🛠️ Quick Launch

[🚀 Open Developer Explorer] ⚪

⚠️ Not detected (port 8502)
```

---

## Implementation Details

**File:** [control_panel_plus_plus.py](control_panel_plus_plus.py)
**Lines:** ~3546-3584 (in `main()` function)

**Code flow:**

1. Get environment variables
2. Determine Dev Explorer port (env → default 8502)
3. Build URL from port
4. Check if service URL exists (from CP++ service management)
5. Check if URL is reachable (HTTP HEAD)
6. Render button + status indicator
7. On click → Open in new tab

**Dependencies:**
- `webbrowser` - Standard library (open browser tabs)
- `requests` - Already used in CP++ (HTTP checks)
- No new dependencies

---

## Benefits

### Before (Without Button)

❌ **Multi-step process:**
1. Open terminal
2. Type: `streamlit run ExplorerDev/explorer_dev.py`
3. Wait for startup
4. Copy URL from terminal
5. Paste into browser

### After (With Button)

✅ **One-click process:**
1. Click "🚀 Open Developer Explorer" in CP++
2. Done!

**Time saved:** 20-30 seconds per launch

---

## Troubleshooting

### Button shows ⚪ (not detected) but Dev Explorer is running

**Possible causes:**
1. Dev Explorer on different port → Configure `dev_explorer_port` in CP++
2. Slow startup → Wait a few seconds and refresh CP++
3. Firewall blocking → Check localhost:8502 is accessible

**Solution:**
```bash
# Check what's running on port 8502
lsof -i :8502

# If nothing, start Dev Explorer
streamlit run ExplorerDev/explorer_dev.py --server.port=8502
```

### Button opens wrong URL

**Cause:** Port mismatch between CP++ config and actual Dev Explorer port

**Solution:**
1. Check Dev Explorer actual port in terminal output
2. Update `dev_explorer_port` in CP++ → Environment & Ports tab
3. Refresh CP++

### Button doesn't open browser

**Cause:** `webbrowser` module can't find default browser

**Solution:**
1. Manually open: `http://localhost:8502`
2. Or set `BROWSER` environment variable:
   ```bash
   export BROWSER=chrome  # or firefox, safari, etc.
   streamlit run control_panel_plus_plus.py
   ```

---

## Related Documentation

- **Developer Tools:** [ExplorerDev/README_DEV_TOOLS.md](ExplorerDev/README_DEV_TOOLS.md)
- **Quick Reference:** [ExplorerDev/QUICK_REFERENCE.md](ExplorerDev/QUICK_REFERENCE.md)
- **CP++ Main:** [control_panel_plus_plus.py](control_panel_plus_plus.py)

---

## Future Enhancements

Possible improvements (not yet implemented):

1. **Auto-start Dev Explorer** - Button could start Dev Explorer if not running
2. **Recent ports history** - Remember last used port
3. **Multiple instances** - Dropdown to select from multiple running Dev Explorers
4. **Direct navigation** - Button could open specific Dev Tools tab (e.g., Test Runner)

---

## Changelog

### 2025-10-04 - Initial Implementation
- ✅ Added "🚀 Open Developer Explorer" button to sidebar
- ✅ Smart port detection (env → default 8502)
- ✅ Status indicator (🟢 running / ⚪ not detected)
- ✅ One-click open in new tab
- ✅ Integration with CP++ service management

---

**Enjoy faster access to Developer Tools!** 🚀
