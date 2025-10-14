# Life OS → User Ops Visual Guide

## 📍 Location in UI

**Path**: DevX → User Ops → [Select User] → **Head Coach** tab

**Position**: Below RSC Collaboration section

---

## 🎨 Visual Hierarchy

```
┌─ User Ops: USER1 ─────────────────────────────────┐
│                                                    │
│  [Personal] [Career] [Head Coach] [Permissions]   │  ← Tabs
│                                                    │
│  ┌─ Agency Level ───────────────────────────┐     │
│  │ [L0] [L1] [L2] [L3] [L4]                 │     │
│  │ ✓ Selected: L2 Autonomous                │     │
│  └──────────────────────────────────────────┘     │
│                                                    │
│  ┌─ Agent Control Center ───────────────────┐     │
│  │ Embedded view of agent panel             │     │
│  └──────────────────────────────────────────┘     │
│                                                    │
│  ┌─ Activity Audit ──────────────────────────┐    │
│  │ Last 20 events...                         │    │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  ┌─ RSC Collaboration ──────────────────────┐     │  ← Only if level ≥ L3
│  │ Agent-to-agent messaging...              │     │
│  └──────────────────────────────────────────┘     │
│                                                    │
│  ┌─ Life OS ─────────────────────────────────┐    │  ← ✨ NEW SECTION
│  │                                            │    │
│  │  ⚠️ Read-only (L0/L1) — Enable L2+ to edit │    │  ← Only if L0/L1
│  │                                            │    │
│  │  ┌─ North Star ─────────────────────┐     │    │
│  │  │ Identity: [empty]                 │     │    │
│  │  │ Purpose: [empty]                  │     │    │
│  │  │ No North Star yet — define...     │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Today's 3 ──────────────────────┐     │    │
│  │  │ ☐ Buy groceries                   │     │    │
│  │  │ ☐ Call dentist                    │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Quick Capture ──────────────────┐     │    │
│  │  │ [What needs to be done?] [Add]    │     │    │  ← Disabled if L0/L1
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Inbox ──────────────────────────┐     │    │
│  │  │ Inbox is empty                    │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Goals ──────────────────────────┐     │    │
│  │  │ No goals yet — add goals to...    │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Projects (Phase 2) ─────────────┐     │    │
│  │  │ No active projects                │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Reading & Links ────────────────┐     │    │
│  │  │ No links saved yet — add articles │     │    │
│  │  └───────────────────────────────────┘     │    │
│  │                                            │    │
│  │  ┌─ Inspiration ─────────────────────┐    │    │
│  │  │ No inspiration added yet — add... │     │    │
│  │  └───────────────────────────────────┘     │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘
```

---

## 🎭 State Variations

### L0/L1 (Read-Only Mode)

```
┌─ Life OS ────────────────────────────────────┐
│  ⚠️ Read-only (L0/L1) — Enable L2+ to edit   │  ← Banner
│                                               │
│  ┌─ Quick Capture ─────────────────────┐     │
│  │ [Enable L2+ to add tasks] [Add]      │     │  ← Disabled, grayed out
│  │      ↑ disabled    ↑ disabled         │     │
│  └──────────────────────────────────────┘     │
│                                               │
│  ┌─ Today's 3 ─────────────────────────┐     │
│  │ ☐ Buy groceries  (checkbox disabled) │     │  ← Can't toggle
│  └──────────────────────────────────────┘     │
└───────────────────────────────────────────────┘
```

### L2+ (Editable Mode)

```
┌─ Life OS ────────────────────────────────────┐
│  (no banner)                                  │
│                                               │
│  ┌─ Quick Capture ─────────────────────┐     │
│  │ [What needs to be done?] [Add]      │     │  ← Active, blue button
│  │      ↑ editable         ↑ clickable  │     │
│  └──────────────────────────────────────┘     │
│                                               │
│  ┌─ Today's 3 ─────────────────────────┐     │
│  │ ☑ Buy groceries  (can toggle)        │     │  ← Interactive
│  └──────────────────────────────────────┘     │
└───────────────────────────────────────────────┘
```

---

## 🎨 Visual Design Tokens

### Colors

**Read-Only Banner**:
- Background: `bg-amber-50`
- Border: `border-amber-200`
- Text: `text-amber-800`

**Empty States**:
- Text: `text-gray-400` (italic)

**Section Cards**:
- Background: `bg-white`
- Border: `border-gray-200`
- Shadow: `shadow-sm`

**Inspiration Card** (special):
- Background: `bg-gradient-to-br from-blue-50 to-purple-50`

### Spacing

**Embedded Mode** (`embedded=true`):
- Container: `space-y-4` (16px between cards)

**Standalone Mode** (`embedded=false`):
- Container: `space-y-6` (24px between cards)

### Typography

**Section Headers**:
- Size: `text-lg`
- Weight: `font-semibold`
- Color: `text-gray-900`

**Descriptions**:
- Size: `text-sm`
- Color: `text-gray-600`

**Empty States**:
- Size: `text-sm`
- Style: `italic`
- Color: `text-gray-400`

---

## 🖱️ Interactive Elements

### Quick Capture Input

**Enabled (L2+)**:
```css
className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm
           focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
placeholder="What needs to be done?"
```

**Disabled (L0/L1)**:
```css
className="... disabled:bg-gray-100 disabled:cursor-not-allowed"
placeholder="Enable L2+ to add tasks"
title="Enable Autonomous mode (L2) to edit"
```

### Checkboxes

**Enabled (L2+)**:
```css
className="h-4 w-4 rounded border-gray-300 text-blue-600
           focus:ring-blue-500"
```

**Disabled (L0/L1)**:
```css
className="... disabled:cursor-not-allowed disabled:opacity-60"
title="Enable Autonomous mode (L2) to edit"
```

---

## 📐 Layout Differences

### Embedded in User Ops (This Implementation)

- **Container padding**: Inherited from parent `<div className="px-6 py-4">`
- **Card spacing**: `space-y-4` (compact)
- **Scrolling**: Inherits from User Ops page scroll
- **Width**: Full width within User Ops layout

### Standalone (Chat Right Rail - Unchanged)

- **Container padding**: Own padding context
- **Card spacing**: `space-y-6` (relaxed)
- **Scrolling**: Own scroll container
- **Width**: Fixed rail width (~300-400px)

---

## 🎬 Animation & Transitions

### Agency Level Change

**User action**: Click L0 → L2 in agency level selector

**Visual feedback**:
1. Agency selector updates (L2 highlighted in blue)
2. Life OS section **immediately** removes read-only banner
3. Quick Capture input transitions from gray → white
4. Checkboxes become clickable
5. Cursor changes from `not-allowed` → `pointer`

**No page reload required** — React state drives editability.

---

## 🔍 Browser DevTools Inspection

### When Testing Quick Capture (L2+)

**Network Tab**:
```
POST http://localhost:8015/ui/hc/life/USER1/capture
Status: 200
Headers:
  Content-Type: application/json
  X-Capability: cap_5a8f3c2b_1728598765_...
Body:
  {"text": "Buy groceries", "when": "backlog"}
```

**Components Tab** (React DevTools):
```
<LifeOSPane>
  userId: "USER1"
  embedded: true
  editable: true  ← Check this value matches agency level
</LifeOSPane>
```

---

## 📱 Responsive Considerations

**Embedded mode inherits responsiveness from User Ops**:
- Desktop: Full width, comfortable spacing
- Tablet: Maintains layout, may reduce padding
- Mobile: (User Ops likely not optimized for mobile yet)

---

## ✨ Empty State Examples

### North Star
> "No North Star yet — define your identity and purpose to guide your goals"

### Today's 3
> "No tasks scheduled for today — Quick Capture something important"

### Goals
> "No goals yet — add goals to track progress toward your North Star"

### Links
> "No links saved yet — add articles and resources for later"

### Inspiration
> "No inspiration added yet — add a quote or wisdom that motivates you"

**Philosophy**: Every empty state includes:
1. Current state ("No X yet")
2. Action hint ("add X" or "Quick Capture")

**No scary red errors** — 404 from API → friendly empty state.

---

## 🎯 Visual Testing Checklist

- [ ] Life OS section appears below RSC
- [ ] All cards have consistent border/shadow
- [ ] Empty states use gray italic text (not red)
- [ ] Read-only banner appears only at L0/L1
- [ ] Quick Capture button is blue when enabled
- [ ] Checkboxes have blue checkmark when completed
- [ ] Inspiration card has gradient background
- [ ] Spacing is compact (space-y-4)
- [ ] No double scrollbars
- [ ] Tooltips appear on hover (disabled state)

---

**Status**: ✅ Visual implementation complete
**Last Updated**: 2025-10-10
