# Simple Chat Layout Fix - Claude Code Style

## The Problem
We've been overcomplicating the layout. The transcript won't scroll because we're fighting flexbox with grid + absolute positioning.

## The Solution
Use the EXACT pattern that Claude Code uses (the interface you're typing in right now):

```tsx
// Parent: 100vh flex column
<div className="flex flex-col h-screen">

  {/* Header: fixed height */}
  <header className="flex-shrink-0">
    Navigation, user info, etc.
  </header>

  {/* Main: fills remaining space, flex column */}
  <main className="flex-1 min-h-0 flex flex-col">

    {/* Transcript: grows to fill, scrolls internally */}
    <div className="flex-1 min-h-0 overflow-y-auto">
      Messages here...
    </div>

    {/* Composer: fixed at bottom */}
    <div className="flex-shrink-0">
      Input box here...
    </div>

  </main>
</div>
```

## Key Principles
1. **`flex-1 min-h-0`** on scroll container forces it to constrain to parent height
2. **No grid, no absolute positioning** - just flexbox all the way down
3. **`overflow-y: auto`** only on the transcript container
4. **Composer is inside the main flex column**, not positioned separately

## Implementation
Replace the complex FocusedChatLayout with this simple structure.
