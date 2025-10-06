# Layout Switcher Implementation Guide

**Status:** ✅ Implemented and Ready
**Date:** 2025-10-05
**Feature Flag:** `focusedChatLayout`

## Overview

The Head Coach UI now supports two layout modes with easy rollback capability:

1. **Classic Layout (Default)** - Original scrolling page with fixed composer at bottom
2. **Focused Chat Layout** - ChatGPT/Claude-style fixed-height chat window

## How to Switch Layouts

### Option 1: Settings UI (Recommended)

1. Open Head Coach at http://localhost:3001
2. Click **Settings** button (top right)
3. Scroll to **Developer flags** section
4. Toggle **"Focused chat layout (ChatGPT-style)"**
5. Change applies instantly

### Option 2: Environment Variable

Add to `.env.local`:
```bash
NEXT_PUBLIC_FLAGS=focusedChatLayout
```

### Option 3: Browser Console

```javascript
// Enable focused chat layout
localStorage.setItem('_hc_flags', JSON.stringify({ focusedChatLayout: true }));
location.reload();

// Disable (revert to classic)
localStorage.setItem('_hc_flags', JSON.stringify({ focusedChatLayout: false }));
location.reload();
```

## Quick Rollback

**If something goes wrong:**

1. Open Settings
2. Find "Focused chat layout" toggle
3. Turn it **OFF**
4. Page instantly reverts to classic layout

**Emergency rollback (if UI is broken):**
```javascript
// Paste in browser console
localStorage.removeItem('_hc_flags');
location.reload();
```

## Layout Comparison

### Classic Layout (Default)
- Full-page scrolling
- Composer fixed to viewport bottom
- Large bottom padding to prevent overlap
- Sidebar scrolls with page
- Works exactly like before

### Focused Chat Layout (New)
- Fixed-height chat window
- Transcript has internal scrolling
- Composer docked directly below transcript
- Sidebar always visible on left (desktop)
- ChatGPT/Claude-style experience

## Implementation Details

### Files Modified

1. **`web/src/lib/feature-flags.ts`**
   - Added `focusedChatLayout` flag type
   - Default: `false` (classic layout)

2. **`web/src/i18n/messages.ts`**
   - Added UI labels for the new toggle

3. **`web/src/components/layout-switcher.tsx`** (NEW)
   - `LayoutSwitcher` - Switches between layouts based on flag
   - `ClassicLayout` - Original layout preserved
   - `FocusedChatLayout` - New ChatGPT-style layout

4. **`web/src/app/page-client.tsx`**
   - Refactored to extract layout sections
   - Now uses `LayoutSwitcher` component

### How It Works

```typescript
// The switcher checks the feature flag
const { flags } = useFeatureFlags();

if (flags.focusedChatLayout) {
  return <FocusedChatLayout {...props} />;
}

return <ClassicLayout {...props} />;
```

## Testing Checklist

- [x] TypeScript compilation passes
- [x] Dev server starts without errors
- [x] Feature flag appears in Settings UI
- [x] Toggle switches layouts instantly
- [x] Classic layout works as before
- [x] Focused layout renders correctly
- [x] Easy rollback via Settings
- [x] Emergency rollback via console

## Known Limitations

### Focused Chat Layout
- Sidebar hidden on mobile (space constraints)
- May need tweaks for very long coach messages
- Tour system may need position adjustments

### Auto-scroll Integration
The focused chat layout works great with the auto-scroll feature implemented earlier:
- Transcript scrolls internally to latest message
- Composer stays docked below transcript
- No more overlap issues

## Next Steps (Optional)

1. **Fine-tune spacing** - Adjust padding/margins in focused layout
2. **Mobile optimization** - Add drawer/modal for sidebar on small screens
3. **Transition animations** - Smooth fade when switching layouts
4. **A/B testing** - Collect user feedback on both layouts

## Support

If you encounter issues:

1. **First**: Try rollback (turn off the toggle)
2. **Check console**: Open browser DevTools for errors
3. **Clear cache**: Remove `_hc_flags` from localStorage
4. **Reference this doc**: Contains all rollback methods

---

**Remember:** The classic layout is preserved and can always be restored instantly by toggling the feature flag OFF.
