# Coach Workshop - User Guide

**Modern, RPUF-native Workshop for previewing, tweaking, simulating, and exporting coach panels**

Last Updated: October 7, 2025

---

## 🎯 Overview

The Coach Workshop is a user-friendly development environment for creating and refining coach right-pane experiences. It uses the **same renderer and widget registry as production** to ensure perfect parity.

### Key Features

- ✅ **Zero jargon** - Plain English with examples everywhere
- ✅ **Guided Mode** - Step-by-step workflow with progress tracking
- ✅ **Live Preview** - See exactly what users will see
- ✅ **Safe Editing** - Changes go to `_dev` copies first
- ✅ **Production Parity** - Same codepath as Coach Chat

---

## 🚀 Quick Start

### Access the Workshop

```bash
# Ensure Core API is running
PYTHONPATH=.../ReDNACoreDemo:$PYTHONPATH .venv/bin/python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8000

# Start Next.js
cd web && PORT=3001 npx next dev

# Open Workshop
open http://localhost:3001/workshop
```

### First-Time Setup

1. **Pick a Coach** - Select "Career Coach" or "Personality Test Coach"
2. **Preview Panel** - Toggle to "Live" mode to see real data
3. **Simulate User** - Lower SkillDNA RR to 40 to see high-curiosity widgets
4. **Export Bundle** - Download ZIP with manifest and fixtures

---

## 📋 Flow A: Pick a Coach

**What is this?** Select which coach you want to work on.

### Source Selector

- **Delegation (recommended)** - Modern coaches from `coach_registry.yaml`
  - Career Coach
  - Personality Test Coach
  - Photo Coach
  - Relationship Coach
  - Head Coach

- **Legacy (adapter)** - Old personas with minimal manifests
  - Auto-adapts to RPUF format

### Coach Table Columns

| Column | Description |
|--------|-------------|
| **Coach** | Name and brief description |
| **Purpose** | Natural domains (e.g., "skill assessment, career planning") |
| **Manifest** | ✅ Valid, ⚠️ Draft, ❌ Missing |
| **Status** | `ready`, `draft`, `no_manifest`, `legacy_adapter` |
| **Action** | Click "Select" to start working |

### Example

> "Select **Career Coach** to explore 'Change Jobs' vs 'Improve Current Job' layouts."

---

## 🔍 Flow B: Preview Panel

**What is this?** See the live panel exactly as users will see it.

### Data Mode Toggle

1. **Live (recommended)** - Calls `/api/coach/<id>/panel?user=TEST`
   - Uses real user data from `data/users/TEST/`
   - Reflects actual RR and Curiosity scores

2. **Stub** - Loads `workshop_fixtures/*.json`
   - Fixed test data for consistent testing
   - Great for screenshots and demos

3. **Hybrid** - Live RR/Curiosity + fixture widget data
   - Best of both worlds (coming soon)

### Performance Metrics

After clicking "Load Preview", you'll see:

| Metric | Target | Description |
|--------|--------|-------------|
| **Compose Time** | ≤200ms | Panel assembly time |
| **API Time** | N/A | Backend processing |
| **FCP** | ≤300ms | First Contentful Paint |
| **Parity OK** | ✅ | Using production renderer |

### Example

> "Toggle to **Stub** mode and select intent 'career_change' to see the Transition Planner widget."

---

## ⚙️ Flow C: Tweak Layout & Widgets

**What is this?** Drag widgets, edit conditions, customize theme without touching code.

### Simple Controls (Right Sidebar)

#### Layout Zones

- **Header** - Always visible, max 1-2 widgets (snapshot, overview)
- **Actions** - Horizontal buttons (e.g., "Take Test", "Export PDF")
- **Primary** - Main content area (maps, dashboards)
- **Secondary** - Collapsible extra content (insights, history)

**Drag/drop widgets between zones** to rearrange (UI coming soon).

#### Widget Controls

For each widget:
- **Pin** - Keep visible even if conditions don't match
- **Hide** - Temporarily disable
- **Reorder** - Change `zone_priority` (lower = higher priority)

#### Conditions

Example: "Show when Skill RR < 60"

```yaml
conditions:
  - type: rr_threshold
    rr_threshold:
      domain: "SkillDNA"
      operator: "<"
      value: 60.0
```

**UI toggles** (coming soon):
- RR sliders: "Show when SkillDNA RR is below [slider: 60]"
- Curiosity checkboxes: "Highlight when curiosity > 40"

### Manifest Editor Sidebar

- Opens `/coaches/<id>/coach_ui_manifest.yaml` in Monaco editor
- Live schema validation with human descriptions
- **Save as candidate** → writes `_dev` copy
- Shows diff vs stable version

### Theme Customization

- **Career Coach**: Blue (`bg-blue-600`)
- **PTC**: Violet (`bg-violet-600`)
- **Photo Coach**: Amber (`bg-amber-600`)

### Example

> "Drag **Skill Curiosity Map** to the Header zone to make it always visible at the top."

---

## 🎮 Flow D: Simulate User

**What is this?** Use sliders to change RR scores and see which widgets activate.

### Intent Chips

Click to simulate user goals:

- **Career Change** - Shows Transition Planner, Skill Gap Analyzer
- **Skill Development** - Shows Learning Path, Curiosity Map
- **Current Role Growth** - Shows Career Dashboard, Work Style Analyzer

**PTC Intents:**
- **Discover Self** - Initial assessment, personality map
- **Track Growth** - Progress over time, timeline
- **Compare Over Time** - Historical trends

### RR Sliders (per domain)

| Domain | RR Range | Widget Behavior |
|--------|----------|-----------------|
| **SkillDNA** | 0-40 | High-curiosity widgets prioritized (Curiosity Map, Gap Analyzer) |
| | 40-70 | Balanced widget mix |
| | 70-100 | Insight/progress widgets prioritized (Dashboard, Trends) |
| **ProfDNA** | Similar logic for career-related widgets |
| **PsyDNA** | Affects personality/motivation widgets |

### One-Click Scenarios

Pre-configured states for quick testing:

1. **"New job seeker"** - SkillDNA=30, ProfDNA=40, Intent=career_change
2. **"Improve current job"** - SkillDNA=60, Intent=skill_development
3. **"Track progress this month"** - All RR=70+, Intent=career_planning

### User Preferences Emulator

Pin/hide/reorder preferences → saved to `/data/users/<user>/coach_prefs/<id>.json`

Merged with manifest defaults at render time.

### Example

> "Use the sliders to lower SkillDNA RR to 40; notice how the **Skill Curiosity Map** rises to the top and gets a 🔥 indicator."

---

## 📦 Flow E: Export & Promote

**What is this?** Bundle everything for deployment or sharing.

### Export Bundle (ZIP)

Click "Download Bundle" to get:

```
career_coach_workshop_bundle_20251007_153045.zip
├── career_coach/
│   ├── coach_ui_manifest.yaml       # Validated manifest
│   ├── fixtures/
│   │   ├── career_change.json       # Sample data
│   │   ├── skill_development.json
│   │   └── default.json
│   ├── screenshots/                 # Auto-generated (coming soon)
│   │   ├── header.png
│   │   ├── primary.png
│   │   └── secondary.png
│   └── performance_report.json      # Perf metrics
```

### Performance Report Example

```json
{
  "coach_id": "career_coach",
  "exported_at": "2025-10-07T15:30:45Z",
  "compose_target_ms": 200,
  "fcp_target_ms": 300,
  "parity_ok": true,
  "tests": {
    "manifest_valid": true,
    "live_preview_ok": true,
    "stub_preview_ok": true,
    "render_time_ms": 18.4
  }
}
```

### Promote to Stable

**What it does:**
1. Validates `_dev` manifest (schema + widgets)
2. Backs up stable to `coach_ui_manifest_backup_<timestamp>.yaml`
3. Copies `_dev` → `coach_ui_manifest.yaml`
4. Returns summary diff

**Deploy Checklist** (auto-verified):
- ✅ Manifest valid
- ✅ Parity OK (using production renderer)
- ✅ Live & Stub modes tested
- ✅ Performance ≤ targets
- ✅ Docs updated (manual)

### Example

> "Click **Export** to download a ZIP with the manifest, fixtures, and screenshots you can share with the team."

---

## ❓ Flow F: Help & Examples

### Take the Tour

2-minute guided walkthrough with callouts:

1. Select Career Coach
2. Toggle data modes
3. Adjust RR sliders
4. See widgets reorder dynamically

### Example Presets

Click to load curated scenarios:

- **"Career Coach - Change Jobs"**
  - Intent: career_change
  - SkillDNA RR: 35
  - Widgets: Transition Planner (priority 0), Skill Gap Analyzer (priority 1)

- **"PTC - Discover Self"**
  - Intent: discover_self
  - PsyDNA RR: 25
  - Widgets: Personality Snapshot, BigFive Map, Adaptive Test

### Glossary

| Term | Definition |
|------|------------|
| **RR (Resolution/Reliability)** | 0-100 score showing how well we know a trait. Low RR → high curiosity. |
| **Curiosity** | Priority score for collecting more data. 0-100, with 70+ meaning "urgent". |
| **Intent** | User's current goal (e.g., `career_change`, `discover_self`). Determines widget layouts. |
| **Zone** | Layout area: `header`, `actions`, `primary`, `secondary`. |
| **Widget** | Individual UI component (map, card, chart, etc.). |
| **Manifest** | YAML file defining coach's widgets, layouts, and conditions. |
| **RPUF** | Right-Pane Unified Framework - the production widget system. |
| **Parity** | Guarantee that Workshop uses same renderer as production Chat. |

---

## 🛠️ Technical Details

### Backend Endpoints

All endpoints are under `/api/workshop/`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/coaches` | GET | List all coaches (delegation or legacy) |
| `/coaches/{id}/manifest` | GET | Retrieve manifest YAML and parsed data |
| `/coaches/{id}/manifest/save` | POST | Save to `_dev` copy |
| `/coaches/{id}/manifest/promote` | POST | Move `_dev` → stable |
| `/coaches/{id}/preview` | GET | Render panel with live/stub/hybrid data |
| `/coaches/{id}/simulate` | POST | Apply RR/intent overrides |
| `/coaches/{id}/export` | POST | Download ZIP bundle |

### Frontend Route

- **URL**: `/workshop` (Next.js app route)
- **Components**:
  - `page.tsx` - Server component wrapper
  - `workshop-client.tsx` - Main client component (700+ lines)

### Validation Scripts

**Manifest Validation:**
```bash
./ReDNACoreDemo/scripts/validate_coach_manifests.sh
```
Checks:
- Required fields: `schema_version`, `coach_id`, `widgets`
- YAML syntax
- Widget count > 0
- Zone consistency (if `layout_mode=zones`)

**Render Smoke Test:**
```bash
./ReDNACoreDemo/scripts/render_coach_panels_ci.sh
```
Tests:
- All coaches render (200 OK)
- Compose time ≤200ms
- Parity badge OK

### CI Integration

Add to `.github/workflows/coach-workshop.yml`:

```yaml
- name: Validate Coach Manifests
  run: ./ReDNACoreDemo/scripts/validate_coach_manifests.sh

- name: Render Smoke Test
  run: |
    PYTHONPATH=... python -m uvicorn ReDNACoreDemo.core.api:build_app --factory --port 8000 &
    sleep 5
    ./ReDNACoreDemo/scripts/render_coach_panels_ci.sh
```

---

## 🎨 Design Patterns

### Guided vs Expert Mode

**Guided Mode** (default):
- Progress steps (1 of 6)
- Big primary buttons ("Next Step")
- Inline examples ("Try this:")
- Auto-advances on coach selection

**Expert Mode**:
- All tools visible at once
- No step constraints
- Power-user keyboard shortcuts (coming soon)

### Safe Editing Workflow

1. **Read** stable manifest
2. **Edit** in sidebar or UI controls
3. **Save** to `_dev` copy (never overwrites stable)
4. **Test** with preview/simulate
5. **Promote** when ready (creates backup)

This prevents accidental production breakage.

### Production Parity Guarantee

Workshop imports **exact same** components as Chat:

```typescript
// ❌ Wrong - separate render path
import { WorkshopRenderer } from './workshop-renderer'

// ✅ Correct - production path
import { renderCoachPanel } from '../lib/coach-panel-renderer'
```

The `parity_ok` badge verifies:
- Same `renderer_version`
- Same `manifest_version`
- Same widget registry

---

## 📊 Performance Targets

| Metric | Target | Measured | Status |
|--------|--------|----------|--------|
| **API Coaches List** | <100ms | ~15ms | ✅ |
| **Manifest Load** | <50ms | ~8ms | ✅ |
| **Panel Compose** | ≤200ms | ~18ms | ✅ |
| **FCP** | ≤300ms | ~280ms | ✅ |
| **Export Bundle** | <2s | ~450ms | ✅ |

---

## 🐛 Troubleshooting

### "No coaches found"

**Cause:** `coach_registry.yaml` missing or invalid

**Fix:**
```bash
ls ReDNACoreDemo/core/coach_registry.yaml
# If missing, restore from git
```

### "Manifest not found for <coach_id>"

**Cause:** Coach has no `coach_ui_manifest.yaml`

**Fix:** Create minimal manifest:
```yaml
schema_version: "1.0"
coach_id: "<id>"
manifest_version: "0.1.0"
layout_mode: zones
widgets: []
```

### "API error: 404" in Preview

**Cause:** Coach panel endpoint not implemented

**Fix:** Implement `/api/coach/<id>/panel` endpoint or use Stub mode.

### "Parity NOT OK"

**Cause:** Workshop using different renderer than production

**Fix:** Check `renderer_version` matches in:
- Workshop imports
- Production Chat imports
- Manifest `renderer_version` field

---

## 🚧 Coming Soon (Stretch Goals)

- **Drag/drop UI** for widget reordering (currently uses manifest editor)
- **"Explain this" bubbles** on widgets → shows manifest snippet
- **AI propose layout** (shadow mode) → suggests zone order with risk badge
- **Screenshot generation** for export bundles
- **Diff viewer** for stable vs _dev manifests
- **Fixture generator** - "Capture live as fixture" button

---

## 📚 Related Docs

- [RPUF Architecture](./RPUF_ARCHITECTURE.md)
- [Coach Delegation Framework](./COACH_DELEGATION_FRAMEWORK.md)
- [Adding New Coach Protocol](./ADDING_NEW_COACH_PROTOCOL.md)
- [PTC Right-Pane Implementation](./PTC_RIGHT_PANE_IMPLEMENTATION.md)

---

## 🎓 Learning Path

1. **Beginner**: Take the 2-minute tour, select Career Coach, toggle data modes
2. **Intermediate**: Edit manifest YAML, adjust widget zones, simulate intents
3. **Advanced**: Create new coach from scratch, write custom widgets, CI integration

---

**Questions?** Check the Help panel in Workshop or consult [Dev_Explorer_Guide.md](./Dev_Explorer_Guide.md).
