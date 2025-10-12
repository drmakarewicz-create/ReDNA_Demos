# Persona Panel Config Debug Report

**Generated**: 2025-10-11T21:12:57.315288+00:00
**Total Personas**: 13
**Test Users Found**: 142

---

## 1. Persona Configuration Summary

| Persona | Life OS | Panels | Description |
|---------|---------|--------|-------------|
| `head_coach` | `full` | (none) | Orchestrator - shows full Life OS |
| `relationship_coach` | `relationship` | (none) | Shows filtered Life OS (relationship items only) |
| `photo_coach` | `hidden` | photo | Photo upload and trait extraction |
| `photo` | `hidden` | photo | Photo Coach (alternate key) |
| `padna_coach` | `hidden` | padna | Portrait renderer from PaDNA traits |
| `padna` | `hidden` | padna | PaDNA Coach (alternate key) |
| `rendering` | `hidden` | avatar, portrait | Avatar and portrait rendering |
| `career_coach` | `hidden` | career_snapshot, skill_map | Career insights and skill curiosity |
| `personality_test_coach` | `hidden` | personality_snapshot, personality_map | Personality traits and map visualization |
| `chatdna_coach` | `hidden` | chatdna_snapshot, language_style | Communication style and language patterns |
| `beliefdna_coach` | `hidden` | (none) | Philosophy and values (rendered via renderPersonaTools) |
| `permission_coach` | `hidden` | (none) | Consent and privacy (uses DynamicCoachPanes) |
| `*` | `hidden` | (none) | Default fallback for unknown personas |

---

## 2. User Override Summary

### Users with Default Layouts

- 10-1-test
- 10-2-507
- 930-1106
- AB Test
- AGG_USER1
- AGG_USER2
- AGG_USER3
- AUTONOMY
- CLITEST
- COMPLETELY_EMPTY_USER_TEST
- DAEMON1
- EMPTY_AGG_USER
- EMPTY_USER_FOCUS_TEST
- EMPTY_WEEK_USER
- HS-MESSY
- INTEGRATION_USER
- LLTEST
- LOHAN1251
- MRSCOACH-EXP
- MrsCoachSuperExp
- PERF_USER0
- PERF_USER1
- PERF_USER2
- PERF_USER3
- PERF_USER4
- PERF_USER5
- PERF_USER6
- PERF_USER7
- PERF_USER8
- PERF_USER9
- PHOTO_TEST
- TEST
- TEST_DEVX_PANEL_API
- TEST_DEVX_PANEL_AUDIT
- TEST_DEVX_PANEL_CONTEXT
- TEST_DEVX_PANEL_COUNT
- TEST_DEVX_PANEL_FLOW
- TEST_DEVX_PANEL_FOCUS
- TEST_DEVX_PANEL_PERF
- TEST_DEVX_PANEL_READONLY
- TEST_DEVX_PANEL_RECOMPUTE
- TEST_DEVX_PANEL_TIMESTAMP
- TEST_GOVERNANCE_USER
- TEST_LEARNING_APPLY_NEW
- TEST_LEARNING_AUDIT
- TEST_LEARNING_BASELINE
- TEST_LEARNING_BEHAVIOR
- TEST_LEARNING_DIR_CREATE
- TEST_LEARNING_HELPER
- TEST_LEARNING_INCREMENT
- TEST_LEARNING_LOAD_PERF
- TEST_LEARNING_OTHER_COACH
- TEST_LEARNING_PERF
- TEST_LEARNING_PRECOMPUTED
- TEST_LEARNING_SAVE_LOAD
- TEST_LEARNING_SMOOTH
- TEST_LIFE_USER
- TEST_TS_CHECK
- U1
- USER1
- USER2
- USER3
- USER4
- USER_DEMO1
- USER_DEMO2
- USER_DEMO3
- VOICE_AUDIT_USER
- VOICE_STORAGE_USER
- VOICE_USER
- WEEK_FLOW_USER
- WEEK_REVIEW_USER
- WRONG_USER
- ab-exp
- ab-ext
- ab-sep26
- abtest
- active_test_user
- bs1009-ext
- bstest
- bundle_test_user
- container_discovery_test
- debug_test_user
- delegation_test_user
- demo_user
- devexp_865e448bed81
- devexp_c9f2160dff12
- devexp_test
- hc_test_alice
- hc_test_user
- hc_v2_1b_demo
- hc_v2_demo
- health
- hstest
- integration_test_user
- lilo-extended
- ll1055
- ll749
- mrscoach-full
- mrscoachtest
- nonexistent_user
- persona_deontological
- persona_hemingway
- persona_joan_didion
- persona_maya_angelou
- persona_obama
- persona_utilitarian
- persona_virtue_ethics
- persona_winston_churchill
- test-ingest-001
- test_manual
- test_projects_user
- test_rr_fix
- test_sprint1c_1759580556463
- test_sprint1c_1759580556471
- test_sprint1c_1759580618567
- test_sprint1c_1759580618571
- test_sprint1c_1759580618582
- test_sprint1c_1759580618592
- test_sprint1c_1759580659611
- test_sprint1c_1759580659616
- test_sprint1c_1759580659634
- test_sprint1c_1759580659647
- test_sprint2a_1759582448550
- test_sprint2a_1759582448557
- test_sprint2a_1759582448566
- test_sprint2a_1759582448577
- test_sprint2a_1759582448580
- test_user
- test_user_001
- test_user_003
- test_user_004
- test_user_005
- test_user_008
- test_user_009
- test_user_010
- test_user_011
- test_user_renders
- test_user_smoke
- test_user_traits
- trait_test_user
- user_bad_json
- user_no_renders

---

## 3. Detailed User Overrides

---

## 4. Component Mapping Validation

Checking if panel components exist in codebase...

| Panel ID | Component Path | Status |
|----------|----------------|--------|
| `photo` | `web/src/components/photo/photo-panel.tsx` | ✅ EXISTS |
| `padna` | `web/src/components/padna/portrait-render-card.tsx` | ✅ EXISTS |
| `avatar` | `web/src/components/rendering/avatar-render-panel.tsx` | ✅ EXISTS |
| `portrait` | `web/src/components/padna/portrait-render-card.tsx` | ✅ EXISTS |
| `career_snapshot` | `web/src/components/career/career-snapshot-card.tsx` | ✅ EXISTS |
| `skill_map` | `web/src/components/career/skill-curiosity-map.tsx` | ✅ EXISTS |
| `personality_snapshot` | `web/src/components/personality/personality-snapshot-card.tsx` | ✅ EXISTS |
| `personality_map` | `web/src/components/personality/personality-map-visualization.tsx` | ✅ EXISTS |
| `chatdna_snapshot` | `web/src/components/chatdna-snapshot-card.tsx` | ✅ EXISTS |
| `language_style` | `web/src/components/language-style-panel.tsx` | ✅ EXISTS |

---

## 5. Recommendations

✅ **No issues found** — All configurations valid!

---

## 6. Quick Actions

### Create Test Override
```bash
mkdir -p data/users/TEST/ui
cat > data/users/TEST/ui/right_pane_layout.json << 'EOF'
{
  "version": 2,
  "overrides": {
    "photo_coach": {
      "visible": {"life_os": false}
    }
  }
}
EOF
```

### Validate All User Layouts
```bash
for user_dir in data/users/*/ui; do
  if [ -f "$user_dir/right_pane_layout.json" ]; then
    echo "Validating $user_dir/right_pane_layout.json"
    cat "$user_dir/right_pane_layout.json" | python3 -m json.tool > /dev/null
  fi
done
```

### Reset User Layout
```bash
rm data/users/TEST/ui/right_pane_layout.json
# Or via API:
curl -X DELETE http://localhost:8000/ui/config/TEST/right_pane_layout
```

---

**End of Report**