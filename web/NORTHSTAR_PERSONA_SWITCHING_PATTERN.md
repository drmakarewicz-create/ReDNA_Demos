# Northstar Persona Switching Pattern

## The Problem (Historical)

Persona/coach switching has been unreliable multiple times. Symptoms:
- Click a coach in catalog → URL changes but panel stays the same
- URL shows `?persona=rc` but still seeing Head Coach
- Panel doesn't remount when switching coaches
- Race conditions between state updates and URL sync

## Root Cause

Multiple code paths called `setActivePersona()` directly, relying on a `useEffect` to sync the URL later. This created timing issues:

```typescript
// ❌ OLD PATTERN (broken)
onSelectCoach={(coachId) => {
  setActivePersona(coachId);  // State updates...
  // ...useEffect fires later to update URL
  // ...but by then the component may have already rendered
}}
```

The `useEffect` that syncs URL happens **after** React's render cycle, causing:
1. State changes immediately
2. Component tries to render with new state
3. URL hasn't updated yet
4. PanelBoundary resetKeys sees old URL
5. Panel doesn't remount

## The Solution: Unified Handler

**Always use `handlePersonaChange()` for all persona switches.**

Location: [page-client.tsx:1316-1326](web/src/app/page-client.tsx#L1316-L1326)

```typescript
const handlePersonaChange = useCallback((newPersona: string) => {
  // 1. Update URL FIRST via router
  const url = new URL(window.location.href);
  url.searchParams.set('persona', newPersona);
  const href = (url.pathname + url.search + url.hash) as Route;
  router.push(href, { scroll: false });

  // 2. Update state for immediate UI response
  setActivePersona(newPersona);
}, [router]);
```

### Why This Works

1. **URL updates immediately** via `router.push()`
2. **State updates immediately** for instant UI feedback
3. **PanelBoundary sees new persona** in `resetKeys={[activePersona, ...]}`
4. **Component remounts cleanly** with correct coach context

## Usage Pattern

### ✅ CORRECT - Use unified handler

```typescript
// In CoachCatalogModal
onSelectCoach={(coachId) => {
  handlePersonaChange(coachId);
  pushNotice(`Switched to ${coachId}`, 'success');
}}

// In PersonaRail
<PersonaRail
  activePersona={activePersona}
  onPersonaChange={handlePersonaChange}
/>

// In ChatComposer (for inline commands like "switch to rc")
<ChatComposer
  onPersonaChange={handlePersonaChange}
/>
```

### ❌ WRONG - Direct state updates

```typescript
// DON'T DO THIS
onClick={() => setActivePersona('relationship_coach')}

// DON'T DO THIS
onSelect={(id) => {
  const url = new URL(window.location.href);
  url.searchParams.set('persona', id);
  router.push(url.href);  // Missing state update OR wrong order
}}
```

## Critical Architecture

For persona switching to work, these pieces must be in place:

### 1. PanelBoundary with activePersona in resetKeys
```typescript
<PanelBoundary resetKeys={[activePersona, activeUser]} onRetry={retryTranscript}>
  <TranscriptPanel ... />
</PanelBoundary>
```

Location: [page-client.tsx:2640](web/src/app/page-client.tsx#L2640)

### 2. activePersona in PersonaCenterContext
```typescript
interface PersonaCenterContext {
  activeUser: string;
  activePersona: string;  // ← Must be present
  // ...
}
```

Location: [page-client.tsx:2469](web/src/app/page-client.tsx#L2469)

### 3. URL Sync Effect (for browser back/forward)
```typescript
useEffect(() => {
  const personaFromUrl = normalizePersonaParam(url.searchParams.get('persona'));
  if (personaFromUrl && personaFromUrl !== activePersona) {
    setActivePersona(personaFromUrl);
  }
}, [activePersona, activeUser, centerView]);
```

Location: [page-client.tsx:1146-1150](web/src/app/page-client.tsx#L1146-L1150)

This handles browser navigation (back button, reload) by reading URL → state.

## Testing Checklist

When modifying persona switching code, verify:

- [ ] Click coach in catalog → URL updates to `?persona=X`
- [ ] Panel remounts (check React DevTools or add console.log in component)
- [ ] Reload page → stays on selected coach
- [ ] Browser back button → returns to previous coach
- [ ] Inline chat command "switch to rc" → works correctly
- [ ] PersonaRail clicks → instant switch with no lag
- [ ] No console errors about missing dependencies or stale closures

## Common Mistakes to Avoid

### 1. Only updating state
```typescript
// ❌ Panel won't remount reliably
onClick={() => setActivePersona('rc')}
```

### 2. Only updating URL
```typescript
// ❌ State is stale until next render cycle
const url = new URL(location.href);
url.searchParams.set('persona', 'rc');
router.push(url.href);
```

### 3. Wrong order (state before URL)
```typescript
// ❌ State updates first, component renders with old URL context
setActivePersona('rc');
router.push('/?persona=rc');
```

### 4. Creating multiple handlers
```typescript
// ❌ Defeats the purpose of having a unified pattern
const handleCatalogChange = (id) => { /* custom logic */ };
const handleRailChange = (id) => { /* different logic */ };
// Use ONE handler everywhere instead
```

## Debugging Tips

If persona switching breaks again:

1. **Check if `handlePersonaChange` is being used** everywhere:
   ```bash
   grep -n "setActivePersona" web/src/app/page-client.tsx
   # Should only see: useState declaration, useEffect for URL→state sync,
   # and handlePersonaChange implementation
   ```

2. **Verify PanelBoundary resetKeys**:
   ```typescript
   // Must include activePersona
   resetKeys={[activePersona, activeUser]}
   ```

3. **Check React DevTools**:
   - Open Components tab
   - Find TranscriptPanel or main coach component
   - Watch for remount when switching (component key should change)

4. **Console log the flow**:
   ```typescript
   const handlePersonaChange = useCallback((newPersona: string) => {
     console.log('[Persona] Switching to:', newPersona);
     // ... rest of implementation
   }, [router]);
   ```

## Summary

**ONE RULE**: Always use `handlePersonaChange()` for persona switching.

This ensures:
- ✅ URL updates immediately
- ✅ State updates immediately
- ✅ Components remount cleanly
- ✅ Browser navigation works
- ✅ No race conditions

**Location**: Search for `handlePersonaChange` in [page-client.tsx](web/src/app/page-client.tsx)

**Pattern established**: October 2025 (Northstar Phase 2)
**Last fixed**: Commit `2973034`
