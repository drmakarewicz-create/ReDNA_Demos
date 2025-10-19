# User Right Pane Overrides — Quick Reference

**Per-User Panel Customization System**

---

## 📍 File Location

```
data/users/<user_id>/ui/right_pane_layout.json
```

---

## 📐 Schema (v2)

```json
{
  "version": 2,
  "cards": ["catalog", "life_os", "reco", "persona_tools"],
  "overrides": {
    "<persona_key>": {
      "order": ["panel_id_1", "panel_id_2"],
      "visible": {
        "panel_id": true,
        "life_os": false
      },
      "lifeOS": "full" | "relationship" | "hidden"
    }
  }
}
```

---

## 🎛️ Override Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `order` | `string[]` | Panel IDs in display order (top to bottom) | `["photo", "catalog"]` |
| `visible` | `Record<string, boolean>` | Panel visibility map | `{"life_os": false}` |
| `lifeOS` | `LifeOSVariant` | Life OS display mode | `"hidden"` |

---

## 🔧 Panel IDs by Persona

### Photo Coach
- `photo` — Photo upload & recent imports panel

### PaDNA Coach
- `padna` — Portrait renderer panel

### Rendering
- `avatar` — Avatar render panel
- `portrait` — Portrait render card

### Career Coach
- `career_snapshot` — Career snapshot card
- `skill_map` — Skill curiosity map

### Personality Test Coach
- `personality_snapshot` — Personality snapshot card
- `personality_map` — Personality map visualization

### ChatDNA Coach
- `chatdna_snapshot` — ChatDNA snapshot card
- `language_style` — Language style panel

---

## 💡 Common Use Cases

### 1. Hide Life OS for Specialized Coach

```json
{
  "version": 2,
  "overrides": {
    "photo_coach": {
      "visible": {"life_os": false}
    }
  }
}
```

### 2. Change Panel Order

```json
{
  "version": 2,
  "overrides": {
    "career_coach": {
      "order": ["skill_map", "career_snapshot"]
    }
  }
}
```

### 3. Change Life OS Variant

```json
{
  "version": 2,
  "overrides": {
    "head_coach": {
      "lifeOS": "full"
    },
    "relationship_coach": {
      "lifeOS": "relationship"
    }
  }
}
```

### 4. Hide Specific Panels

```json
{
  "version": 2,
  "overrides": {
    "career_coach": {
      "visible": {
        "career_snapshot": true,
        "skill_map": false
      }
    }
  }
}
```

---

## 🌐 API Endpoints

### Get Layout
```bash
GET /ui/config/{user_id}/right_pane_layout
```

**Response**: Layout JSON or 404 if not configured

### Save Layout
```bash
POST /ui/config/{user_id}/right_pane_layout
Content-Type: application/json

{
  "version": 2,
  "overrides": { ... }
}
```

**Response**: Saved layout JSON

### Reset to Default
```bash
DELETE /ui/config/{user_id}/right_pane_layout
```

**Response**: `{"ok": true, "message": "Layout reset to default"}`

---

## 🖥️ CLI Examples

### Create Custom Layout
```bash
curl -X POST http://localhost:8000/ui/config/TEST/right_pane_layout \
  -H "Content-Type: application/json" \
  -d '{
    "version": 2,
    "overrides": {
      "photo_coach": {
        "visible": {"life_os": false, "photo": true}
      }
    }
  }'
```

### Fetch Layout
```bash
curl http://localhost:8000/ui/config/TEST/right_pane_layout
```

### Reset Layout
```bash
curl -X DELETE http://localhost:8000/ui/config/TEST/right_pane_layout
```

---

## 🔍 Validation Rules

1. **`version`**: Must be `2` (future-proofing)
2. **`order`**: Array of valid panel IDs for that persona
3. **`visible`**: Boolean values only
4. **`lifeOS`**: Must be `"full"`, `"relationship"`, or `"hidden"`

---

## ⚠️ Fallback Behavior

- **No layout file**: Uses base config (default behavior)
- **Invalid JSON**: Logs warning, uses base config
- **Missing fields**: Partial override applied, rest uses base config
- **Unknown panel IDs**: Ignored silently

---

## 📊 Audit Trail

Layout changes are logged to:
```
data/audit/agent_activity.jsonl
```

**Event Type**: `ui_right_pane_config_updated`

**Example Entry**:
```json
{
  "timestamp": "2025-10-11T20:00:00.000Z",
  "user_id": "TEST",
  "event_type": "ui_right_pane_config_updated",
  "source": "user_preferences",
  "metadata": {
    "version": 2,
    "has_overrides": true
  }
}
```

---

## 🚀 Quick Start

1. **Create a layout file**:
   ```bash
   mkdir -p data/users/TEST/ui
   nano data/users/TEST/ui/right_pane_layout.json
   ```

2. **Add basic override**:
   ```json
   {
     "version": 2,
     "overrides": {
       "photo_coach": {
         "visible": {"life_os": false}
       }
     }
   }
   ```

3. **Reload UI**:
   - Refresh browser
   - Layout auto-loads on page load

4. **Verify**:
   - Switch to Photo Coach
   - Life OS should be hidden

---

## 💾 Backup & Restore

### Backup Layout
```bash
cp data/users/TEST/ui/right_pane_layout.json \
   data/users/TEST/ui/right_pane_layout.backup.json
```

### Restore Layout
```bash
cp data/users/TEST/ui/right_pane_layout.backup.json \
   data/users/TEST/ui/right_pane_layout.json
```

---

## 🐛 Troubleshooting

### Layout Not Applied
1. Check file exists: `ls data/users/<user_id>/ui/right_pane_layout.json`
2. Validate JSON: `cat file.json | python3 -m json.tool`
3. Check console for errors: Browser DevTools → Console
4. Verify API response: `curl http://localhost:8000/ui/config/<user_id>/right_pane_layout`

### Panels Still Visible
- Check `visible` field is `false`, not `"false"` (boolean vs string)
- Verify panel ID matches exactly (case-sensitive)
- Clear browser cache and reload

### Order Not Applied
- Ensure all panel IDs in `order` array exist for that persona
- Check for typos in panel IDs
- Order only applies to panels that pass visibility filter

---

## 📚 Related Docs

- **[PHASE3_RIGHT_PANE_OVERRIDES_COMPLETE.md](PHASE3_RIGHT_PANE_OVERRIDES_COMPLETE.md)** — Full implementation details
- **[PERSONA_PANEL_CONFIG_IMPLEMENTATION.md](PERSONA_PANEL_CONFIG_IMPLEMENTATION.md)** — Phase 1+2 foundation
- **[RIGHT_PANE_ARCHITECTURE_PROPOSAL.md](RIGHT_PANE_ARCHITECTURE_PROPOSAL.md)** — Original architecture proposal

---

**Quick Reference Version**: 1.0
**Last Updated**: 2025-10-11
**Applies To**: Phase 3 (User Overrides System)
