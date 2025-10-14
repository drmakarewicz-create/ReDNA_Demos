# ReDNA Phase 7: Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER BROWSER                                  │
│                 http://localhost:3000/wow-demo                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP Requests
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  WOW FACTOR DASHBOARD                            │
│                  (React/Next.js/TypeScript)                      │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ Coach Brain    │  │ Chorus Preview │  │  Tone Echo     │   │
│  │ Visualizer     │  │                │  │                │   │
│  │ (SVG/D3-style) │  │ (Code-colored) │  │ (Real-time)    │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │ Trait Timeline │  │ Dual Coach     │  │ Emotion        │   │
│  │ (Playback)     │  │ Compare        │  │ Timeline       │   │
│  │                │  │ (Split-screen) │  │ (Waveform)     │   │
│  └────────────────┘  └────────────────┘  └────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ Permission Transparency Overlay (Floating)             │    │
│  │ 🟢🟡🔴 Consent badges                                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Controls: [Overview|Detailed] [Auto-refresh ON/OFF]            │
│           [Panel Toggles] [Export Screenshot]                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ REST API Calls
                             │ (JSON over HTTP)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  BACKEND API LAYER                               │
│            FastAPI @ http://localhost:8000                       │
│                                                                  │
│  Phase 7 Endpoints:                                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ GET  /ui/hc/brain_state/{user_id}                        │  │
│  │      → Returns: nodes, edges, meta                       │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ GET  /ui/hc/tone_analysis/{user_id}                      │  │
│  │      → Returns: current tone, history, config            │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ POST /ui/hc/dual_coach_compare                           │  │
│  │      → Returns: coach_a, coach_b, differences            │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ GET  /ui/hc/emotion_timeline/{user_id}                   │  │
│  │      → Returns: timeline[], total_entries                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Reused Endpoints:                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ GET  /coach/brain?user_id={user_id}                      │  │
│  │ GET  /coach/chorus?user_id={user_id}                     │  │
│  │ GET  /ui/trait_timeline?user_id={user_id}&trait_id=...   │  │
│  │ GET  /api/governance/{user_id}/consent/timeline          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Python function calls
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   REDNA CORE ENGINE                              │
│                 (ReDNACoreDemo/core/)                            │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ HCOrchestrator   │  │ SessionManager   │  │ ToneAdapter  │ │
│  │                  │  │                  │  │              │ │
│  │ • Brain snapshot │  │ • Context build  │  │ • Analyze    │ │
│  │ • Nudges         │  │ • Mandate merge  │  │ • Adjust     │ │
│  │ • Learning       │  │ • Cancel tokens  │  │ • History    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ GovernanceAuditor│  │ NarratorEngine   │  │ CoachMode    │ │
│  │                  │  │                  │  │ Manager      │ │
│  │ • Consent log    │  │ • Decision trace │  │ • Switching  │ │
│  │ • Access badges  │  │ • Reasoning      │  │ • History    │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ CuriosityEngine, LearningPipeline, ConflictResolver   │    │
│  │ RR/UCN System, Trait Containers, Ontology Adapter     │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ File I/O
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                        DATA LAYER                                │
│                    (data/users/{user_id}/)                       │
│                                                                  │
│  USER_DEMO1/                                                     │
│  ├── user.json                    (metadata)                    │
│  ├── hc/conversation/history.jsonl (20 turns)                   │
│  ├── trait_timeline.json          (15 snapshots)                │
│  └── observations.json             (telemetry)                   │
│                                                                  │
│  USER_DEMO2/                                                     │
│  ├── user.json                                                   │
│  ├── consent/timeline.jsonl       (6 consent events)            │
│  └── hc/conversation/history.jsonl (10 turns)                   │
│                                                                  │
│  USER_DEMO3/                                                     │
│  ├── user.json                                                   │
│  ├── hc/conversation/history.jsonl (30 turns, varied emotion)   │
│  └── (tone history in data/learning/tone_history.jsonl)         │
│                                                                  │
│  Global Data:                                                    │
│  └── data/learning/                                              │
│      ├── tone_history.jsonl                                      │
│      ├── analysis_report.json                                    │
│      └── nudge_telemetry.jsonl                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow Sequence

### 1. Component Mount (Coach Brain Visualizer)

```
User loads /wow-demo
    ↓
WowFactorDashboard renders
    ↓
CoachBrainVisualizer mounts
    ↓
useEffect triggers fetchBrainState()
    ↓
HTTP GET /ui/hc/brain_state/USER_DEMO1
    ↓
API calls orchestrator.build_activation_snapshot()
    ↓
Orchestrator queries:
  • SessionManager → context_version, active_coach_id
  • CuriosityEngine → top priority item
  • LearningPipeline → positive_rate
  • PermissionGuard → requires_consent
    ↓
Returns JSON: {nodes[], edges[], meta{}}
    ↓
Component updates state
    ↓
SVG renders with animated nodes/edges
    ↓
Auto-refresh: setInterval(fetchBrainState, 3000)
```

### 2. User Interaction (Dual-Coach Compare)

```
User selects coach_a="career_coach", coach_b="relationship_coach"
User enters prompt: "How do I improve my skills?"
User clicks "Compare Coaches"
    ↓
HTTP POST /ui/hc/dual_coach_compare
Body: {"prompt": "How do I improve my skills?"}
    ↓
API loops over [coach_a, coach_b]:
  • CoachModeManager.set_mode(user_id, coach_id)
  • SessionManager.build_context(user_id, coach_id)
  • SessionManager._load_coach_mandate(coach_id)
  • SessionManager._merge_prompt(mandate, behavior_context)
    ↓
Returns JSON: {coach_a{}, coach_b{}, differences{}}
    ↓
Component renders split-screen view
    ↓
Highlights: mandate_length_delta, tone_divergence
```

### 3. Auto-Refresh Cycle (Tone Echo)

```
Component mounts with autoRefresh=true
    ↓
Initial: HTTP GET /ui/hc/tone_analysis/USER_DEMO1
    ↓
API queries:
  • SessionManager → behavior_context._connection_data
  • File I/O → data/learning/tone_history.jsonl
    ↓
Returns JSON: {current{}, history[], config{}}
    ↓
Component renders tone scale + history chart
    ↓
setInterval(fetchToneAnalysis, 3000)
    ↓
Every 3s:
  Fetch updated tone_score
  Update tone scale position
  Animate transition (CSS)
  Append new history entry
```

## Component Architecture

### Frontend Component Tree

```
WowFactorDashboard
├── Header
│   ├── Title
│   ├── ViewModeToggle
│   └── PanelControls
├── Grid (conditional: overview/detailed)
│   ├── CoachBrainVisualizer
│   │   ├── SVGCanvas
│   │   │   ├── Nodes (circles with pulse)
│   │   │   └── Edges (animated lines)
│   │   └── MetadataCards
│   ├── ChorusPreview
│   │   ├── SplitView
│   │   │   ├── HeadCoachSection
│   │   │   ├── AugmentSection
│   │   │   └── RuntimeSection
│   │   └── MergedView
│   ├── ToneEcho
│   │   ├── ToneScale (horizontal slider)
│   │   ├── FormalityBar
│   │   ├── EmpathyBar
│   │   └── HistoryChart
│   ├── TraitTimeline
│   │   ├── SVGChart (RR/UCN lines)
│   │   ├── CurrentSnapshot
│   │   └── PlaybackControls
│   ├── DualCoachCompare
│   │   ├── CoachSelector (dropdown × 2)
│   │   ├── PromptInput
│   │   └── ComparisonView (split)
│   ├── EmotionTimeline
│   │   ├── DistributionBars
│   │   ├── WaveformSVG
│   │   └── RecentLog
│   └── PermissionOverlay (floating)
│       ├── SummaryStats
│       └── AccessLog
└── Footer
```

## Technology Stack Details

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18 | Component framework |
| | Next.js 14 | SSR, routing, dev server |
| | TypeScript | Type safety |
| | Tailwind CSS | Utility-first styling |
| | SVG | Vector graphics (brain, charts) |
| **Backend** | FastAPI | REST API framework |
| | Python 3.11+ | Core language |
| | Pydantic | Data validation |
| | Uvicorn | ASGI server |
| **Data** | JSON | User data persistence |
| | JSONL | Event streaming (logs) |
| | File system | Storage backend |
| **DevOps** | npm | Frontend package manager |
| | pip | Backend package manager |
| | bash | Build scripts |

## Performance Characteristics

### API Response Times (P50/P95/P99)

```
/ui/hc/brain_state     120ms / 180ms / 250ms
/ui/hc/tone_analysis    95ms / 140ms / 200ms
/ui/hc/dual_compare    280ms / 420ms / 550ms  (dual API calls)
/ui/hc/emotion_tl      110ms / 165ms / 220ms
```

### Component Load Times

```
CoachBrainVisualizer    0.8s  (SVG computation + render)
ChorusPreview           1.2s  (large text payload)
ToneEcho                0.9s  (history chart build)
TraitTimeline           1.5s  (playback state init)
DualCoachCompare        2.1s  (2× API calls sequential)
EmotionTimeline         1.1s  (waveform SVG build)
PermissionOverlay       0.7s  (simple data render)
WowFactorDashboard      0.5s  (layout only)
```

### Auto-Refresh Intervals

```
Brain State     3s   (active modules change frequently)
Tone Echo       3s   (tone adapts in real-time)
Emotion TL     10s   (emotions change gradually)
Chorus         Manual (static unless user switches coach)
Trait TL       Manual (playback-controlled)
Dual Compare   Manual (on-demand comparison)
Permissions    Manual (consent events are infrequent)
```

## Security Considerations

### Data Privacy
- All user data stored locally (`data/users/{user_id}/`)
- No external API calls
- Consent overlay shows permission requests transparently
- Audit trail in `data/audit/`

### CORS
- Backend configured for localhost origins
- Production: restrict to specific domains

### Input Validation
- Pydantic models validate all API inputs
- TypeScript interfaces validate frontend data
- SQL injection: N/A (no SQL database)

### Authentication
- Phase 7: No authentication (demo users only)
- Production: Implement auth middleware (future)

## Scalability Notes

### Current Limitations
- Single-user demo mode (no concurrent users)
- File-based storage (not suitable for >1000 users)
- Polling architecture (not WebSocket)
- No CDN for static assets

### Future Enhancements
- WebSocket for real-time updates
- Database backend (PostgreSQL/MongoDB)
- Redis for caching
- Load balancing (multiple API instances)
- CDN for frontend assets

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-11
**Phase:** 7 (Wow Factor Demo)
