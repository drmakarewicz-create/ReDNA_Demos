# Development Rules & Principles

## 🚨 RULE #1: LEFT PANE SANCTITY

**The left chat pane is SACRED. DO NOT TOUCH IT.**

### Quick Decision Tree

```
Do I need to add a feature?
  │
  ├─→ Can it go in the RIGHT pane?
  │     └─→ YES → ✅ Go ahead! Innovate freely.
  │
  └─→ Does it REQUIRE left pane changes?
        └─→ Probably not. Reconsider the approach.
            │
            └─→ Still sure?
                  └─→ Read LEFT_PANE_SANCTITY_RULE.md
                      Get approval. Proceed with extreme caution.
```

### Where to Put New Features

| Feature Type | Location | Approved? |
|--------------|----------|-----------|
| New persona tool (upload, render, etc.) | RIGHT pane via `renderPersonaTools()` | ✅ YES |
| New support panel | RIGHT pane in `CoachToolsPane` | ✅ YES |
| Enhanced UI for existing right panel | RIGHT pane component | ✅ YES |
| Tabs, accordions, sub-panes | RIGHT pane | ✅ YES |
| Chat interface modification | LEFT pane | ⚠️ EXTREME CAUTION |
| Transcript display changes | LEFT pane | ⚠️ EXTREME CAUTION |
| Composer changes | LEFT pane | ⚠️ EXTREME CAUTION |

### Files with Left Pane Code (Protected)

❌ **Modify with EXTREME caution:**
- `web/src/components/layout-switcher.tsx` - Left column section
- `web/src/components/transcript-panel.tsx` - Core layout
- `web/src/app/page-client.tsx` - `renderPersonaCenter()` function

✅ **Safe to modify:**
- `web/src/components/coach-tools-pane.tsx` - Right pane wrapper
- `web/src/app/page-client.tsx` - `renderPersonaTools()` function
- Any right pane component (PhotoPanel, AvatarRenderPanel, etc.)

## Documentation Index

### Before ANY Development
1. Read this file (DEVELOPMENT_RULES.md)

### For Left Pane Changes (STOP!)
1. [LEFT_PANE_SANCTITY_RULE.md](LEFT_PANE_SANCTITY_RULE.md) - WHY the left pane is sacred
2. [FOCUSED_CHAT_LAYOUT_SOLUTION.md](FOCUSED_CHAT_LAYOUT_SOLUTION.md) - HOW the left pane works
3. [TWO_PANE_LAYOUT_IMPLEMENTATION.md](TWO_PANE_LAYOUT_IMPLEMENTATION.md) - Architecture overview

### For Right Pane Development (Go for it!)
1. [TWO_PANE_LAYOUT_IMPLEMENTATION.md](TWO_PANE_LAYOUT_IMPLEMENTATION.md) - See "CoachToolsPane" section

## Quick Reference

### Left Pane Formula (DO NOT CHANGE)
```tsx
// Grid column - overflow-hidden!
<section className="flex flex-col min-h-0 overflow-hidden">
  <div className="flex-1 min-h-0">
    {centerContent}  // Chat interface
  </div>
  <div className="shrink-0">
    {composer}  // Fixed at bottom
  </div>
</section>

// TranscriptPanel height - h-full NOT flex-1!
const heightClass = fillHeight ? 'h-full max-h-full' : 'h-[60vh]';

// Virtualization - DISABLED in focused mode!
const shouldVirtualize = !fillHeight;
```

### Right Pane (Innovate Freely)
```tsx
// Add persona-specific tools
function renderPersonaTools(personaKey, context) {
  switch (personaKey) {
    case 'my_new_coach':
      return <MyNewCoachPanel />;  // ✅ APPROVED!
  }
}

// Add to CoachToolsPane
<CoachToolsPane title="Coach Tools">
  <PersonaRail />
  <UnabridgedPanel />
  {renderPersonaTools(...)}  // Your tools here!
  {renderSharedSupportPanels(...)}
</CoachToolsPane>
```

## Commit Message Guidelines

When committing changes, be EXPLICIT about which pane:

✅ **Good commit messages:**
- `feat(right-pane): Add new photo upload panel`
- `fix(right-pane): Improve avatar rendering layout`
- `enhance(tools): Add collapsible sections to coach tools`

⚠️ **Concerning commit messages (requires justification):**
- `fix(left-pane): Adjust transcript height` ← WHY? Document!
- `refactor(chat): Update composer layout` ← STOP! Get approval!
- `feat: Add new component to chat interface` ← Which pane?!

## Code Review Checklist

### For ANY PR touching left pane files:
- [ ] Has the change been documented with WHY?
- [ ] Is there a rollback plan?
- [ ] Has testing been done for: overlap, blinking, scroll?
- [ ] Can this be done in the right pane instead?
- [ ] Has approval been obtained from project lead?

### For right pane changes (standard review):
- [ ] Does it follow existing patterns?
- [ ] Is it responsive (mobile-friendly)?
- [ ] Does it maintain independent scrolling?

## Emergency Rollback

If left pane breaks in production:

```tsx
// In web/src/lib/feature-flags.ts
export const DEFAULT_FLAGS: FeatureFlags = {
  focusedChatLayout: false  // ← Set to false to revert to classic layout
};
```

This immediately reverts to the old working layout while you fix the issue.

## Summary

### The Golden Rule
> **When in doubt, don't touch the left pane.**
> **All innovation happens in the right pane.**

### Remember
- The left pane took 20+ iterations to stabilize
- It works perfectly now
- There's no need to touch it
- Right pane has unlimited potential for features
- Keep the chat sacred, innovate in the tools

---

*Updated: After stabilizing two-pane layout*
*Next review: When considering ANY left pane change*
