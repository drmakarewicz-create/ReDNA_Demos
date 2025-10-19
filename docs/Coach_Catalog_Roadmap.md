# Coach Catalog Roadmap

_Date: 2025-10-06_
_Status: Phase 1 Complete, Phase 2-4 Planned_

This document outlines the implementation plan for the Coach Catalog system, which provides a scalable way to manage 40-50+ specialized coaches without UI clutter.

---

## ✅ Phase 1: Core Catalog Infrastructure (COMPLETE)

**Completed: October 6, 2025**

### 1.1 Backend API
- ✅ Created `/ui/coach-catalog` endpoint ([api.py:1647-1691](../ReDNACoreDemo/core/api.py#L1647-L1691))
- ✅ Reads from `coach_registry.yaml` for live data
- ✅ Returns full coach metadata: capabilities, domains, autonomy levels, availability
- ✅ Icon mapping helper function

### 1.2 Frontend Modal Component
- ✅ Beautiful modal UI with grid layout ([coach-catalog-modal.tsx](../web/src/components/coach-catalog-modal.tsx))
- ✅ Search functionality (filter by name, description, domain)
- ✅ Coach cards showing:
  - Name, icon, description
  - Natural domains (expertise areas)
  - Autonomy level with color coding
  - Active/Default badges
  - Availability status
- ✅ Click-to-switch persona functionality
- ✅ Responsive design (2 columns desktop, 1 mobile)

### 1.3 UI Integration
- ✅ "Coach Catalog 📚" button above PersonaRail in Developer Mode
- ✅ Shows total coach count
- ✅ Available in both focused and standard layouts
- ✅ Properly gated behind Developer Mode setting

### 1.4 Initial Coach Registry
- ✅ Head Coach (default, cognitive/conversational)
- ✅ Relationship Coach (psychology, emotions, relationships)
- ✅ Photo Coach (physical appearance traits)
- ✅ Personality Test Coach (adaptive personality profiling)
- ✅ Career Coach (skills, professional development)

---

## 🔄 Phase 2: Favorites System (NEXT PRIORITY)

**Goal:** Allow users to select up to 8 favorite coaches → show as quick-access buttons in the right pane

### 2.1 Backend Changes

**Storage Schema:**
```json
// data/users/{user_id}/coach_preferences.json
{
  "favorites": [
    "head_coach",
    "relationship_coach",
    "career_coach",
    "photo_coach"
  ],
  "max_favorites": 8,
  "updated_ts": "2025-10-06T12:34:56Z"
}
```

**API Endpoints:**
- `GET /ui/coach-favorites?user_id={user_id}` → Return user's favorite coaches
- `POST /ui/coach-favorites` → Update favorites list
  - Payload: `{"user_id": "...", "favorites": ["coach_id_1", ...]}`
  - Validation: Max 8 coaches, all must exist in registry
  - Returns: Updated favorites list

### 2.2 Frontend Changes

**Catalog Modal Enhancements:**
- Add "⭐ Favorite" toggle button on each coach card
- Show "★ Favorited" badge on selected coaches
- Visual indicator when favorites limit (8) reached
- Confirmation when removing favorite if it would remove quick-access button

**Quick Access Panel (NEW):**
```tsx
// web/src/components/coach-quick-access.tsx
<CoachQuickAccess
  favorites={userFavorites}
  currentCoach={activePersona}
  onSelectCoach={setActivePersona}
/>
```

Displays 8 or fewer buttons in right pane:
- Compact button grid (2x4 or responsive)
- Each button shows icon + abbreviated name
- Active coach highlighted
- "Manage Favorites" button → opens catalog

**Settings Integration:**
- Add "Manage Favorites" shortcut in Settings modal
- Display current favorites count
- Link to catalog modal

### 2.3 User Experience Flow

1. User opens Coach Catalog
2. Clicks ⭐ on up to 8 coaches
3. Close catalog → Quick Access panel appears in right pane
4. Click any quick-access button to switch coaches instantly
5. Catalog button remains available for browsing all coaches

### 2.4 Acceptance Criteria
- [ ] Users can select/deselect favorites via catalog modal
- [ ] Favorites persist across sessions
- [ ] Quick Access panel shows favorited coaches as buttons
- [ ] Favorites limit (8) enforced with clear messaging
- [ ] Catalog button counts favorites: "Browse all 50 coaches (8 favorited)"

---

## 📊 Phase 3: Usage Analytics & Recommendations (FUTURE)

**Goal:** Track coach usage and recommend coaches based on user needs

### 3.1 Analytics Collection

**Metrics to Track:**
```json
// data/users/{user_id}/coach_usage.json
{
  "head_coach": {
    "total_sessions": 142,
    "total_messages": 1203,
    "avg_session_length_min": 12.5,
    "last_used": "2025-10-06T14:23:00Z",
    "satisfaction_rating": 4.7
  },
  "career_coach": {
    "total_sessions": 8,
    "total_messages": 67,
    "avg_session_length_min": 18.2,
    "last_used": "2025-10-03T09:15:00Z",
    "satisfaction_rating": 5.0
  }
}
```

**Collection Points:**
- Every coach switch (timestamp, from/to coach)
- Session duration tracking
- Message count per session
- Explicit user feedback (thumbs up/down, star rating)

### 3.2 Recommendation Engine

**Triggers:**
- High curiosity in specific namespace → recommend specialist coach
- User spends >5 messages on topic X → suggest relevant coach
- Low engagement with current coach → offer alternatives
- Periodic prompts: "Try Career Coach for skill development?"

**Recommendation Algorithm:**
```python
def recommend_coaches(user_id: str, current_context: Dict) -> List[str]:
    # 1. Match curiosity namespaces to coach capabilities
    high_curiosity_namespaces = get_high_curiosity_namespaces(user_id)
    relevant_coaches = match_coaches_to_namespaces(high_curiosity_namespaces)

    # 2. Filter out recently used coaches (avoid repetition)
    recent_coaches = get_recent_coaches(user_id, days=7)
    candidates = [c for c in relevant_coaches if c not in recent_coaches]

    # 3. Boost coaches with high satisfaction ratings
    candidates = sorted(candidates, key=lambda c: get_satisfaction(user_id, c), reverse=True)

    # 4. Return top 3
    return candidates[:3]
```

### 3.3 UI Changes

**Catalog Modal Enhancements:**
- "Recommended for You" section at top
- Usage stats badge: "You've used this coach 12 times"
- Satisfaction rating display (if user has rated)
- "Try something new" filter → hide frequently used coaches

**In-Context Recommendations:**
```tsx
// Appears in chat when relevant
<CoachRecommendation
  coach="career_coach"
  reason="I notice you're discussing skill development. Want to switch to Career Coach for specialized guidance?"
  onAccept={() => switchToCoach('career_coach')}
  onDismiss={() => dismissRecommendation()}
/>
```

### 3.4 Privacy & Control

- All analytics stored locally (no cloud upload without consent)
- User can view/export their usage data
- "Reset Analytics" button in Settings
- Opt-out of recommendations (use catalog manually only)

---

## 🎨 Phase 4: Advanced Catalog Features (FUTURE)

**Goal:** Make catalog a powerful coach discovery and learning tool

### 4.1 Coach Preview Mode

**"Try Before You Switch":**
- Hover over coach card → see preview of recent delegation example
- "Sample Session" button → view 3-5 example messages from that coach
- "What can this coach help with?" expandable section with use cases

### 4.2 Coach Comparison Tool

**Compare 2-3 coaches side-by-side:**
```tsx
<CoachComparison
  coaches={['relationship_coach', 'personality_test_coach']}
  compareFields={['domains', 'autonomy', 'typical_questions', 'sample_output']}
/>
```

Helps users decide between similar coaches (e.g., Relationship Coach vs. Personality Test Coach for emotional topics).

### 4.3 Coach Discovery Wizard

**Guided selection for new users:**
1. "What are you working on today?"
   - Career planning
   - Understanding myself better
   - Improving relationships
   - Physical appearance
   - General conversation
2. Based on answer, recommend 2-3 coaches
3. Show preview of each
4. User picks one → auto-favorite it

### 4.4 Coach Tags & Filtering

**Enhanced Search:**
- Tag coaches: `#psychology`, `#career`, `#visual`, `#assessment`
- Filter by autonomy level: "Show only high-autonomy coaches"
- Filter by namespace: "Show coaches that work with SkillDNA"
- Sort options: Most used, Highest rated, Alphabetical, Newest

### 4.5 Coach Notes & History

**Per-Coach Context:**
```json
// data/users/{user_id}/coach_notes.json
{
  "career_coach": {
    "personal_notes": "Helped me create learning plan for Python. Very actionable!",
    "last_topics": ["skill gaps", "learning paths", "career transition"],
    "bookmarked_sessions": ["session_2025_10_03_09_15"]
  }
}
```

- User can add private notes about each coach
- View history of topics discussed with each coach
- Bookmark particularly helpful sessions
- Search notes across all coaches

---

## 📐 Implementation Guidelines

### Scalability Targets
- System should gracefully handle 40-50 coaches
- Catalog modal should load <300ms even with 50 coaches
- Search should be instant (client-side filtering)
- Quick Access panel limited to 8 buttons prevents UI overflow

### Design Principles
1. **Catalog as Discovery Tool:** Not just a list, but a learning interface
2. **Minimize Clicks:** Quick Access for common tasks, Catalog for exploration
3. **Smart Defaults:** Auto-recommend based on context, let users override
4. **Progressive Disclosure:** Show basics first, advanced features on demand
5. **Respect User Preferences:** Remember choices, don't nag

### Technical Constraints
- All coach metadata sourced from `coach_registry.yaml` (single source of truth)
- Favorites stored per-user in `coach_preferences.json`
- Analytics optional and privacy-preserving
- Frontend must work SSR-safe (no localStorage in render, only in effects)

---

## 🚀 Migration Path

### From Phase 1 (Current) to Phase 2 (Favorites)

**Step 1: Backend Prep**
1. Create `coach_preferences.json` schema
2. Add favorites endpoints
3. Write migration script for existing users (auto-favorite Head Coach)

**Step 2: Frontend Update**
1. Add CoachQuickAccess component
2. Update catalog modal with favorite toggles
3. Wire up persistence

**Step 3: Rollout**
1. Enable for Developer Mode users first (dogfooding)
2. Gather feedback on limit (8 vs 10 vs 12?)
3. Refine UX based on usage patterns
4. Enable for all users

---

## ✅ Success Metrics

### Phase 2 (Favorites)
- **Adoption:** 70% of users set at least 3 favorites within first week
- **Engagement:** Quick Access buttons reduce catalog opens by 60%
- **Satisfaction:** User survey: "Favorites make coach switching easier" >4.5/5

### Phase 3 (Analytics & Recommendations)
- **Accuracy:** 80% of recommended coaches are accepted (not dismissed)
- **Discovery:** 40% of users try a coach they hadn't used before due to recommendation
- **Retention:** Users with recommendations enabled have 25% longer session times

### Phase 4 (Advanced Features)
- **Utility:** Coach comparison tool used by 30% of users before first coach switch
- **Education:** Discovery wizard increases new coach trial rate by 50%
- **Organization:** 60% of power users (8+ coaches used) maintain coach notes

---

## 🔗 Related Documentation

- [Coach Registry Schema](../ReDNACoreDemo/core/coach_registry.yaml)
- [Delegation System Guide](../ReDNACoreDemo/DELEGATION_SYSTEM_GUIDE.md)
- [Developer Mode Architecture](../web/docs/DEVELOPER_MODE_ARCHITECTURE.md)

---

**Document Status:** Living roadmap, updated as phases complete
**Owner:** ReDNA Core Team
**Last Updated:** 2025-10-06
