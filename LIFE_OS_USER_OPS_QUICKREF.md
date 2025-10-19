# Life OS → User Ops Quick Reference

## 🎯 What Was Built

Mounted the full Life OS panel inside **User Ops → Head Coach** tab with:
- **Embedded mode**: Compact spacing, inherits container scroll
- **Autonomy-aware**: Read-only at L0/L1, editable at L2+
- **Direct Core routing**: Port 8015, capability-gated writes
- **Friendly empty states**: No red errors, helpful placeholders
- **Feature flag**: Easy on/off toggle

---

## 📍 Where to Find It

**URL**: `http://localhost:3100/user-ops/USER1/hc`

**Location**: Below the RSC Collaboration section (when agency level ≥ L1)

---

## 🔧 How to Use

### As an Operator (DevX)

1. **Navigate** to User Ops → Select user → Head Coach tab
2. **View** Life OS data (always visible, even if empty)
3. **Change agency level** via L0-L4 selector:
   - L0/L1 → Life OS is **read-only** (displays banner)
   - L2+ → Life OS is **editable** (Quick Capture, checkboxes work)
4. **Test Quick Capture** (L2+):
   - Type in input → Press Enter or click Add
   - Task appears in Today's 3 or Inbox

### Empty State Messages

When no data exists, you'll see:
- "No North Star yet — define your identity and purpose..."
- "No tasks scheduled for today — Quick Capture something important"
- "No goals yet — add goals to track progress..."
- (etc. for all cards)

**These are normal and expected!** Not errors.

---

## 🎚️ Feature Flag

**File**: [featureFlags.ts](ReDNACoreDemo/devx/frontend/src/lib/featureFlags.ts)

```typescript
export const FEATURE_FLAGS = {
  LIFE_OS_IN_USER_OPS: true,  // Set to false to hide Life OS
} as const
```

**To disable**: Change to `false`, rebuild frontend

---

## 🧪 Verification

### Quick Test
```bash
./scripts/verify_life_os_user_ops.sh
```

### Manual Test
1. Open `http://localhost:3100/user-ops/USER1/hc`
2. Scroll to Life OS section (below RSC)
3. Verify cards appear with empty states
4. Switch agency level L2 → L0 → observe read-only badge
5. Switch back to L2 → Quick Capture a task

---

## 📁 Files Changed

| File | Changes |
|------|---------|
| [LifeOSPane.tsx](ReDNACoreDemo/devx/frontend/src/components/LifeOSPane.tsx) | Added `embedded` & `editable` props, 404 handling, empty states, read-only controls |
| [HCTab.tsx](ReDNACoreDemo/devx/frontend/src/routes/user-ops/tabs/HCTab.tsx:366-379) | Mounted LifeOSPane with `embedded editable={level >= 2}` |
| [featureFlags.ts](ReDNACoreDemo/devx/frontend/src/lib/featureFlags.ts) | Created feature flag `LIFE_OS_IN_USER_OPS: true` |

---

## 🔒 Security

- **Reads**: No capability required (GET requests)
- **Writes**: Require `X-Capability` token (auto-injected by `getCapabilityToken`)
- **Agency level** enforces UI editability (L0/L1 = read-only UI, L2+ = editable UI)
- Backend still enforces permissions regardless of UI state

---

## 🐛 Troubleshooting

**Life OS section not appearing?**
- Check `FEATURE_FLAGS.LIFE_OS_IN_USER_OPS` is `true`
- Verify agency level ≥ L1 (L0 hides the entire agent section)

**Quick Capture disabled?**
- Check agency level is L2+ via selector
- Look for "Read-only (L0/L1)" banner

**Empty states showing red errors?**
- Should NOT happen (404 → empty state)
- If you see red: check browser console, verify Core is running

**Cards not updating after Quick Capture?**
- Check DevTools Network → POST to `:8015/ui/hc/life/USER1/capture`
- Verify `X-Capability` header present
- Check response is 200

---

## 📊 Agency Level → Editability Map

| Level | Name          | Life OS UI State |
|-------|---------------|------------------|
| L0    | Manual        | Hidden (no agent section) |
| L1    | Background    | **Read-only** (banner + disabled controls) |
| L2    | Autonomous    | ✅ **Editable** |
| L3    | Collaborative | ✅ **Editable** |
| L4    | Delegated     | ✅ **Editable** |

---

## ✅ Acceptance Criteria Met

- [x] Life OS mounted in User Ops → Head Coach
- [x] Embedded mode (compact spacing)
- [x] Autonomy-aware (L0/L1 read-only, L2+ editable)
- [x] Direct Core routing (port 8015)
- [x] Friendly empty states (no red errors)
- [x] Feature flag functional
- [x] TypeScript clean (no new errors)
- [x] Verification script passes

---

**Status**: ✅ Complete and verified
**Last Updated**: 2025-10-10
