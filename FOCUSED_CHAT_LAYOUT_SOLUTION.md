# Focused Chat Layout Solution

## Problem
Creating a ChatGPT/Claude-style fixed layout with:
- Header fixed at top
- Transcript area that scrolls internally and fills available space
- Composer fixed at bottom
- NO overlap between transcript and composer
- NO blinking or visual artifacts

## Solution Formula

### Key Changes Made

#### 1. **layout-switcher.tsx** - Simplified Layout Container
```tsx
function FocusedChatLayout({ header, centerContent, composer, modals, notices }) {
  const dockedComposer = isValidElement(composer)
    ? cloneElement(composer, { docked: true })
    : composer;

  return (
    <div className="flex h-dvh flex-col bg-hc-background">
      {/* Header: fixed */}
      <div className="shrink-0">{header}</div>

      {/* Main chat area: fills remaining height */}
      <main className="flex flex-1 min-h-0 flex-col items-center">
        <div className="flex w-full max-w-4xl flex-1 min-h-0 flex-col px-4 sm:px-6">
          {/* Notices */}
          {notices && <div className="shrink-0 pt-4">{notices}</div>}

          {/* All center content (toolbar, transcript, etc) */}
          <div className="flex-1 min-h-0 pt-4">
            {centerContent}
          </div>

          {/* Composer: fixed at bottom */}
          <div className="shrink-0 pt-4 pb-4">
            {dockedComposer}
          </div>
        </div>
      </main>

      {modals}
    </div>
  );
}
```

**Key CSS Classes:**
- Root: `flex h-dvh flex-col` - Full viewport height flex column
- Main: `flex flex-1 min-h-0 flex-col` - Fills remaining space, can shrink
- Center content wrapper: `flex-1 min-h-0` - Grows to fill space
- Composer wrapper: `shrink-0` - Fixed height, doesn't grow/shrink

#### 2. **page-client.tsx** - Conditional Wrapper Classes
```tsx
// Add useFeatureFlags
import { useFeatureFlags } from '../lib/feature-flags';

// In component
const { flags } = useFeatureFlags();

// Update centerContentSection wrapper
const centerContentSection = (
  <ClientOnly fallback={...}>
    <div className={flags.focusedChatLayout ? "flex flex-col h-full min-h-0 space-y-6" : "flex-1 space-y-6"}>
      {renderPersonaCenter(...)}
    </div>
  </ClientOnly>
);

// Add fillHeightMode to PersonaCenterContext
interface PersonaCenterContext {
  // ... other props
  fillHeightMode: boolean;
}

// In personaContext useMemo
fillHeightMode: flags.focusedChatLayout,

// Update renderPersonaCenter default case
default:
  return (
    <>
      <div className={context.fillHeightMode ? "shrink-0" : ""}>
        <HeadCoachToolbar {...props} />
      </div>
      <div className={context.fillHeightMode ? "flex-1 min-h-0" : ""}>
        <PanelBoundary resetKeys={[context.activeUser]} onRetry={context.retryTranscript}>
          <TranscriptPanel
            {...props}
            fillHeight={context.fillHeightMode}
          />
        </PanelBoundary>
      </div>
      {/* Hide shared panels in focused mode to save space */}
      {!context.fillHeightMode && renderSharedSupportPanels(context)}
    </>
  );
```

**Key Changes:**
- Wrapper uses `flex flex-col h-full min-h-0` in focused mode (instead of `flex-1`)
- Toolbar wrapper: `shrink-0` in focused mode - fixed height
- TranscriptPanel wrapper: `flex-1 min-h-0` in focused mode - grows to fill space
- Shared panels (ObservationSummary, CoachAsks, etc.) hidden in focused mode
- Pass `fillHeight={context.fillHeightMode}` to TranscriptPanel

#### 3. **transcript-panel.tsx** - Disable Virtualization & Fix Height
```tsx
// Disable virtualization in fillHeight mode to prevent blinking
const shouldVirtualize = !fillHeight;

const virtualizer = useVirtualizer({
  count: isHydrated && shouldVirtualize ? displayEntries.length : 0,
  // ... other config
});

const virtualItems = isHydrated && shouldVirtualize ? virtualizer.getVirtualItems() : [];

// Height class
const heightClass = fillHeight ? 'h-full max-h-full' : 'h-[60vh]';

// Section element
<section className={`flex flex-col ${heightClass} min-h-0 overflow-hidden ...`}>

// Render items
{isHydrated && shouldVirtualize ? (
  // Virtualized rendering
  <div style={{ height: `${virtualizer.getTotalSize()}px`, ... }}>
    {virtualItems.map((virtualItem) => renderTranscriptItem(...))}
  </div>
) : isHydrated ? (
  // Non-virtualized rendering (used in fillHeight mode)
  <div className="flex flex-col">
    {displayEntries.map((_, index) => renderTranscriptItem(index, { isVirtual: false }))}
  </div>
) : (
  // Loading state
  ...
)}
```

**Key Changes:**
- `shouldVirtualize = !fillHeight` - Disables virtualization in focused mode
- Height: `h-full max-h-full` in focused mode (NOT `flex-1`)
- Added `min-h-0` to section to allow flex shrinking
- Non-virtualized rendering path for stable display without blinking

## Why This Works

### The Layout Hierarchy
```
div (h-dvh)                                    ← Full viewport height
  ├─ header (shrink-0)                         ← Fixed
  ├─ main (flex-1 min-h-0)                     ← Fills remaining space
  │   └─ wrapper (flex-1 min-h-0)              ← Can shrink
  │       ├─ notices (shrink-0)                ← Fixed
  │       ├─ centerContent (flex-1 min-h-0)    ← flex flex-col h-full
  │       │   ├─ toolbar (shrink-0)            ← Fixed
  │       │   └─ transcript wrapper (flex-1)   ← Grows to fill
  │       │       └─ TranscriptPanel (h-full)  ← 100% of parent
  │       │           ├─ header (shrink-0)
  │       │           └─ scroll (flex-1)       ← Scrolls internally
  │       └─ composer (shrink-0)               ← Fixed at bottom
  └─ modals
```

### Critical CSS Combinations

1. **`flex-1 min-h-0`** - Allows flex items to shrink below content size
2. **`h-full` (NOT `flex-1`)** on TranscriptPanel - Takes 100% of parent height
3. **`max-h-full`** on TranscriptPanel - Prevents exceeding container
4. **`shrink-0`** on toolbar and composer - Prevents them from shrinking
5. **No `overflow-hidden` on parent wrappers** - Allows scroll to work

### Why Virtualization Was Disabled

Virtual scrolling with `transform: translateY()` caused:
- Blinking during scroll
- Doubling of text boxes
- Visual artifacts with dynamic heights

**Trade-off:** Slightly less performant with 100+ messages, but:
- Typical chat conversations are <50 messages
- Stable, predictable rendering
- No visual artifacts
- Better UX for chat interface

## What NOT to Do (These Break the Layout)

❌ **Don't** add `overflow-hidden` to the transcript wrapper
❌ **Don't** use `flex-1` on TranscriptPanel (use `h-full` instead)
❌ **Don't** remove `min-h-0` from flex containers
❌ **Don't** enable virtualization in fillHeight mode
❌ **Don't** add `display: contents` or `will-change` / `contain` CSS
❌ **Don't** try to strip wrapper classes with React cloning
❌ **Don't** show shared panels in focused mode (they take space)

## Testing Checklist

✅ No overlap between transcript and composer
✅ Transcript scrolls smoothly
✅ Can reach latest message
✅ "Jump to latest" button appears when scrolled up
✅ No blinking or visual artifacts
✅ No doubling of messages
✅ Composer stays fixed at bottom
✅ Layout stable during scroll
✅ Works with new messages arriving

## Feature Flag

The layout is controlled by the `focusedChatLayout` feature flag in `lib/feature-flags.ts`:
```tsx
export const DEFAULT_FLAGS: FeatureFlags = {
  focusedChatLayout: true
};
```

Set to `false` to revert to classic full-page scrolling layout.
