# Coach Features Documentation Index

This document provides an entry point to all documentation about coach-specific features in the ReDNA system.

---

## 🚨 START HERE: Production Baseline

**[COACH_FEATURES_BASELINE.md](../COACH_FEATURES_BASELINE.md)**

**Read this first!** This document establishes which features are the **production baseline** that should NOT be reverted or removed without explicit discussion.

**Key Points:**
- Lists all 9 coaches and their established panels
- Explains the persona-panels-config architecture
- Documents API requirements
- Provides testing checklist
- Explains why hardcoded switch statements are forbidden

---

## Architecture Documentation

### Persona Panel Configuration System

**[web/src/lib/PERSONA_PANELS_README.md](../web/src/lib/PERSONA_PANELS_README.md)**

Quick reference for the persona-panels-config system:
- How to use the system
- Current coach configurations table
- How to add new panels
- Integration with page-client.tsx

**[web/src/lib/persona-panels-config.ts](../web/src/lib/persona-panels-config.ts)**

The actual configuration file (400+ lines):
- Lazy-loaded component imports
- PERSONA_PANEL_CONFIG master object
- Helper functions (getPersonaPanels, getLifeOSVariant, etc.)
- JSDoc comments explaining each coach's configuration

---

## Coach-Specific Documentation

### Adding New Coaches

**[docs/ADDING_NEW_COACH_PROTOCOL.md](./ADDING_NEW_COACH_PROTOCOL.md)**

Comprehensive protocol for adding a new coach to the system:
- Frontend updates (api.ts, page-client.tsx)
- Backend updates (registry, mode manager, API routes)
- Testing requirements
- Common failure modes and how to debug them

### Individual Coach Panels

| Coach | Panel Components | Configuration |
|-------|-----------------|---------------|
| **ChatDNA Coach** | `chatdna-snapshot-card.tsx`<br>`language-style-panel.tsx` | Lines 238-253 in config |
| **Career Coach** | `career/career-snapshot-card.tsx`<br>`career/skill-curiosity-map.tsx` | Lines 197-212 in config |
| **Personality Test Coach** | `personality/personality-snapshot-card.tsx`<br>`personality/personality-map-visualization.tsx` | Lines 218-232 in config |
| **Photo Coach** | `photo/photo-panel.tsx` | Lines 119-142 in config |
| **PaDNA Coach** | `padna/portrait-render-card.tsx` | Lines 148-171 in config |

---

## Implementation Files

### Frontend (TypeScript/React)

**Key Files:**
- `web/src/app/page-client.tsx` - Main page component
  - Lines 2510-2574: `renderPersonaTools()` function (integration point)
  - Lines 79: Import persona-panels-config
- `web/src/lib/persona-panels-config.ts` - Configuration system
- `web/src/lib/api.ts` - API client
  - Line 3: CORE_API_BASE configuration
  - Lines 2472-2587: CANONICAL_ORDER, CANONICAL_DEFAULTS, PERSONA_ALIASES

**Component Files:**
- `web/src/components/chatdna-snapshot-card.tsx`
- `web/src/components/language-style-panel.tsx`
- `web/src/components/career/career-snapshot-card.tsx`
- `web/src/components/career/skill-curiosity-map.tsx`
- `web/src/components/personality/personality-snapshot-card.tsx`
- `web/src/components/personality/personality-map-visualization.tsx`
- `web/src/components/photo/photo-panel.tsx`
- `web/src/components/padna/portrait-render-card.tsx`

### Backend (Python)

**Key Files:**
- `ReDNACoreDemo/core/coach_registry.yaml` - Coach definitions
- `ReDNACoreDemo/core/coach_mode_manager.py` - Mode validation
- `ReDNACoreDemo/core/api.py` - API routes
- `ReDNACoreDemo/core/ui_readonly.py` - UI roster fallback

---

## API Endpoints

### Coach Panel Endpoints

All coach panel endpoints follow this pattern:

```
GET /api/coach/{coach_id}/panel?user_id={user_id}
```

**Implemented Endpoints:**
- `/api/coach/chatdna_coach/panel` - Returns ChatDNA snapshot
- `/api/coach/career_coach/panel` - Returns career snapshot + skills
- `/api/coach/personality_test_coach/panel` - Returns personality snapshot + map

**Expected Response Format:**
```json
{
  "snapshot": {
    // Coach-specific snapshot data
  }
  // ... additional coach-specific fields
}
```

---

## Testing

### Manual Testing Checklist

From `COACH_FEATURES_BASELINE.md`:

- [ ] All 9 coaches switch successfully via Coach Catalog
- [ ] ChatDNA Coach shows 2 panels
- [ ] Career Coach shows 2 panels
- [ ] Personality Coach shows 2 panels
- [ ] Photo Coach shows Photo Panel
- [ ] PaDNA Coach shows Portrait Render Card
- [ ] Head Coach shows Life OS (full)
- [ ] Relationship Coach shows Life OS (filtered)
- [ ] All panels load without HTTP 500 errors

### API Testing

```bash
# Test all coach panel endpoints
curl http://localhost:8015/api/coach/chatdna_coach/panel?user_id=TEST
curl http://localhost:8015/api/coach/career_coach/panel?user_id=TEST
curl http://localhost:8015/api/coach/personality_test_coach/panel?user_id=TEST
```

All should return HTTP 200 with JSON.

---

## Troubleshooting

### Common Issues

**Issue:** "Coach panels not showing after switching"
- **Check:** Browser cache - do hard refresh (Cmd+Shift+R)
- **Check:** Backend running on correct port (8015, not 8000)
- **Check:** `NEXT_PUBLIC_CORE_API_BASE` environment variable

**Issue:** "HTTP 500 Internal Server Error"
- **Check:** Backend governance module (see CODEX_FIX_GOVERNANCE_ERROR.md)
- **Check:** Backend logs for Python errors
- **Check:** All backend dependencies installed

**Issue:** "Coach appears in catalog but doesn't work when clicked"
- **Root Cause:** Missing from api.ts CANONICAL_ORDER/DEFAULTS/ALIASES
- **Solution:** See ADDING_NEW_COACH_PROTOCOL.md Step 4

---

## Historical Context

### Why Multiple Documentation Files?

**2025-10-12:** During coach switching fixes, coach-specific panels were accidentally removed. Created baseline documentation to prevent future regressions.

**Key Lesson:** Always search for existing systems before assuming features don't exist.

### Evolution of Coach Features

1. **Phase 1:** Basic coach switching (HEAD_COACH only)
2. **Phase 2:** Added Photo/PaDNA specialized panels
3. **Phase 3:** Created persona-panels-config system (declarative)
4. **Phase 4:** Added ChatDNA, Career, Personality panels
5. **Phase 5:** Integrated Coach Catalog for all coaches
6. **Current:** Established production baseline (this documentation)

---

## For AI Assistants (Claude/Codex)

### Before Making Changes

1. **Read** [COACH_FEATURES_BASELINE.md](../COACH_FEATURES_BASELINE.md) first
2. **Check** if the change removes existing functionality
3. **Verify** the change doesn't replace config system with hardcoding
4. **Test** all coaches after making changes

### Red Flags (Stop and Ask)

- Removing panels from persona-panels-config
- Adding hardcoded switch statements to renderPersonaTools
- Comments like "// These coaches don't have specialized tools yet"
- Reverting to commits before 2025-10-12

### Safe Changes

- Adding new coaches to persona-panels-config
- Adding new panels to existing coaches
- Updating panel props/configuration
- Improving panel UI/UX
- Adding feature flags to panels

---

## Contributing

### Adding Documentation

When adding new coach features:

1. Update `COACH_FEATURES_BASELINE.md` if adding baseline features
2. Update `persona-panels-config.ts` with inline JSDoc comments
3. Update this index if creating new documentation files
4. Add tests to the testing checklist

### Documentation Standards

- Use ✅ ❌ for clear pass/fail indicators
- Include code examples for complex concepts
- Reference line numbers for key files
- Explain WHY not just WHAT

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-12 | 1.0 | Initial documentation structure |

---

## Quick Links

- [Production Baseline](../COACH_FEATURES_BASELINE.md) ⚠️ **Read First**
- [Persona Panels README](../web/src/lib/PERSONA_PANELS_README.md)
- [Adding New Coach Protocol](./ADDING_NEW_COACH_PROTOCOL.md)
- [Coach Registry (YAML)](../ReDNACoreDemo/core/coach_registry.yaml)
- [Persona Config (TS)](../web/src/lib/persona-panels-config.ts)
- [Page Client (TSX)](../web/src/app/page-client.tsx)

---

**Last Updated:** 2025-10-12
**Maintained By:** Engineering Team
