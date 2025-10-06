# Two-Pane Focused Chat Layout Implementation

## Overview
Implemented a ChatGPT/Claude-style two-pane layout:
- **LEFT PANE**: Head Coach chat interface (stable, black box)
- **RIGHT PANE**: Persona-specific tools and support panels (independent scroll)

## Architecture

### Layout Hierarchy
```
div (h-dvh overflow-hidden)                    ← Page root, no scroll
  ├─ header (shrink-0)                         ← Fixed header
  ├─ main (grid, flex-1 min-h-0)               ← CSS Grid work area
  │   ├─ section (LEFT, overflow-hidden)       ← Chat pane column
  │   │   └─ centerContent                     ← Toolbar + Transcript
  │   │       ├─ notices (shrink-0)
  │   │       ├─ content (flex-1 min-h-0)
  │   │       └─ composer (shrink-0)
  │   │
  │   └─ aside (RIGHT, overflow-auto)          ← Tools pane column
  │       └─ CoachToolsPane                    ← Support panels, tools
  │           ├─ PersonaRail
  │           ├─ UnabridgedPanel
  │           ├─ ObservationSummary
  │           ├─ CoachAsksPanel
  │           └─ NudgeInboxPanel
  └─ modals (overlay)
```

### Grid Configuration
```css
grid-cols-1                                  /* Mobile: single column */
lg:grid-cols-[minmax(320px,480px)_minmax(0,1fr)]  /* Desktop: 320-480px left, rest right */
gap-x-4                                      /* 1rem gap between columns */
```

## Key Components

### 1. HeadCoachChatPane (Black Box)
**File**: `web/src/components/head-coach-chat-pane.tsx`

**Purpose**: Encapsulates the entire chat interface with scoped measurements

**Props**:
- `toolbar`: ReactNode - Top fixed toolbar
- `transcript`: ReactNode - Scrollable transcript area
- `composer`: ReactNode - Bottom fixed composer
- `notices`: ReactNode (optional) - Notices above content

**Critical Features**:
- Sets `--composer-h` CSS variable SCOPED to this component only
- Measures composer with ResizeObserver
- Internal flex column layout: toolbar (shrink-0) → transcript (flex-1) → composer (shrink-0)
- Does NOT add any scroll containers

### 2. CoachToolsPane (Right Pane)
**File**: `web/src/components/coach-tools-pane.tsx`

**Purpose**: Independent scrolling container for tools and panels

**Props**:
- `children`: ReactNode - Tool/panel components
- `title`: string (optional) - Pane title

**Critical Features**:
- ONE scroll container: `overflow-auto overscroll-contain`
- Stable scrollbar gutter: `[scrollbar-gutter:stable_both-edges]`
- Sticky header support for long content
- Cannot affect left pane's `--composer-h`

### 3. FocusedChatLayout (Grid Container)
**File**: `web/src/components/layout-switcher.tsx`

**Updates**:
```tsx
// Work area: 2-column grid
<main className="grid flex-1 min-h-0 overflow-hidden overscroll-none
                 grid-cols-1 lg:grid-cols-[minmax(320px,480px)_minmax(0,1fr)]
                 gap-x-4 px-4 sm:px-6">

  {/* LEFT: overflow-hidden (NO scroll here) */}
  <section className="min-h-0 overflow-hidden pt-4">
    {/* centerContent with composer */}
  </section>

  {/* RIGHT: overflow-auto (independent scroll) */}
  <aside className="min-h-0 overflow-auto overscroll-contain
                    [scrollbar-gutter:stable_both-edges]
                    hidden lg:block pt-4">
    {sidebar}  {/* CoachToolsPane */}
  </aside>
</main>
```

### 4. page-client.tsx Updates
**File**: `web/src/app/page-client.tsx`

**Changes**:
1. Import `CoachToolsPane`
2. Update `sidebarSection` to use `CoachToolsPane` in focused mode
3. Add `renderSharedSupportPanels` to right pane
4. Keep classic layout unchanged for backward compatibility

```tsx
const sidebarSection = flags.focusedChatLayout ? (
  <CoachToolsPane title="Coach Tools">
    <PersonaRail ... />
    <UnabridgedPanel ... />
    {/* Support panels moved from chat to right pane */}
    {renderSharedSupportPanels(personaContext)}
  </CoachToolsPane>
) : (
  /* Classic sidebar layout */
);
```

## Critical Rules (DO NOT VIOLATE)

### LEFT PANE (Chat) ✅
1. **overflow-hidden** on column wrapper - ONLY transcript scrolls
2. **min-h-0** on all flex containers in the path
3. **h-full max-h-full** on TranscriptPanel (NOT flex-1)
4. **Virtualization DISABLED** in focused mode
5. **--composer-h** scoped to HeadCoachChatPane root only
6. **No nested scroll** containers

### RIGHT PANE (Tools) ✅
1. **overflow-auto** on aside element - ONE scroll container
2. **No position:fixed** - use position:sticky for headers
3. **No touching --composer-h** from right pane
4. **Avoid nested scrollers** - all tools in one container
5. **Independent** - cannot affect left pane layout

### GRID CONTAINER ✅
1. **overflow-hidden** on main grid - prevent page scroll
2. **min-h-0** on grid track - allow shrinking
3. **Grid, not flex** - more stable for two columns
4. **Responsive** - collapses to single column at <lg

## Responsive Behavior

### Desktop (≥1024px)
- Two-column grid
- Chat pane: 320-480px wide
- Tools pane: fills remaining space
- Both visible simultaneously

### Mobile/Tablet (<1024px)
- Single column: `grid-cols-1`
- Chat pane: full width
- Tools pane: `hidden lg:block` (hidden on small screens)
- **Future**: Can add tab switching (Chat | Tools)

## Acceptance Criteria

### ✅ Must Pass Before Merge

1. **No scroll bleed**
   ```js
   document.scrollingElement.scrollHeight === document.scrollingElement.clientHeight
   ```

2. **Left isolation**
   ```js
   getComputedStyle(leftColumn).overflowY === 'hidden'
   // Only transcript div returns 'auto'
   ```

3. **Composer always visible**
   - Last message never overlaps composer
   - Works during rapid messaging
   - Works when composer grows (multiline)
   - Works with notices toggling
   - Works with window resize

4. **Right pane independence**
   - Adding 2000px tall content scrolls only right pane
   - Long JSON editors don't affect left pane
   - Image rendering doesn't cause layout shift

5. **Mobile Safari**
   - Rotate device: layout stable
   - Show/hide keyboard: chat pinned
   - Momentum scroll feels native

6. **Classic mode still works**
   - Setting `focusedChatLayout: false` reverts to original layout

## What We Preserved

From the original stable chat layout:
- ✅ No overlap between transcript and composer
- ✅ Transcript scrolls smoothly
- ✅ Can reach latest message
- ✅ "Jump to latest" button works
- ✅ No blinking or visual artifacts
- ✅ No doubling of messages
- ✅ Composer fixed at bottom
- ✅ Stable during scroll and new messages

## What We Added

New capabilities with two-pane layout:
- ✅ Independent tools pane for persona-specific features
- ✅ Support panels (ObservationSummary, CoachAsks, etc.) moved to right
- ✅ Chat always visible on left
- ✅ More screen real estate for both chat and tools
- ✅ Responsive design (collapses on mobile)
- ✅ Extensible architecture for future tools

## Common Pitfalls (How Layouts Regress)

### ❌ DON'T:
1. Add `overflow-auto` to left column wrapper
   - **Why**: Creates page scroll, buries composer
   - **Fix**: Keep `overflow-hidden`

2. Use `flex-1` on TranscriptPanel in focused mode
   - **Why**: Unstable height calculations
   - **Fix**: Keep `h-full max-h-full`

3. Re-enable virtualization with transforms
   - **Why**: Causes flicker and duplication
   - **Fix**: Keep `shouldVirtualize = !fillHeight`

4. Set `--composer-h` globally
   - **Why**: Right pane tools resize chat
   - **Fix**: Scope to HeadCoachChatPane root

5. Create nested scroll in right pane
   - **Why**: Trackpad feels broken
   - **Fix**: ONE overflow-auto container

6. Use `position:fixed` in right pane
   - **Why**: Breaks scroll isolation
   - **Fix**: Use `position:sticky` for headers

## Future Enhancements (Optional)

### Resizable Splitter
```tsx
// Add CSS variable for left width
grid-cols-[minmax(320px,var(--left-w,420px))_minmax(0,1fr)]

// Add drag handle to resize
// Persist to localStorage
```

### Mobile Tabs
```tsx
// At <lg: show tabs instead of hiding
<Tabs>
  <Tab>Chat</Tab>
  <Tab>Tools</Tab>
</Tabs>

// Hide inactive pane with `hidden` (not `display:contents`)
```

### Persona-Specific Right Pane
```tsx
function renderPersonaTools(personaKey: string, context) {
  switch (personaKey) {
    case 'photo':
      return <PhotoUploadPanel />;
    case 'rendering':
      return <AvatarRenderPanel />;
    default:
      return <DefaultToolsPanel />;
  }
}
```

## Testing Checklist

- [ ] Chat pane: no scroll except transcript
- [ ] Right pane: scrolls independently
- [ ] Composer always visible
- [ ] No overlap between panes
- [ ] No blinking or artifacts
- [ ] Responsive collapse works
- [ ] Classic mode still works
- [ ] Mobile Safari tested
- [ ] Long content in right pane tested
- [ ] Rapid messaging tested

## Files Modified

1. **NEW**: `web/src/components/head-coach-chat-pane.tsx`
2. **NEW**: `web/src/components/coach-tools-pane.tsx`
3. **MODIFIED**: `web/src/components/layout-switcher.tsx`
4. **MODIFIED**: `web/src/app/page-client.tsx`
5. **PRESERVED**: `web/src/components/transcript-panel.tsx` (no changes)

## Rollback Plan

If issues arise:
1. Set `focusedChatLayout: false` in `lib/feature-flags.ts`
2. System reverts to classic layout
3. All changes are behind feature flag
