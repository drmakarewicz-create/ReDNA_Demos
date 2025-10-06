# LEFT PANE SANCTITY RULE

## Core Principle

**THE LEFT PANE IS SACRED. DO NOT TOUCH IT.**

The left chat pane took extensive effort to stabilize. It is now working perfectly with:
- ✅ No overlap between transcript and composer
- ✅ Smooth scrolling without blinking
- ✅ Stable layout across all interactions
- ✅ Proper height calculations

## IRON-CLAD RULES

### ❌ NEVER DO (Without Extensive Review & Approval)

1. **DO NOT modify layout-switcher.tsx LEFT column section**
   - The `<section>` wrapper with `overflow-hidden`
   - The flex column structure inside it
   - Any CSS classes on left pane elements

2. **DO NOT change transcript-panel.tsx core layout**
   - The `h-full max-h-full min-h-0` height classes
   - The `overflow-hidden` on the section element
   - The virtualization disable logic (`shouldVirtualize = !fillHeight`)
   - The scroll container's `overflow-y-auto`

3. **DO NOT modify page-client.tsx chat structure**
   - The `renderPersonaCenter()` chat interface
   - The toolbar wrapper with `shrink-0`
   - The transcript wrapper with `flex-1 min-h-0`
   - The composer placement

4. **DO NOT add scroll containers to the left pane**
   - Only ONE scroll container allowed: the transcript's internal scroll div
   - No `overflow-auto` on any wrapper elements
   - No `overflow-y-scroll` anywhere in the left column

5. **DO NOT change the composer measurement**
   - The `--composer-h` CSS variable must stay scoped to left pane
   - The ResizeObserver logic must not be touched
   - The padding calculations based on `--composer-h` are sacred

6. **DO NOT re-enable virtualization in focused mode**
   - `shouldVirtualize = !fillHeight` is the formula
   - This prevents blinking and doubling
   - No exceptions

7. **DO NOT use percentage-based heights**
   - Keep `h-full` not `flex-1` on TranscriptPanel
   - Percentage heights cause recalculation cycles
   - Stick with the working formula

8. **DO NOT add new components to the left pane**
   - All new features go in the RIGHT pane
   - The left pane structure is frozen
   - Chat interface is complete as-is

## ✅ APPROVED: Innovation in the RIGHT Pane

### All New Features Go Here

The right pane is the ONLY area for new development:

1. **Add new persona-specific tools**
   ```tsx
   function renderPersonaTools(personaKey, context) {
     switch (personaKey) {
       case 'new_coach':
         return <NewCoachToolPanel />;  // ✅ APPROVED
     }
   }
   ```

2. **Add new support panels**
   ```tsx
   <CoachToolsPane>
     <NewFeaturePanel />  // ✅ APPROVED
     <AnotherToolPanel /> // ✅ APPROVED
   </CoachToolsPane>
   ```

3. **Modify existing right pane components**
   - PhotoPanel: ✅ APPROVED
   - AvatarRenderPanel: ✅ APPROVED
   - ObservationSummary: ✅ APPROVED
   - CoachAsksPanel: ✅ APPROVED
   - Any new panels: ✅ APPROVED

4. **Change right pane layout**
   - Tabs, accordions, collapsible sections: ✅ APPROVED
   - Drag-and-drop reordering: ✅ APPROVED
   - Split into sub-panes: ✅ APPROVED
   - Anything that doesn't affect the left: ✅ APPROVED

## WARNING TRIGGERS

If you're considering ANY change that involves:

### 🚨 STOP IMMEDIATELY IF:
- Modifying `layout-switcher.tsx` left section
- Changing `transcript-panel.tsx` height/overflow
- Adding scroll to left pane ancestors
- Touching composer measurement logic
- Re-enabling virtualization
- Changing flex layout structure on left
- Adding new components to centerContent
- Modifying the grid column configuration for left

### ⚠️ EXTREME CAUTION IF:
- Updating ChatComposer component
- Changing HeadCoachToolbar
- Modifying TranscriptPanel props
- Touching any CSS class in the left column
- Changing how messages render
- Updating scroll behavior
- Adding animations/transitions to left pane

## Before Touching the Left Pane

### Required Checklist (ALL must be YES):

- [ ] Is this absolutely necessary? (Can't be done in right pane?)
- [ ] Have you reviewed FOCUSED_CHAT_LAYOUT_SOLUTION.md?
- [ ] Have you reviewed TWO_PANE_LAYOUT_IMPLEMENTATION.md?
- [ ] Do you understand why virtualization is disabled?
- [ ] Do you understand the overflow-hidden requirements?
- [ ] Do you understand the min-h-0 necessity?
- [ ] Have you identified ALL potential side effects?
- [ ] Have you created a rollback plan?
- [ ] Have you tested the change won't cause blinking?
- [ ] Have you tested the change won't cause overlap?
- [ ] Have you verified scroll still works correctly?
- [ ] Have you tested on mobile Safari?
- [ ] Are you prepared to revert immediately if issues arise?

### If Absolutely Necessary:

1. **Document the reason** in a new markdown file
2. **Create a feature flag** to toggle the change
3. **Make changes incremental** - one tiny change at a time
4. **Test after EACH change** - verify no regression
5. **Have rollback ready** - can revert in seconds
6. **Get approval** before merging

## The Painful Journey (Never Forget)

We went through MULTIPLE cycles of:
1. Fixing overlap → Caused blinking
2. Fixing blinking → Caused overlap
3. Trying virtualization → Caused doubling
4. Using flex-1 → Caused instability
5. Adding overflow → Buried composer
6. Changing heights → Broke scroll

**It took 20+ iterations to find the working formula.**

## The Working Formula (DO NOT CHANGE)

```tsx
// layout-switcher.tsx - LEFT COLUMN
<section className="flex flex-col min-h-0 overflow-hidden pl-4 sm:pl-6">
  <div className="flex-1 min-h-0 pt-4">
    {centerContent}
  </div>
  <div className="shrink-0 pt-4 pb-4">
    {composer}
  </div>
</section>

// page-client.tsx - CHAT STRUCTURE
<>
  <div className={fillHeightMode ? "shrink-0" : ""}>
    <HeadCoachToolbar />
  </div>
  <div className={fillHeightMode ? "flex-1 min-h-0" : ""}>
    <TranscriptPanel fillHeight={fillHeightMode} />
  </div>
</>

// transcript-panel.tsx - HEIGHT & SCROLL
const shouldVirtualize = !fillHeight;
const heightClass = fillHeight ? 'h-full max-h-full' : 'h-[60vh]';

<section className={`flex flex-col ${heightClass} min-h-0 overflow-hidden ...`}>
  <header className="shrink-0">...</header>
  <div className="flex-1 min-h-0 overflow-y-auto ...">
    {/* Messages */}
  </div>
</section>
```

## Acceptance Test (Run After ANY Left Pane Change)

```bash
# Manual testing checklist:
1. Send multiple rapid messages → No overlap
2. Scroll up and down → No blinking
3. Resize window → Layout stable
4. Grow composer (multiline) → No overlap
5. Toggle notices → Layout stable
6. Switch personas → Chat works for all
7. Test on mobile → Scroll feels native
8. Check inspector → Only transcript div has overflow-y-auto
9. Verify → document.scrollingElement.scrollHeight === clientHeight
```

## Summary

### DO:
✅ **Innovate freely in the RIGHT pane**
✅ **Add new features to CoachToolsPane**
✅ **Create new persona tools**
✅ **Enhance existing right pane components**
✅ **Experiment with right pane layouts**

### DON'T:
❌ **Touch the left pane structure**
❌ **Modify chat layout**
❌ **Change overflow/height rules**
❌ **Add scroll containers to left**
❌ **Re-enable virtualization**
❌ **Touch composer measurement**

## Final Word

**When in doubt, don't touch the left pane.**

If a feature "needs" left pane changes, reconsider the feature or find a way to implement it in the right pane. The left pane is a black box that works perfectly. Keep it that way.

---

*This document is a living reminder of the effort it took to stabilize the chat interface. Respect the left pane's sanctity.*
