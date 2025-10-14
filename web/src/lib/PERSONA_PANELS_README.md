# Persona Panels Configuration System

**⚠️ PRODUCTION BASELINE - DO NOT REMOVE OR REPLACE**

This system is documented as the established baseline in:
👉 **`/COACH_FEATURES_BASELINE.md`** at repository root

---

## Quick Reference

This configuration system defines which panels appear in the right pane for each coach.

### Usage

```typescript
import { getPersonaPanels, getLifeOSVariant } from './persona-panels-config';

// Get panels for a coach
const panels = getPersonaPanels('chatdna_coach');

// Get Life OS variant
const variant = getLifeOSVariant('head_coach'); // returns "full"
```

### Current Coach Configurations

| Coach | Life OS | Specialized Panels |
|-------|---------|-------------------|
| Head Coach | Full | None (Life OS is the main tool) |
| Relationship Coach | Relationship | None (filtered Life OS) |
| Career Coach | Hidden | Career Snapshot + Skill Map |
| Personality Test Coach | Hidden | Personality Snapshot + Map |
| ChatDNA Coach | Hidden | ChatDNA Profile + Language Style |
| Photo Coach | Hidden | Photo Panel |
| PaDNA Coach | Hidden | Portrait Render Card |
| BeliefDNA Coach | Hidden | (Inline panels) |
| Permission Coach | Hidden | (DynamicCoachPanes) |

---

## Architecture

**DO NOT replace this system with hardcoded switch statements!**

This system provides:
- ✅ Declarative configuration
- ✅ Lazy loading for performance
- ✅ User customization support (future)
- ✅ Feature flag support
- ✅ Easy maintenance

### Adding a New Coach Panel

1. **Create component** in `/web/src/components/`
2. **Add lazy import** at top of this file
3. **Add configuration** to `PERSONA_PANEL_CONFIG`:

```typescript
new_coach: {
  lifeOS: "hidden", // or "full" or "relationship"
  panels: [
    {
      id: "my_panel",
      component: MyLazyLoadedPanel,
      order: 10,
      props: { /* optional */ }
    }
  ]
}
```

4. **Done!** Panel will automatically render when coach is active.

---

## Integration Point

This config is consumed by `page-client.tsx` in the `renderPersonaTools()` function:

```typescript
// Get panels from config
const panels = getPersonaPanels(normalized);

// Render each panel
const personaPanels = panels.map((panel) => (
  <PanelBoundary key={panel.id}>
    <Suspense fallback={<div>Loading...</div>}>
      <panel.component {...panel.props} />
    </Suspense>
  </PanelBoundary>
));
```

**This is the established pattern. Do not replace with switch statements.**

---

## See Also

- `/COACH_FEATURES_BASELINE.md` - Full baseline documentation
- `/docs/ADDING_NEW_COACH_PROTOCOL.md` - How to add new coaches
- `page-client.tsx` - Where this config is consumed
