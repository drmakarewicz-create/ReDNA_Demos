# Developer Mode - Quick Start Guide

## 🚀 How to Toggle Developer Mode

1. **Open Settings**
   - Click the ⚙️ Settings button in the header
   - Or press `Ctrl+,` (or `Cmd+,` on Mac)

2. **Find Developer Mode Section**
   - Scroll to the "Developer Mode" section
   - Look for the orange-highlighted toggle

3. **Toggle ON/OFF**
   - Check the box to enable Developer Mode
   - Uncheck to return to User Mode
   - Setting persists across page refreshes

---

## 📸 What Changes?

### In User Mode (Default)
```
✅ Clean, production-ready interface
✅ Head Coach conversation
✅ Delegation recommendations
✅ Observation Summary
✅ Coach Asks
✅ Nudge Inbox

❌ NO PersonaRail (manual coach switching)
❌ NO debugging panels
❌ NO raw metrics
❌ NO developer tools
```

### In Developer Mode
```
✅ Everything from User Mode, PLUS:

✅ PersonaRail (manual coach switching buttons)
✅ Performance metrics (when enabled)
✅ Feature flags
✅ Raw UCN/RR scores
✅ Container paths
✅ Debugging tools
```

---

## 🛠️ For Developers: Adding Mode-Specific Features

### Dev-Only Feature

```typescript
import { DevOnly } from '@/lib/developer-mode';

<DevOnly>
  <PerformanceMetrics />
  <DebugPanel />
  <RawDataInspector />
</DevOnly>
```

### User-Only Feature

```typescript
import { UserOnly } from '@/lib/developer-mode';

<UserOnly>
  <CleanDelegationUI />
  <SimplifiedMetrics />
</UserOnly>
```

### Adaptive Feature

```typescript
import { useDeveloperMode } from '@/lib/developer-mode';

function MyComponent() {
  const { isDeveloperMode } = useDeveloperMode();

  return (
    <div>
      {isDeveloperMode ? (
        <DetailedView showRawData />
      ) : (
        <SimplifiedView />
      )}
    </div>
  );
}
```

---

## ⚠️ Important Notes

1. **Default Mode:** User Mode (pristine, production-ready)

2. **Left Pane Protection:** Developer Mode changes MUST NOT affect the left pane (chat/transcript/composer) in User Mode

3. **Testing:** Always test both modes before committing changes

4. **Documentation:** Mark features as User-only, Dev-only, or Shared in PR descriptions

---

## 🔍 Troubleshooting

**Q: Developer Mode toggle doesn't appear**
- Clear browser cache and reload
- Check that you're running the latest code

**Q: Mode doesn't persist after refresh**
- Check browser localStorage permissions
- Ensure localStorage key `redna_developer_mode` is not blocked

**Q: Features still show in wrong mode**
- Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
- Clear localStorage and reset settings

---

For full details, see [DEVELOPER_MODE_ARCHITECTURE.md](DEVELOPER_MODE_ARCHITECTURE.md)
