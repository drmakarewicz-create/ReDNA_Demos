# Coach Workshop - Quick Start

**One-page cheat sheet for immediate access**

---

## 🚀 Access

```
http://localhost:3001/workshop
```

**Prerequisites:**
- Core API running on port 8000
- Next.js running on port 3001

---

## 🎯 5-Minute Workflow

### 1. Pick a Coach
- Click "Delegation (recommended)"
- Select **Career Coach** or **Personality Test Coach**
- Click **Select** button

### 2. Preview Panel
- Toggle to **Live** (real data) or **Stub** (fixtures)
- Click **Load Preview**
- Check performance: ≤200ms compose, ≤300ms FCP, Parity ✅

### 3. Simulate User
- Select intent: **Career Change**, **Skill Development**, etc.
- Lower **SkillDNA RR** to 40 with slider
- Click **Apply Simulation → Preview**
- Watch widgets reorder dynamically

### 4. Export Bundle
- Click **Export & Promote** tab
- Click **Download Bundle** button
- Get ZIP with manifest, fixtures, performance report

---

## 📋 API Endpoints (Quick Reference)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/workshop/coaches` | List all coaches |
| `GET /api/workshop/coaches/{id}/manifest` | Get manifest YAML |
| `POST /api/workshop/coaches/{id}/manifest/save` | Save to _dev copy |
| `POST /api/workshop/coaches/{id}/manifest/promote` | Promote to stable |
| `GET /api/workshop/coaches/{id}/preview` | Preview panel (live/stub) |
| `POST /api/workshop/coaches/{id}/simulate` | Apply RR/intent overrides |
| `POST /api/workshop/coaches/{id}/export` | Download ZIP bundle |

---

## 🧪 Testing Commands

**Validate all manifests:**
```bash
./ReDNACoreDemo/scripts/validate_coach_manifests.sh
```

**Render smoke test:**
```bash
./ReDNACoreDemo/scripts/render_coach_panels_ci.sh
```

**Test API directly:**
```bash
curl "http://127.0.0.1:8000/api/workshop/coaches?source=delegation"
curl "http://127.0.0.1:8000/api/workshop/coaches/career_coach/preview?user_id=TEST&data_mode=live"
```

---

## 📖 Glossary (5-Second Version)

| Term | Meaning |
|------|---------|
| **RR** | How well we know a trait (0-100) |
| **Curiosity** | Priority for collecting data (0-100) |
| **Intent** | User's goal (career_change, etc.) |
| **Zone** | Layout area (header/actions/primary/secondary) |
| **Widget** | UI component (map, card, chart) |
| **Manifest** | YAML file defining coach's widgets |
| **RPUF** | Right-Pane Unified Framework (production system) |
| **Parity** | Workshop uses same renderer as Chat ✅ |

---

## 🎨 Modes

### Guided Mode (Default)
- Step-by-step workflow
- Inline examples ("Try this:")
- Auto-advances to next step
- Best for: Dave (non-technical users)

### Expert Mode
- All tools visible at once
- No step constraints
- Best for: Power users

**Toggle:** Top-left button (Guided / Expert)

---

## ⚡ Performance Targets

| Metric | Target |
|--------|--------|
| Panel Compose | ≤200ms |
| FCP | ≤300ms |
| API Calls | ≤3 per panel |

---

## 🔥 Example Scenarios

**"New Job Seeker"**
```
Intent: career_change
SkillDNA RR: 30
ProfDNA RR: 40

Result: Transition Planner, Skill Gap Analyzer prioritized
```

**"Improve Current Job"**
```
Intent: skill_development
SkillDNA RR: 60

Result: Learning Path, Curiosity Map visible
```

**"Track Progress"**
```
Intent: career_planning
All RR: 70+

Result: Dashboard, Trends, Progress widgets
```

---

## 📦 Export Bundle Contents

```
career_coach_workshop_bundle_20251007.zip
├── career_coach/
│   ├── coach_ui_manifest.yaml       # Validated manifest
│   ├── fixtures/
│   │   ├── career_change.json
│   │   ├── skill_development.json
│   │   └── default.json
│   └── performance_report.json      # Perf metrics
```

---

## 🛠️ Troubleshooting

**"No coaches found"**
→ Check `ReDNACoreDemo/core/coach_registry.yaml` exists

**"API error: 404"**
→ Use Stub mode or implement panel endpoint

**"Parity NOT OK"**
→ Check `renderer_version` matches production

---

## 📚 Full Documentation

- [Complete User Guide](./COACH_WORKSHOP_GUIDE.md) - 12 pages
- [Implementation Summary](./WORKSHOP_IMPLEMENTATION_SUMMARY.md) - Technical details
- [Dev Explorer Guide](./Dev_Explorer_Guide.md) - General development

---

**Need help?** Open Workshop → Help & Examples tab → Click "Start Tour"
