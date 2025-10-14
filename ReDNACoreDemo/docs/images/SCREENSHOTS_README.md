# Narrator Mode Screenshots

## Required Screenshots

To complete the documentation, please capture the following screenshots:

### 1. Narrator Timeline Overview (`narrator_timeline_overview.png`)

**How to capture:**
1. Start DevX: `cd ReDNACoreDemo/devx && npm run dev`
2. Open: http://localhost:8100
3. Navigate to: 🗣 Narrator
4. Enter User ID: TEST
5. Click "Refresh" to load traces
6. Capture full page view showing:
   - Navigation bar with "🗣 Narrator" highlighted
   - Controls panel (User ID, filters, buttons)
   - Statistics summary (4 cards)
   - Timeline with multiple session groups
   - Several trace entries visible

**Dimensions:** ~1400x900px

---

### 2. Narrator Entry Detail (`narrator_entry_detail.png`)

**How to capture:**
1. From the timeline view above
2. Zoom in or crop to show a single trace entry card
3. Ensure the following are visible:
   - Timestamp + context version chip
   - Decision heading (bold)
   - Confidence badge (colored)
   - Impact badge
   - Reasoning list (bullet points)
   - Metadata chips
   - "Open Context" button
   - Duration indicator

**Dimensions:** ~800x500px

---

## Screenshot Guidelines

- **Resolution:** High DPI (2x for Retina displays)
- **Format:** PNG with transparency where applicable
- **Naming:** Exactly as specified above (lowercase, underscores)
- **Quality:** Clear text, no compression artifacts
- **Content:** Use TEST user with realistic trace data

---

## Alternative: DevX Running State

If you cannot capture screenshots, you can verify the UI by:

1. Starting services:
   ```bash
   # Terminal 1: Core API
   python3 -m uvicorn ReDNACoreDemo.core.api:app --reload --port 8015

   # Terminal 2: DevX
   cd ReDNACoreDemo/devx && npm run dev
   ```

2. Generating sample traces:
   ```bash
   # Generate a few coach switches
   curl -X POST http://localhost:8015/users/TEST/coach-mode \
     -H "Content-Type: application/json" \
     -d '{"target_mode":"career_coach"}'

   curl -X POST http://localhost:8015/users/TEST/coach-mode \
     -H "Content-Type: application/json" \
     -d '{"target_mode":"relationship_coach"}'
   ```

3. Opening DevX at http://localhost:8100
4. Clicking 🗣 Narrator
5. Reviewing the timeline

---

## Placeholder Status

Currently, the documentation references these screenshots, but they are placeholders until captured.

The system is fully functional without screenshots — they are for documentation enhancement only.
