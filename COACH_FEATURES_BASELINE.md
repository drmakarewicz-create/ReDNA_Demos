# Coach Features Baseline - DO NOT REVERT

**Status:** ✅ PRODUCTION BASELINE
**Last Updated:** 2025-10-12
**Stability:** STABLE - These features are the established baseline

## ⚠️ CRITICAL WARNING

**These coach-specific features are NOT experimental or temporary.**
They are the **established baseline** for the ReDNA coaching system.

**DO NOT:**
- ❌ Remove coach-specific panels without explicit discussion
- ❌ Hardcode panel rendering in `renderPersonaTools()`
- ❌ Skip the persona-panels-config system
- ❌ Assume "no specialized tools" means panels should be removed
- ❌ Revert to earlier commits that lack these features

**IF YOU SEE:**
- Comments like "// These coaches don't have specialized tools yet"
- Hardcoded switch statements for only Photo/PaDNA coaches
- Missing ChatDNA, Career, or Personality panels
- Coach Catalog button only on Head Coach

**STOP!** You're looking at broken/incomplete code. Restore from this baseline.

---

## Established Coach Features (Production Baseline)

### 1. Coach Catalog - Universal Access ✅

**Status:** REQUIRED for all coaches
**Location:** Right pane, top position
**Implementation:** `web/src/app/page-client.tsx` `renderPersonaTools()`

```typescript
// Coach Catalog button - available for ALL personas
const coachCatalogButton = onOpenCoachCatalog ? (
  <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
    <button type="button" onClick={onOpenCoachCatalog}>
      // ... Coach Catalog UI
    </button>
  </div>
) : null;
```

**Why:** Users need ability to switch coaches from any coach mode. This is core UX.

---

### 2. Persona Panel Configuration System ✅

**Status:** PRODUCTION ARCHITECTURE
**Location:** `web/src/lib/persona-panels-config.ts`
**Implementation:** Dynamic panel loading via `getPersonaPanels()`

**Key Files:**
- `web/src/lib/persona-panels-config.ts` - Master configuration (400+ lines)
- `web/src/app/page-client.tsx` - Consumer of config system

**Architecture Benefits:**
- ✅ Declarative panel configuration (no hardcoding)
- ✅ Lazy loading for performance
- ✅ User customization support (future)
- ✅ Easy to add/remove panels per coach
- ✅ Feature flag support built-in

**DO NOT replace this with hardcoded switch statements!**

---

### 3. ChatDNA Coach Panels ✅

**Status:** PRODUCTION FEATURE
**Backend API:** `/api/coach/chatdna_coach/panel`
**Panels:**
1. **ChatDNA Profile** (`chatdna-snapshot-card.tsx`)
   - Language Style RR
   - Interaction RR
   - Top speaking style traits
   - Writing samples count
   - Active communication mode

2. **Language Style Panel** (`language-style-panel.tsx`)
   - Detailed language traits
   - Curiosity map for communication patterns

**Configuration:** `persona-panels-config.ts` lines 238-253

```typescript
chatdna_coach: {
  lifeOS: "hidden",
  panels: [
    { id: "chatdna_snapshot", component: ChatDNASnapshotCard, order: 10 },
    { id: "language_style", component: LanguageStylePanel, order: 20 }
  ]
}
```

**Why:** ChatDNA Coach analyzes communication style. These panels visualize the analysis.

---

### 4. Career Coach Panels ✅

**Status:** PRODUCTION FEATURE
**Backend API:** `/api/coach/career_coach/panel`
**Panels:**
1. **Career Snapshot** (`career-snapshot-card.tsx`)
   - ProfDNA RR (Professional DNA score)
   - SkillDNA RR (Skills assessment score)
   - Top strengths
   - High curiosity areas
   - Active career intent

2. **Skill Curiosity Map** (`skill-curiosity-map.tsx`)
   - Visualization of skill assessment
   - Curiosity levels per skill

**Configuration:** `persona-panels-config.ts` lines 197-212

**Why:** Career Coach helps with professional development. These panels show career DNA and skills.

---

### 5. Personality Test Coach Panels ✅

**Status:** PRODUCTION FEATURE
**Backend API:** `/api/coach/personality_test_coach/panel`
**Panels:**
1. **Personality Snapshot** (`personality-snapshot-card.tsx`)
   - PsyDNA RR (Psychology DNA score)
   - Top personality strengths
   - High curiosity traits
   - Active intent (discover_self, track_growth, compare_over_time)
   - Assessment progress (X/5 BigFive factors)

2. **Personality Map Visualization** (`personality-map-visualization.tsx`)
   - Visual representation of personality factors
   - Big Five personality dimensions

**Configuration:** `persona-panels-config.ts` lines 218-232

**Why:** Personality Test Coach performs psychological profiling. These panels show results.

---

### 6. Photo Coach Panel ✅

**Status:** PRODUCTION FEATURE
**Backend API:** `/ui/media/list`, `/ui/photo/extract`
**Panel:** Photo Panel (`photo-panel.tsx`)
- Photo upload interface
- Photo refinement tools
- Trait extraction from images
- Photo management

**Configuration:** `persona-panels-config.ts` lines 119-142 (includes both `photo` and `photo_coach` keys)

**Why:** Photo Coach analyzes appearance from photos. Panel provides upload/analysis interface.

---

### 7. PaDNA Coach Panels ✅

**Status:** PRODUCTION FEATURE
**Panels:**
1. **Portrait Render Card** (`portrait-render-card.tsx`)
   - Portrait generation from traits
   - Photorealistic rendering

**Configuration:** `persona-panels-config.ts` lines 148-171 (includes both `padna` and `padna_coach` keys)

**Why:** PaDNA Coach generates visual representations. Panel provides rendering interface.

---

### 8. Life OS Integration ✅

**Status:** PRODUCTION FEATURE
**Variants:**
- `full` - Head Coach (all goals, todos, projects)
- `relationship` - Relationship Coach (filtered for relationship items)
- `hidden` - Specialist coaches (Career, Personality, etc.)

**Implementation:**
```typescript
const lifeOSVariant = getLifeOSVariant(normalized);
const lifeOSPanel = lifeOSVariant !== 'hidden' ? (
  <LifeOSChatPanel userId={context.activeUser} variant={lifeOSVariant} />
) : null;
```

**Why:** Head Coach orchestrates life management. Life OS is the core tool.

---

## API Requirements (Backend Contract)

All coach panel endpoints MUST follow this pattern:

**Endpoint:** `/api/coach/{coach_id}/panel?user_id={user_id}`
**Method:** GET
**Response:** HTTP 200 with JSON containing `snapshot` object

**Example Response:**
```json
{
  "snapshot": {
    "profdna_rr": 50.0,
    "skilldna_rr": 0.0,
    "top_strengths": [],
    "top_curiosity": [],
    "active_intent": "organization_mode"
  }
  // ... additional coach-specific data
}
```

**Required for:**
- ✅ `chatdna_coach`
- ✅ `career_coach`
- ✅ `personality_test_coach`
- ✅ `beliefdna_coach` (if panels exist)
- ✅ `permission_coach` (if panels exist)

---

## Configuration Management

### Adding New Coach Panels

**File:** `web/src/lib/persona-panels-config.ts`

```typescript
new_coach: {
  lifeOS: "hidden", // or "full" or "relationship"
  panels: [
    {
      id: "unique_panel_id",
      component: LazyLoadedComponent,
      order: 10, // Lower = appears higher
      props: { /* optional props */ }
    }
  ]
}
```

**Steps:**
1. Create component in `web/src/components/`
2. Add lazy import at top of `persona-panels-config.ts`
3. Add coach entry to `PERSONA_PANEL_CONFIG`
4. Component will automatically render when coach is active

**DO NOT modify `renderPersonaTools()` switch statement!**

---

## Common Mistakes to Avoid

### ❌ WRONG: Hardcoding Panels

```typescript
// BAD - Don't do this!
switch (normalized) {
  case 'chatdna_coach':
    return <ChatDNASnapshotCard userId={userId} />;
  case 'career_coach':
    return <CareerSnapshotCard userId={userId} />;
  // ... hardcoded for every coach
}
```

### ✅ RIGHT: Using Config System

```typescript
// GOOD - This is the baseline!
const panels = getPersonaPanels(normalized);
const personaPanels = panels.map((panel: PersonaPanelItem) => (
  <PanelBoundary key={panel.id}>
    <Suspense fallback={<div>Loading...</div>}>
      <panel.component {...panel.props} />
    </Suspense>
  </PanelBoundary>
));
```

---

## Testing Requirements

Before considering any changes to coach features:

### Manual Testing Checklist

- [ ] All 9 coaches switch successfully via Coach Catalog
- [ ] ChatDNA Coach shows ChatDNA Profile + Language Style panels
- [ ] Career Coach shows Career Snapshot + Skill Map panels
- [ ] Personality Coach shows Personality Snapshot + Map panels
- [ ] Photo Coach shows Photo Panel
- [ ] PaDNA Coach shows Portrait Render Card
- [ ] Head Coach shows Life OS (full variant)
- [ ] Relationship Coach shows Life OS (relationship variant)
- [ ] All panels load without HTTP 500 errors

### API Testing Checklist

```bash
# All these should return HTTP 200 with JSON
curl http://localhost:8015/api/coach/chatdna_coach/panel?user_id=TEST
curl http://localhost:8015/api/coach/career_coach/panel?user_id=TEST
curl http://localhost:8015/api/coach/personality_test_coach/panel?user_id=TEST
```

---

## Historical Context

### Why This Document Exists

**Date:** 2025-10-12
**Issue:** During coach switching fixes, we accidentally removed coach-specific panels that were already implemented.

**What Happened:**
1. Coach switching was broken (coaches wouldn't switch)
2. During fix, we refactored `renderPersonaTools()` function
3. Initial refactor only restored Photo/PaDNA panels
4. Left placeholder comments: `// These coaches don't have specialized tools yet`
5. **BUT** a complete persona-panels-config system already existed!
6. ChatDNA, Career, and Personality panels were implemented but not connected

**Resolution:**
- Integrated persona-panels-config system into `renderPersonaTools()`
- Restored all coach-specific panels
- Created this baseline document to prevent future regressions

**Lesson:** Always search for existing systems before assuming features don't exist.

---

## Document History

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2025-10-12 | 1.0 | Initial baseline document | Claude Code |

---

## References

### Key Files
- `web/src/lib/persona-panels-config.ts` - Configuration system (400+ lines)
- `web/src/app/page-client.tsx` - Panel rendering (lines 2498-2562)
- `web/src/components/chatdna-snapshot-card.tsx` - ChatDNA panel
- `web/src/components/career/career-snapshot-card.tsx` - Career panel
- `web/src/components/personality/personality-snapshot-card.tsx` - Personality panel
- `web/src/components/photo/photo-panel.tsx` - Photo panel
- `web/src/components/padna/portrait-render-card.tsx` - PaDNA panel

### Related Documentation
- `docs/ADDING_NEW_COACH_PROTOCOL.md` - How to add new coaches
- `web/src/lib/persona-panels-config.ts` - Inline JSDoc comments

---

## Questions?

If you're considering changes that might affect these baseline features, ask yourself:

1. **Does this remove functionality users already have?**
   - If yes → STOP. Discuss with team first.

2. **Does this replace the config system with hardcoding?**
   - If yes → STOP. That's a regression.

3. **Are coach-specific panels still rendering for all coaches?**
   - If no → STOP. You've broken the baseline.

4. **Do you see "doesn't have specialized tools yet" comments?**
   - If yes → Those are OUTDATED. Panels DO exist.

**When in doubt, check this document first!**

---

**This is the baseline. Do not revert without explicit discussion and approval.**
