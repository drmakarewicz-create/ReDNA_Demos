# Coach Workshop Integration Specification

**Version:** 1.0
**Last Updated:** October 7, 2025
**Status:** Implementation Ready

---

## Overview

This document specifies how the Coach Workshop integrates with the RPUF (Right Pane Unified Framework) to support both legacy persona-based coaches and new delegation-based coaches with manifest-driven UI.

## Architecture

### Current State (Legacy)
```
Coach Workshop
  ↓
persona_registry.list_personas()
  ↓
Load from ExplorerFinal/ui/personas/*.py
  ↓
Display: PaDNA, Photo, Relationship Coach
```

### Target State (Bridge)
```
Coach Workshop
  ↓
[Source Switcher: Personas | Delegation]
  ↓
┌─────────────────────┬──────────────────────────┐
│ Personas (legacy)   │ Delegation (registry)    │
│                     │                          │
│ persona_registry    │ coach_registry.yaml      │
│ ↓                   │ ↓                        │
│ PaDNA, Photo, RC    │ Career, PTC, Photo, RC   │
└─────────────────────┴──────────────────────────┘
         ↓                        ↓
    Legacy Renderer        RPUF Renderer
```

## Implementation Tasks

### 1. Add Source Switcher UI

**Location:** `ExplorerDev/explorer_dev.py` → `_show_persona_registry()`

```python
def _show_persona_registry(context: DevWriteContext) -> None:
    st.subheader("Coach Workshop")

    # NEW: Source switcher
    source_tab1, source_tab2 = st.tabs(["📋 Personas (legacy)", "🚀 Delegation (registry)"])

    with source_tab1:
        _render_legacy_persona_workshop(context)

    with source_tab2:
        _render_delegation_workshop(context)
```

**Implementation:**
- Two tabs at top of Workshop
- "Personas (legacy)" tab shows existing persona registry UI (unchanged)
- "Delegation (registry)" tab shows new delegation-based UI

### 2. Implement Delegation Workshop Renderer

**New Function:** `_render_delegation_workshop(context)`

```python
def _render_delegation_workshop(context: DevWriteContext) -> None:
    """
    Delegation-based coach workshop.
    Loads coaches from coach_registry.yaml and renders via RPUF.
    """

    # 1. Load coaches from registry
    coaches = _load_delegation_coaches()

    # 2. Coach selector
    selected_coach_id = st.selectbox(
        "Select Coach",
        options=[c["id"] for c in coaches],
        format_func=lambda id: next(c["display_name"] for c in coaches if c["id"] == id)
    )

    # 3. Load manifest
    manifest_path = REPO_ROOT / f"ReDNACoreDemo/coaches/{selected_coach_id}/coach_ui_manifest.yaml"
    manifest = _load_and_validate_manifest(manifest_path)

    # 4. Data binding mode selector
    data_mode = st.radio(
        "Data Binding Mode",
        options=["Live", "Stubbed", "Hybrid"],
        horizontal=True,
        help="Live: real API calls | Stubbed: workshop fixtures | Hybrid: live RR + stub widgets"
    )

    # 5. Intent/RR simulator
    _render_intent_rr_simulator(selected_coach_id, manifest)

    # 6. Render preview
    _render_workshop_preview(selected_coach_id, manifest, data_mode, context)
```

### 3. Load Delegation Coaches from Registry

```python
def _load_delegation_coaches() -> List[Dict[str, Any]]:
    """Load coaches from coach_registry.yaml."""
    registry_path = REPO_ROOT / "ReDNACoreDemo/core/coach_registry.yaml"

    if not registry_path.exists():
        st.error(f"Coach registry not found: {registry_path}")
        return []

    with open(registry_path, "r") as f:
        registry = yaml.safe_load(f)

    coaches = []
    for coach_id, coach_data in registry.get("coaches", {}).items():
        coaches.append({
            "id": coach_id,
            "display_name": coach_data.get("display_name", coach_id),
            "description": coach_data.get("description", ""),
            "primary_namespaces": coach_data.get("primary_namespaces", [])
        })

    return coaches
```

### 4. Load and Validate Manifest

```python
def _load_and_validate_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load coach UI manifest and validate against schema.
    Returns None if manifest doesn't exist or validation fails.
    """
    if not manifest_path.exists():
        st.warning(f"Manifest not found: {manifest_path.name}")
        st.info("This coach doesn't have a UI manifest yet. Create one to enable Workshop preview.")
        return None

    # Load manifest
    try:
        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)
    except Exception as e:
        st.error(f"Failed to parse manifest: {e}")
        return None

    # Validate against schema
    schema_path = REPO_ROOT / "ReDNACoreDemo/schemas/coach_ui_manifest.schema.json"

    if schema_path.exists():
        try:
            with open(schema_path, "r") as f:
                schema = json.load(f)

            import jsonschema
            jsonschema.validate(manifest, schema)

            st.success(f"✓ Manifest valid (schema v{manifest.get('schema_version', '?')})")
        except jsonschema.ValidationError as e:
            st.error(f"Manifest validation failed: {e.message}")
            st.json(e.instance)
            return None
        except Exception as e:
            st.warning(f"Schema validation unavailable: {e}")

    return manifest
```

### 5. Intent & RR Simulator

```python
def _render_intent_rr_simulator(coach_id: str, manifest: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, float]]:
    """
    Render intent/RR simulator panel.
    Returns (selected_intent, rr_values).
    """
    with st.expander("🎯 Intent & RR Simulator", expanded=True):
        st.caption("Simulate user intents and RR distribution to test widget conditions")

        # Intent selector
        intent_layouts = manifest.get("intent_layouts", {})
        available_intents = list(intent_layouts.keys()) + ["(none)"]

        intent_col, user_col = st.columns([2, 1])

        with intent_col:
            selected_intent = st.selectbox(
                "User Intent",
                options=available_intents,
                help="Select an intent to test intent-specific layouts"
            )

            if selected_intent != "(none)" and selected_intent in intent_layouts:
                layout_config = intent_layouts[selected_intent]
                st.json(layout_config)

        with user_col:
            test_user_id = st.text_input(
                "Test User ID",
                value="TEST",
                help="User ID for live data mode"
            )

        # RR sliders
        st.markdown("**Domain RR Values**")

        # Determine relevant domains from manifest conditions
        domains = _extract_domains_from_manifest(manifest)

        rr_values = {}
        slider_cols = st.columns(len(domains) if len(domains) <= 4 else 2)

        for idx, domain in enumerate(domains):
            col = slider_cols[idx % len(slider_cols)]
            with col:
                rr_values[domain] = st.slider(
                    domain.split(".")[-1],  # Show short name
                    min_value=0.0,
                    max_value=100.0,
                    value=50.0,
                    step=5.0,
                    help=f"RR for {domain}"
                )

        # Curiosity values (derived from RR)
        curiosity_values = {k: 100.0 - v for k, v in rr_values.items()}

        # Store in session state
        st.session_state["workshop_intent"] = selected_intent if selected_intent != "(none)" else None
        st.session_state["workshop_rr"] = rr_values
        st.session_state["workshop_curiosity"] = curiosity_values
        st.session_state["workshop_user_id"] = test_user_id

        return selected_intent if selected_intent != "(none)" else None, rr_values


def _extract_domains_from_manifest(manifest: Dict[str, Any]) -> List[str]:
    """Extract unique domains from widget conditions."""
    domains = set()

    for widget in manifest.get("widgets", []):
        conditions = widget.get("conditions", [])
        for condition in conditions:
            if condition.get("type") == "rr_threshold":
                domain = condition.get("rr_threshold", {}).get("domain")
                if domain:
                    domains.add(domain)
            elif condition.get("type") == "curiosity_threshold":
                domain = condition.get("curiosity_threshold", {}).get("domain")
                if domain:
                    domains.add(domain)

    return sorted(list(domains))
```

### 6. Workshop Preview Renderer

```python
def _render_workshop_preview(
    coach_id: str,
    manifest: Dict[str, Any],
    data_mode: str,
    context: DevWriteContext
) -> None:
    """
    Render workshop preview with manifest-driven widgets.
    """
    st.markdown("---")
    st.subheader("Right Pane Preview")

    # Get simulator state
    intent = st.session_state.get("workshop_intent")
    rr_values = st.session_state.get("workshop_rr", {})
    curiosity_values = st.session_state.get("workshop_curiosity", {})
    user_id = st.session_state.get("workshop_user_id", "TEST")

    # Resolve layout (apply intent overrides, evaluate conditions)
    visible_widgets = _resolve_workshop_layout(manifest, intent, rr_values, curiosity_values)

    if not visible_widgets:
        st.info("No widgets visible with current intent/RR configuration. Adjust simulator values.")
        return

    # Render status strip
    st.caption(
        f"**{len(visible_widgets)} widgets visible** | "
        f"Intent: {intent or 'none'} | "
        f"Data mode: {data_mode} | "
        f"User: {user_id}"
    )

    # Render each widget
    for widget in visible_widgets:
        _render_workshop_widget(widget, data_mode, user_id, context)


def _resolve_workshop_layout(
    manifest: Dict[str, Any],
    intent: Optional[str],
    rr_values: Dict[str, float],
    curiosity_values: Dict[str, float]
) -> List[Dict[str, Any]]:
    """
    Resolve visible widgets based on intent and RR/curiosity values.
    Mimics production layout resolution logic.
    """
    widgets = manifest.get("widgets", []).copy()

    # 1. Apply intent layout overrides
    if intent and intent in manifest.get("intent_layouts", {}):
        layout = manifest["intent_layouts"][intent]

        # Handle priority_boost
        boost_ids = layout.get("priority_boost", [])
        for widget in widgets:
            if widget["id"] in boost_ids:
                widget["_priority_boosted"] = True
                widget["position"] = widget.get("position", 0) - 100  # Move to top

        # Handle hide
        hide_ids = layout.get("hide", [])
        widgets = [w for w in widgets if w["id"] not in hide_ids]

        # Handle show (force visible even if default_visible=false)
        show_ids = layout.get("show", [])
        for widget in widgets:
            if widget["id"] in show_ids:
                widget["_forced_visible"] = True

    # 2. Evaluate conditions
    visible_widgets = []
    for widget in widgets:
        if _evaluate_widget_conditions(widget, intent, rr_values, curiosity_values):
            visible_widgets.append(widget)

    # 3. Sort by position
    visible_widgets.sort(key=lambda w: w.get("position", 999))

    return visible_widgets


def _evaluate_widget_conditions(
    widget: Dict[str, Any],
    intent: Optional[str],
    rr_values: Dict[str, float],
    curiosity_values: Dict[str, float]
) -> bool:
    """
    Evaluate all widget conditions (AND logic).
    Returns True if all conditions pass.
    """
    conditions = widget.get("conditions", [])

    if not conditions:
        return widget.get("default_visible", True) or widget.get("_forced_visible", False)

    for condition in conditions:
        cond_type = condition.get("type")

        if cond_type == "intent":
            required_intents = condition.get("intent", [])
            if intent not in required_intents:
                return False

        elif cond_type == "rr_threshold":
            threshold = condition.get("rr_threshold", {})
            domain = threshold.get("domain")
            operator = threshold.get("operator", ">=")
            value = threshold.get("value", 0.0)

            if domain not in rr_values:
                return False  # Missing data

            user_rr = rr_values[domain]

            if operator == ">=":
                if not (user_rr >= value):
                    return False
            elif operator == ">":
                if not (user_rr > value):
                    return False
            elif operator == "<=":
                if not (user_rr <= value):
                    return False
            elif operator == "<":
                if not (user_rr < value):
                    return False
            elif operator == "==":
                if not (user_rr == value):
                    return False

        elif cond_type == "curiosity_threshold":
            threshold = condition.get("curiosity_threshold", {})
            domain = threshold.get("domain")
            operator = threshold.get("operator", ">=")
            value = threshold.get("value", 0.0)

            if domain not in curiosity_values:
                return False

            user_curiosity = curiosity_values[domain]

            if operator == ">=":
                if not (user_curiosity >= value):
                    return False
            elif operator == ">":
                if not (user_curiosity > value):
                    return False
            # ... (other operators)

        elif cond_type == "data_available":
            # In Workshop, simulate data availability
            # For now, assume data is available if RR > 0
            data_check = condition.get("data_available", {})
            path = data_check.get("path", "")
            domain = path.split(".")[1] if "." in path else path

            if domain not in rr_values or rr_values[domain] == 0:
                return False

        # Other condition types (feature_flag, user_pref) can be added later

    return True


def _render_workshop_widget(
    widget: Dict[str, Any],
    data_mode: str,
    user_id: str,
    context: DevWriteContext
) -> None:
    """
    Render a single widget in workshop preview mode.
    """
    widget_id = widget["id"]
    widget_title = widget.get("title", widget_id)
    widget_component = widget.get("component", "Unknown")

    with st.expander(f"📦 {widget_title}", expanded=True):
        # Widget metadata
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.caption(f"**Component:** `{widget_component}`")
            st.caption(f"**ID:** `{widget_id}`")

        with col2:
            st.caption(f"**Type:** {widget.get('type', 'unknown')}")
            st.caption(f"**Position:** {widget.get('position', '?')}")

        with col3:
            if widget.get("_priority_boosted"):
                st.success("⬆️ Priority Boosted")
            if widget.get("_forced_visible"):
                st.info("👁️ Force Visible")

        # Data source info
        data_source = widget.get("data_source", {})
        if data_source:
            st.markdown("**Data Source**")
            ds_col1, ds_col2 = st.columns([1, 2])

            with ds_col1:
                st.caption(f"Type: `{data_source.get('type', 'unknown')}`")
                st.caption(f"Cache: `{data_source.get('cache_ttl', 0)}s`")

            with ds_col2:
                if data_source.get("type") == "api":
                    endpoint = data_source.get("endpoint", "")
                    st.code(f"{data_source.get('method', 'GET')} {endpoint}", language="http")

        # Widget preview area
        st.markdown("**Widget Preview**")

        if data_mode == "Stubbed":
            # Load fixture data
            fixture_data = _load_widget_fixture(widget, user_id)
            if fixture_data:
                st.json(fixture_data)
                st.caption("↑ Fixture data (stubbed mode)")
            else:
                st.info(f"No fixture data available for {widget_id}")

        elif data_mode == "Live":
            st.info(f"Live mode: would call {data_source.get('endpoint', '?')} for user {user_id}")
            st.caption("(Live API calls not implemented in Workshop yet)")

        else:  # Hybrid
            st.info("Hybrid mode: live RR/Curiosity + stubbed widget data")

        # AI suggestions (if enabled)
        ai_config = widget.get("ai_suggestions", {})
        if ai_config.get("enabled"):
            st.markdown("**AI Suggestions**")
            st.caption(f"Policy gate: `{ai_config.get('policy_gate', 'none')}`")
            st.caption(f"Max suggestions: {ai_config.get('max_suggestions', 0)}")
            if ai_config.get("shadow_mode"):
                st.warning("⚠️ Shadow mode: suggestions logged but not displayed")


def _load_widget_fixture(widget: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    """Load fixture data for widget in stubbed mode."""
    # Placeholder - would load from workshop_fixtures/*.json
    return {
        "status": "stubbed",
        "widget_id": widget["id"],
        "user_id": user_id,
        "data": "(fixture data would be loaded here)"
    }
```

### 7. Telemetry Panel

```python
def _render_telemetry_panel(manifest: Dict[str, Any]) -> None:
    """
    Display performance telemetry and targets.
    """
    with st.expander("📊 Performance Telemetry", expanded=False):
        perf_targets = manifest.get("performance", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Compose Target",
                f"{perf_targets.get('compose_target_ms', 200)}ms",
                help="Time from manifest load to first widget render"
            )

        with col2:
            st.metric(
                "FCP Target",
                f"{perf_targets.get('fcp_target_ms', 300)}ms",
                help="First Contentful Paint for right pane"
            )

        with col3:
            st.metric(
                "Max API Calls",
                perf_targets.get("max_api_calls", 3),
                help="Maximum concurrent API calls"
            )

        st.caption("⏱️ Actual metrics would be measured during rendering")
```

## File Changes Summary

### Modified Files
1. **`ExplorerDev/explorer_dev.py`**
   - Update `_show_persona_registry()` to add source switcher tabs
   - Add new functions:
     - `_render_delegation_workshop()`
     - `_load_delegation_coaches()`
     - `_load_and_validate_manifest()`
     - `_render_intent_rr_simulator()`
     - `_extract_domains_from_manifest()`
     - `_render_workshop_preview()`
     - `_resolve_workshop_layout()`
     - `_evaluate_widget_conditions()`
     - `_render_workshop_widget()`
     - `_load_widget_fixture()`
     - `_render_telemetry_panel()`

### New Files
None (all changes in existing `explorer_dev.py`)

### Dependencies
- `jsonschema` - For manifest validation (add to requirements if missing)

## Testing Checklist

- [ ] Workshop loads with source switcher (Personas | Delegation)
- [ ] Legacy Personas tab shows existing coaches (PaDNA, Photo, RC)
- [ ] Delegation tab loads coaches from `coach_registry.yaml`
- [ ] Career Coach manifest loads and validates
- [ ] PTC manifest loads and validates
- [ ] Intent selector populates from manifest `intent_layouts`
- [ ] RR sliders extract domains from manifest conditions
- [ ] Widget visibility respects intent conditions
- [ ] Widget visibility respects RR threshold conditions
- [ ] Widget visibility respects curiosity threshold conditions
- [ ] Priority boost works (widgets move to top)
- [ ] Hide/show overrides work
- [ ] Stubbed data mode shows placeholder data
- [ ] Telemetry panel displays performance targets
- [ ] Manifest validation errors display clearly

## Migration Notes

- **No breaking changes** - Legacy persona tab continues to work unchanged
- **Opt-in migration** - Coaches can adopt manifests incrementally
- **Coach without manifest** - Shows warning + instructions to create manifest
- **Fixture data** - Stubbed mode requires workshop fixtures; can be generated manually or via "Generate fixture from live" button (future enhancement)

## Next Steps

1. Implement source switcher UI (`_show_persona_registry` update)
2. Implement `_render_delegation_workshop()` core logic
3. Add manifest loading and validation
4. Build intent/RR simulator
5. Implement layout resolution logic
6. Add widget preview rendering
7. Test with Career Coach and PTC manifests
8. Document widget development workflow
9. Add "Export manifest" and "Generate fixture" features (phase 2)

---

**References:**
- `RPUF_ARCHITECTURE.md` - Overall RPUF design
- `coach_ui_manifest.schema.json` - Manifest validation schema
- `ReDNACoreDemo/coaches/*/coach_ui_manifest.yaml` - Example manifests
