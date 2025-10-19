# RPUF (Right Pane Unified Framework) Architecture

**Version:** 1.0
**Last Updated:** October 7, 2025
**Status:** Design Specification

---

## Overview

The **Right Pane Unified Framework (RPUF)** is a manifest-driven rendering system for coach-specific UI components in the ReDNA platform. It enables delegation coaches to define their right-pane layouts declaratively through YAML manifests, ensuring dev/prod parity and enabling rapid iteration through the Coach Workshop.

## Goals

1. **Unified rendering** - Single renderer for all coach right-panes (legacy + delegation)
2. **Manifest-driven** - Declarative widget composition via `coach_ui_manifest.yaml`
3. **Dev/prod parity** - Workshop uses production renderer (no divergence)
4. **Performance** - Compose ≤200ms, FCP ≤300ms, lazy loading support
5. **Extensibility** - Widget registry allows new component types without core changes

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     Coach Workshop (Dev)                     │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │ Source     │  │ Data Binding │  │ Intent/RR Simulator │ │
│  │ Switcher   │  │ Live/Stubbed │  │ Telemetry Panel     │ │
│  └────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  RPUF Core (Shared Library)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Manifest     │  │ Widget       │  │ Layout Manager  │  │
│  │ Loader       │  │ Registry     │  │ (sort/filter)   │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Condition    │  │ Data Binder  │  │ Telemetry       │  │
│  │ Evaluator    │  │ (API/stub)   │  │ Collector       │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            Production UI (Coach Chat Right Pane)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ <CoachToolsPane>                                     │  │
│  │   {renderWidgets(manifest, intent, user_prefs)}     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Component Structure

### 1. RPUF Core Library

**Location:** `/ReDNACoreDemo/core/rpuf/`

```
rpuf/
├── __init__.py
├── manifest_loader.py       # Load & validate manifests
├── widget_registry.py       # Component registry & resolver
├── layout_manager.py        # Sort, filter, apply conditions
├── condition_evaluator.py   # Evaluate widget visibility conditions
├── data_binder.py           # Bind data sources (API/static/computed)
├── telemetry.py             # Performance tracking
└── types.py                 # TypedDict/dataclass definitions
```

### 2. Frontend Integration

**Location:** `/web/src/lib/rpuf/`

```
rpuf/
├── index.ts                 # Main exports
├── manifest-loader.ts       # Fetch & cache manifests
├── widget-renderer.tsx      # Core rendering logic
├── widget-registry.ts       # React component registry
├── layout-resolver.ts       # Intent/RR/user-pref merger
├── data-fetcher.ts          # API client for widget data
├── telemetry-hooks.ts       # Performance instrumentation
└── types.ts                 # TypeScript types
```

### 3. Widget Components

**Location:** `/web/src/components/widgets/`

```
widgets/
├── career/
│   ├── SkillCuriosityMap.tsx
│   ├── TransitionPlanner.tsx
│   └── CareerDashboard.tsx
├── personality/
│   ├── PersonalityRadar.tsx
│   ├── TraitQuestionnaire.tsx
│   └── PersonalityMap.tsx
├── shared/
│   ├── WidgetContainer.tsx      # Wrapper with collapse/pin
│   ├── WidgetError.tsx          # Error boundary
│   └── WidgetSkeleton.tsx       # Loading state
└── registry.ts                   # Widget registration
```

## Data Flow

### Manifest Loading

```typescript
// 1. Load manifest
const manifest = await loadManifest(coachId);

// 2. Validate against schema
validateManifest(manifest);

// 3. Resolve intent/RR/user_prefs
const resolvedLayout = resolveLayout(manifest, {
  intent: 'career_change',
  rrData: userRR,
  userPrefs: userWidgetPrefs
});

// 4. Render widgets
return (
  <CoachToolsPane>
    {resolvedLayout.widgets.map(widget => (
      <WidgetRenderer
        key={widget.id}
        widget={widget}
        dataSource={widget.data_source}
      />
    ))}
  </CoachToolsPane>
);
```

### Widget Rendering

```typescript
function WidgetRenderer({ widget, dataSource }) {
  // 1. Fetch data
  const { data, loading, error } = useWidgetData(dataSource);

  // 2. Resolve component
  const Component = widgetRegistry.get(widget.component);

  // 3. Track performance
  const metrics = useWidgetTelemetry(widget.id);

  // 4. Render with container
  return (
    <WidgetContainer
      id={widget.id}
      title={widget.title}
      collapsible={widget.collapsible}
      pinnable={widget.pinnable}
      metrics={metrics}
    >
      {loading ? <WidgetSkeleton /> : null}
      {error ? <WidgetError error={error} /> : null}
      {data ? <Component data={data} {...widget.props} /> : null}
    </WidgetContainer>
  );
}
```

## Condition Evaluation

Widgets support multiple condition types:

### Intent Conditions
```yaml
conditions:
  - type: intent
    intent: ["career_change", "skill_development"]
```
**Logic:** Show if user's current intent matches ANY of the listed intents.

### RR/Curiosity Thresholds
```yaml
conditions:
  - type: curiosity_threshold
    curiosity_threshold:
      domain: SkillDNA
      operator: ">="
      value: 60.0
```
**Logic:** Show if domain's curiosity meets threshold.

### Data Availability
```yaml
conditions:
  - type: data_available
    data_available:
      path: "resolved.SkillDNA"
      min_count: 3
```
**Logic:** Show if data exists and meets minimum count.

### Feature Flags
```yaml
conditions:
  - type: feature_flag
    feature_flag: "career_coach_v2"
```
**Logic:** Show if feature flag is enabled.

## Layout Resolution

Priority order for widget visibility/ordering:

1. **Intent layouts** - Highest priority (career_change intent boosts specific widgets)
2. **User preferences** - User-pinned widgets, custom order
3. **Manifest defaults** - Widget `position` and `default_visible`
4. **Conditions** - Evaluated last, widgets hidden if conditions fail

```python
def resolve_layout(manifest, context):
    widgets = manifest.widgets.copy()

    # 1. Apply intent layout overrides
    if context.intent in manifest.intent_layouts:
        layout = manifest.intent_layouts[context.intent]
        widgets = apply_intent_layout(widgets, layout)

    # 2. Evaluate conditions
    widgets = [w for w in widgets if evaluate_conditions(w, context)]

    # 3. Apply user preferences
    widgets = apply_user_prefs(widgets, context.user_prefs)

    # 4. Sort by position
    widgets.sort(key=lambda w: w.position)

    return widgets
```

## Performance Targets

### Compose Time Budget
- **Target:** ≤200ms from manifest load to first widget render
- **Breakdown:**
  - Manifest load/parse: 20ms
  - Condition evaluation: 30ms
  - Layout resolution: 50ms
  - Component instantiation: 100ms

### First Contentful Paint (FCP)
- **Target:** ≤300ms for right pane visibility
- **Strategies:**
  - Lazy load below-fold widgets
  - Skeleton loaders for async data
  - Concurrent data fetching (max 3 parallel)

### Widget Load Time
- **Target:** ≤150ms per widget (including data fetch)
- **Monitoring:** Track via `useWidgetTelemetry` hook

## Workshop Integration

### Source Switcher
```typescript
enum WorkshopSource {
  Personas = 'personas',    // Legacy persona_registry
  Delegation = 'delegation' // Coach registry + manifests
}

function CoachWorkshop() {
  const [source, setSource] = useState(WorkshopSource.Delegation);

  if (source === WorkshopSource.Personas) {
    return <LegacyPersonaRegistry />;
  }

  return <DelegationCoachWorkshop />;
}
```

### Data Binding Modes
```typescript
enum DataBindingMode {
  Live = 'live',       // GET /api/coach/{id}/panel?user={user}
  Stubbed = 'stubbed', // Load from workshop_fixtures/*.json
  Hybrid = 'hybrid'    // Live RR/Curiosity + stub widgets
}

function WorkshopRenderer({ coachId, mode }) {
  const dataProvider = useMemo(() => {
    switch (mode) {
      case DataBindingMode.Live:
        return new LiveDataProvider(coachId);
      case DataBindingMode.Stubbed:
        return new StubDataProvider(coachId);
      case DataBindingMode.Hybrid:
        return new HybridDataProvider(coachId);
    }
  }, [coachId, mode]);

  return <WidgetRenderer dataProvider={dataProvider} />;
}
```

### Intent/RR Simulator
```typescript
interface SimulatorState {
  intent: string | null;
  rr: Record<string, number>;  // domain -> RR value
  curiosity: Record<string, number>;
  cooldowns: Record<string, boolean>;
}

function IntentRRSimulator({ onChange }) {
  const [state, setState] = useState<SimulatorState>({
    intent: null,
    rr: { SkillDNA: 65.0 },
    curiosity: { SkillDNA: 72.0 },
    cooldowns: {}
  });

  return (
    <div>
      <IntentChips onSelect={i => setState({...state, intent: i})} />
      <RRSliders values={state.rr} onChange={rr => setState({...state, rr})} />
      <button onClick={() => onChange(state)}>Apply</button>
    </div>
  );
}
```

## Widget Registry

Widgets register themselves via a central registry:

```typescript
// widgets/career/SkillCuriosityMap.tsx
import { registerWidget } from '../registry';

export function SkillCuriosityMap({ data }) {
  // ... implementation
}

registerWidget('SkillCuriosityMap', SkillCuriosityMap, {
  category: 'visualization',
  requiredProps: ['data'],
  optionalProps: ['minCuriosity', 'colorScheme']
});
```

Registry lookup in renderer:

```typescript
function WidgetRenderer({ widget }) {
  const Component = widgetRegistry.get(widget.component);

  if (!Component) {
    console.error(`Widget not found: ${widget.component}`);
    return <WidgetError message={`Unknown widget: ${widget.component}`} />;
  }

  return <Component {...widget.props} />;
}
```

## AI Suggestions Integration

Widgets can opt into AI-powered suggestions:

```yaml
widgets:
  - id: transition_planner
    component: TransitionPlanner
    ai_suggestions:
      enabled: true
      policy_gate: career_suggestions
      model: claude-3-5-sonnet
      max_suggestions: 3
      shadow_mode: false
```

Backend flow:

1. Widget data fetch includes `ai_suggestions` flag
2. Policy gate checks approval (user consent + domain policy)
3. LLM generates suggestions with provenance
4. Suggestions rendered with attribution + dismiss

## Telemetry & Observability

### Performance Metrics
- `widget.compose_time_ms` - Time to render widget
- `widget.data_fetch_time_ms` - API response time
- `widget.fcp_ms` - First Contentful Paint
- `widget.interaction_count` - User interactions

### Event Tracking
- `widget.rendered` - Widget became visible
- `widget.collapsed` - User collapsed widget
- `widget.pinned` - User pinned to top
- `widget.error` - Render/data error

### Workshop Metrics
- `workshop.manifest_load_time_ms`
- `workshop.fixture_load_time_ms`
- `workshop.preview_render_time_ms`

## Migration Path for Legacy Personas

### Phase 1: Adapter Pattern
Create thin adapters for legacy personas:

```yaml
# coaches/relationship_coach/coach_ui_manifest.yaml
schema_version: "1.0"
coach_id: "relationship_coach"
manifest_version: "0.1.0"
renderer_version: "1.0"

widgets:
  - id: observation_summary
    type: display
    component: ObservationSummary  # Existing component
    position: 0
    data_source:
      type: api
      endpoint: /api/observations/aggregates
```

### Phase 2: Gradual Enhancement
Incrementally add delegation-specific widgets:

```yaml
widgets:
  # Legacy widget (unchanged)
  - id: observation_summary
    component: ObservationSummary

  # New delegation widget
  - id: relationship_insights
    component: RelationshipInsights
    ai_suggestions:
      enabled: true
```

### Phase 3: Full Migration
Once all legacy widgets have manifests, retire persona_registry adapter.

## Next Steps

1. **Implement RPUF core** (`rpuf/manifest_loader.py`, `rpuf/widget_registry.py`)
2. **Create frontend integration** (`web/src/lib/rpuf/`)
3. **Build Workshop bridge** (source switcher, data binding modes)
4. **Create starter manifests** (Career Coach, PTC)
5. **Implement first widgets** (SkillCuriosityMap, PersonalityRadar)
6. **Add telemetry hooks** (performance tracking)
7. **Document widget development** (how to add new widgets)

## Appendix

### File Structure
```
ReDNACoreDemo/
├── core/
│   └── rpuf/                     # RPUF core library
│       ├── manifest_loader.py
│       ├── widget_registry.py
│       └── ...
├── schemas/
│   └── coach_ui_manifest.schema.json
└── coaches/
    ├── career_coach/
    │   ├── coach_ui_manifest.yaml
    │   └── workshop_fixtures/
    │       ├── career_change.json
    │       └── skill_development.json
    └── personality_test_coach/
        ├── coach_ui_manifest.yaml
        └── workshop_fixtures/
            └── assessment_mode.json

web/
└── src/
    ├── lib/
    │   └── rpuf/                 # Frontend RPUF integration
    └── components/
        └── widgets/              # Widget implementations
            ├── career/
            └── personality/
```

### API Endpoints

**Get Coach Panel Data (Live Mode):**
```
GET /api/coach/{coach_id}/panel?user={user_id}&intent={intent}
```

**Get Manifest:**
```
GET /api/coach/{coach_id}/manifest
```

**Workshop Fixture Upload:**
```
POST /api/workshop/fixtures/{coach_id}
Body: { "fixture_name": "career_change", "data": {...} }
```

---

**References:**
- `coach_ui_manifest.schema.json` - Manifest validation schema
- `coach_registry.yaml` - Coach definitions and capabilities
- `CoachToolsPane.tsx` - Production right-pane container
