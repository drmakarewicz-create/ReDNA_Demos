"""Developer Tools UI components for Explorer."""

from __future__ import annotations

import streamlit as st
from typing import Optional

from ExplorerDev.test_runner_utils import (
    find_test_files,
    find_test_functions,
    get_test_file_display_name,
    load_test_history,
    run_pytest,
)
from ExplorerDev.artifact_browser_utils import (
    find_all_artifacts,
    find_user_artifacts,
    get_user_list,
    load_recent_artifacts,
    read_artifact_content,
    track_recent_artifact,
)
from ExplorerDev.log_tail_utils import (
    LOG_SOURCES,
    get_log_tail,
    get_server_pids,
    save_test_output,
)


def render_dev_tools(context=None) -> None:
    """Render Developer Tools section."""
    st.header("🧰 Developer Tools")
    st.caption("Test runner, log tails, artifact browser, HTTP helpers, system settings")

    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧪 Test Runner",
        "📜 Log Tails",
        "📁 Artifact Browser",
        "🌐 HTTP Helpers",
        "⚙️ System Settings",
    ])

    with tab1:
        _render_test_runner()

    with tab2:
        _render_log_tails()

    with tab3:
        _render_artifact_browser()

    with tab4:
        _render_http_helpers()

    with tab5:
        _render_system_settings(context)


def _render_test_runner() -> None:
    """Render Test Runner tab."""
    st.subheader("Test Runner")

    # Find test files
    test_files = find_test_files()

    if not test_files:
        st.warning("No test_*acceptance*.py files found in repo root")
        return

    # Test file selector
    col1, col2 = st.columns([2, 1])

    with col1:
        test_file_options = {
            str(f.relative_to(f.parents[1])): get_test_file_display_name(f)
            for f in test_files
        }

        selected_file = st.selectbox(
            "Test File",
            options=list(test_file_options.keys()),
            format_func=lambda x: test_file_options[x],
            key="dev_tools_test_file",
        )

    with col2:
        verbose_mode = st.checkbox("Verbose (-v)", value=True, key="dev_tools_verbose")

    # Test function selector
    if selected_file:
        from pathlib import Path
        test_functions = find_test_functions(Path(selected_file))

        if test_functions:
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                test_function = st.selectbox(
                    "Test Function (optional)",
                    options=["[All Tests]"] + test_functions,
                    key="dev_tools_test_function",
                )

            with col2:
                run_all_btn = st.button("▶️ Run All", use_container_width=True, type="primary")

            with col3:
                run_single_btn = st.button(
                    "▶️ Run Selected",
                    use_container_width=True,
                    disabled=(test_function == "[All Tests]"),
                )

            # Run tests
            if run_all_btn or run_single_btn:
                test_name = None if (run_all_btn or test_function == "[All Tests]") else test_function

                with st.spinner(f"Running {'all tests' if not test_name else test_name}..."):
                    result = run_pytest(
                        test_file=selected_file,
                        test_name=test_name,
                        verbose=verbose_mode,
                    )

                    # Save output for log viewer
                    save_test_output(result.stdout + "\n" + result.stderr)

                # Display results
                st.divider()

                # Status header
                status_col1, status_col2, status_col3, status_col4 = st.columns(4)

                with status_col1:
                    st.metric("Status", result.status)

                with status_col2:
                    st.metric("Passed", result.passed)

                with status_col3:
                    st.metric("Failed", result.failed)

                with status_col4:
                    st.metric("Duration", f"{result.duration_sec}s")

                # Output display
                output_tabs = st.tabs(["📊 Summary", "📝 Full Output", "⚠️ Errors"])

                with output_tabs[0]:
                    # Extract summary lines
                    summary_lines = []
                    for line in result.stdout.split("\n"):
                        if "PASSED" in line or "FAILED" in line or "ERROR" in line or "====" in line:
                            summary_lines.append(line)

                    if summary_lines:
                        st.code("\n".join(summary_lines[-20:]), language="text")
                    else:
                        st.info("No summary available")

                with output_tabs[1]:
                    st.code(result.stdout, language="text", line_numbers=False)

                with output_tabs[2]:
                    if result.stderr:
                        st.code(result.stderr, language="text")
                    else:
                        st.success("No errors")

        else:
            # No test functions found, just show run all button
            if st.button("▶️ Run All Tests", type="primary"):
                with st.spinner(f"Running {selected_file}..."):
                    result = run_pytest(
                        test_file=selected_file,
                        verbose=verbose_mode,
                    )

                    save_test_output(result.stdout + "\n" + result.stderr)

                st.divider()
                st.metric("Status", result.status)
                st.code(result.stdout, language="text")

    # Test history
    st.divider()
    st.subheader("Recent Test Runs")

    history = load_test_history(limit=10)

    if history:
        for entry in history:
            with st.expander(
                f"{entry.get('test_file', 'Unknown')} - {entry.get('timestamp', '')} - "
                f"{'✅' if entry.get('exit_code', 1) == 0 else '❌'}"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Passed", entry.get("passed", 0))
                with col2:
                    st.metric("Failed", entry.get("failed", 0))
                with col3:
                    st.metric("Duration", f"{entry.get('duration_sec', 0)}s")

                if entry.get("test_name"):
                    st.caption(f"Test: {entry['test_name']}")
    else:
        st.info("No test runs yet")


def _render_log_tails() -> None:
    """Render Log Tails tab."""
    st.subheader("Log Tails")

    # Log source selector
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        log_source = st.selectbox(
            "Log Source",
            options=list(LOG_SOURCES.keys()),
            format_func=lambda k: LOG_SOURCES[k].name,
            key="dev_tools_log_source",
        )

    with col2:
        auto_refresh = st.checkbox("Auto-refresh (5s)", value=False, key="dev_tools_auto_refresh")

    with col3:
        refresh_btn = st.button("🔄 Refresh", use_container_width=True)

    # Display log source info
    if log_source:
        source = LOG_SOURCES[log_source]
        st.caption(source.description)

        # Get log content
        if auto_refresh or refresh_btn or st.session_state.get("_dev_tools_first_load", True):
            st.session_state["_dev_tools_first_load"] = False

            content, status = get_log_tail(log_source, max_lines=200)

            # Store in session state
            st.session_state[f"_log_content_{log_source}"] = content
            st.session_state[f"_log_status_{log_source}"] = status

            # Auto-refresh logic
            if auto_refresh:
                st.rerun()

        # Display content
        content = st.session_state.get(f"_log_content_{log_source}", "")
        status = st.session_state.get(f"_log_status_{log_source}", "empty")

        if status == "ok":
            # Action buttons
            action_col1, action_col2 = st.columns([1, 6])

            with action_col1:
                if st.button("📋 Copy"):
                    st.code(content, language="text")
                    st.success("Content displayed above - use browser copy")

            with action_col2:
                if st.button("🗑️ Clear View"):
                    st.session_state[f"_log_content_{log_source}"] = ""
                    st.rerun()

            # Display log
            st.code(content, language="text", line_numbers=False)

        elif status == "empty":
            st.info(content)
        else:
            st.error(content)

    # Server status panel
    st.divider()
    st.subheader("Server Status")

    server_pids = get_server_pids()

    if server_pids:
        for pid, port in server_pids:
            st.success(f"✅ Uvicorn running on port {port} (PID: {pid})")
    else:
        st.warning("No uvicorn servers detected")
        st.caption("Expected: uvicorn ReDNACoreDemo.core.api:app --port 8001")


def _render_artifact_browser() -> None:
    """Render Artifact Browser tab."""
    st.subheader("Artifact Browser")

    # Search and filter
    col1, col2 = st.columns([3, 1])

    with col1:
        search_term = st.text_input(
            "Search artifacts",
            placeholder="Enter filename or path...",
            key="dev_tools_artifact_search",
        )

    with col2:
        filter_category = st.selectbox(
            "Category",
            options=["All", "User Data", "Automation Logs"],
            key="dev_tools_artifact_category",
        )

    # Recent artifacts quick access
    st.caption("**Recent Artifacts**")

    recent_paths = load_recent_artifacts()

    if recent_paths[:5]:
        recent_cols = st.columns(5)
        for idx, path in enumerate(recent_paths[:5]):
            with recent_cols[idx]:
                from pathlib import Path
                if st.button(
                    Path(path).name[:20],
                    key=f"recent_{idx}",
                    use_container_width=True,
                ):
                    st.session_state["_selected_artifact"] = path
                    st.rerun()
    else:
        st.caption("No recent artifacts")

    st.divider()

    # Find artifacts
    artifacts = find_all_artifacts(search_term=search_term if search_term else None)

    # Filter by category
    if filter_category == "User Data":
        artifacts = [a for a in artifacts if a.category == "user_data"]
    elif filter_category == "Automation Logs":
        artifacts = [a for a in artifacts if a.category == "automation_log"]

    # Display artifact list
    st.caption(f"**Found {len(artifacts)} artifacts**")

    if artifacts:
        # Limit display for performance
        display_artifacts = artifacts[:50]

        for artifact in display_artifacts:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                if st.button(
                    artifact.relative_path,
                    key=f"artifact_{artifact.relative_path}",
                    use_container_width=True,
                ):
                    st.session_state["_selected_artifact"] = artifact.relative_path
                    track_recent_artifact(artifact.relative_path)
                    st.rerun()

            with col2:
                st.caption(artifact.size_display)

            with col3:
                st.caption(artifact.modified_display)

            with col4:
                badge = "👤" if artifact.category == "user_data" else "📝"
                st.caption(badge)

        if len(artifacts) > 50:
            st.info(f"Showing first 50 of {len(artifacts)} artifacts. Use search to narrow results.")

    # Selected artifact viewer
    selected_artifact = st.session_state.get("_selected_artifact")

    if selected_artifact:
        st.divider()
        st.subheader(f"📄 {selected_artifact}")

        close_col1, close_col2 = st.columns([6, 1])

        with close_col2:
            if st.button("❌ Close"):
                del st.session_state["_selected_artifact"]
                st.rerun()

        content, file_type = read_artifact_content(selected_artifact, max_lines=500)

        if file_type == "error":
            st.error(content)
        else:
            # Determine language for syntax highlighting
            lang_map = {
                "json": "json",
                "jsonl": "json",
                "markdown": "markdown",
                "text": "text",
            }

            lang = lang_map.get(file_type, "text")

            st.code(content, language=lang, line_numbers=True)


def _render_http_helpers() -> None:
    """Render HTTP Helpers tab."""
    st.subheader("HTTP Request Builder")

    # Endpoint selector
    endpoints = {
        "/hc/say": {"method": "POST", "description": "Send user message to Head Coach"},
        "/hc/tasks/queue": {"method": "POST", "description": "Queue a new task"},
        "/hc/tasks/list": {"method": "GET", "description": "List user tasks"},
        "/hc/tasks/tick": {"method": "POST", "description": "Process pending tasks"},
        "/hc/playbooks/list": {"method": "GET", "description": "List available playbooks"},
        "/hc/playbooks/run": {"method": "POST", "description": "Run a playbook"},
        "/hc/conversation/history": {"method": "GET", "description": "Get conversation history"},
        "/hc/state": {"method": "GET", "description": "Get Head Coach state"},
    }

    col1, col2 = st.columns([3, 1])

    with col1:
        selected_endpoint = st.selectbox(
            "Endpoint",
            options=list(endpoints.keys()),
            format_func=lambda ep: f"{endpoints[ep]['method']} {ep} - {endpoints[ep]['description']}",
            key="dev_tools_endpoint",
        )

    with col2:
        base_url = st.text_input("Base URL", value="http://localhost:8001", key="dev_tools_base_url")

    # User ID input
    user_id = st.text_input("User ID", value="bstest", key="dev_tools_user_id")

    # Method and URL
    method = endpoints[selected_endpoint]["method"]
    full_url = f"{base_url.rstrip('/')}{selected_endpoint}?user_id={user_id}"

    st.caption(f"**Request:** `{method} {full_url}`")

    # Request body (for POST)
    request_body = None

    if method == "POST":
        st.subheader("Request Body (JSON)")

        # Template based on endpoint
        templates = {
            "/hc/say": '{"message": "What should I do next?", "role": "user"}',
            "/hc/tasks/queue": '{"description": "Test task", "priority": 5}',
            "/hc/tasks/tick": '{}',
            "/hc/playbooks/run": '{"playbook_id": "curiosity_campaign"}',
        }

        template = templates.get(selected_endpoint, "{}")

        request_body = st.text_area(
            "JSON Body",
            value=template,
            height=150,
            key="dev_tools_request_body",
        )

    # Send button
    if st.button(f"🚀 Send {method} Request", type="primary"):
        import requests
        import json

        try:
            # Parse request body if POST
            body_json = None
            if method == "POST" and request_body:
                body_json = json.loads(request_body)

            # Send request
            with st.spinner("Sending request..."):
                if method == "GET":
                    response = requests.get(full_url, timeout=10)
                else:
                    response = requests.post(
                        full_url,
                        json=body_json,
                        timeout=10,
                    )

            # Display response
            st.divider()
            st.subheader("Response")

            status_col1, status_col2 = st.columns([1, 4])

            with status_col1:
                status_color = "🟢" if response.status_code < 400 else "🔴"
                st.metric("Status", f"{status_color} {response.status_code}")

            with status_col2:
                st.caption(f"Content-Type: {response.headers.get('content-type', 'unknown')}")

            # Response body
            response_tabs = st.tabs(["📄 Formatted", "📝 Raw"])

            with response_tabs[0]:
                try:
                    response_json = response.json()
                    st.json(response_json)
                except Exception:
                    st.code(response.text, language="text")

            with response_tabs[1]:
                st.code(response.text, language="text")

        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON in request body: {exc}")
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
        except Exception as exc:
            st.error(f"Error: {exc}")

    # Quick links
    st.divider()
    st.subheader("Quick Actions")

    quick_col1, quick_col2, quick_col3 = st.columns(3)

    with quick_col1:
        if st.button("📊 Get HC State", use_container_width=True):
            st.session_state["dev_tools_endpoint"] = "/hc/state"
            st.rerun()

    with quick_col2:
        if st.button("💬 Say Hello", use_container_width=True):
            st.session_state["dev_tools_endpoint"] = "/hc/say"
            st.rerun()

    with quick_col3:
        if st.button("📋 List Tasks", use_container_width=True):
            st.session_state["dev_tools_endpoint"] = "/hc/tasks/list"
            st.rerun()


def _render_system_settings(context) -> None:
    """Render System Settings tab."""
    st.subheader("System Settings")
    st.caption("Holistic scheduler, soft imports, environment variables")

    if context is None:
        st.warning("Context not provided — write-protect status unknown")
        return

    # System settings tabs
    settings_tabs = st.tabs([
        "🕐 Holistic Scheduler",
        "📥 Soft Import Settings",
        "🔒 Write Protect",
        "🌍 Environment Variables",
    ])

    with settings_tabs[0]:
        _render_holistic_scheduler_settings(context)

    with settings_tabs[1]:
        _render_soft_import_settings(context)

    with settings_tabs[2]:
        _render_write_protect_settings(context)

    with settings_tabs[3]:
        _render_environment_variables()


def _render_holistic_scheduler_settings(context) -> None:
    """Render holistic scheduler configuration."""
    st.markdown("**Holistic Scheduler Configuration**")
    st.caption("Configure automated holistic review cadence")

    try:
        from ExplorerDev.scheduler_utils import load_scheduler_prefs, save_scheduler_prefs
    except ImportError:
        st.error("Unable to import scheduler_utils")
        return

    # Load current preferences
    prefs = load_scheduler_prefs()

    # Display current state
    enabled = prefs.get("enabled", False)
    cadence_hours = prefs.get("cadence_hours", 168)  # Default: weekly
    last_run = prefs.get("last_run", "Never")

    st.markdown(f"**Status:** {'🟢 Enabled' if enabled else '⚪ Disabled'}")
    st.markdown(f"**Cadence:** Every {cadence_hours} hours ({cadence_hours / 24:.1f} days)")
    st.markdown(f"**Last Run:** {last_run}")

    # Edit interface
    if not context.write_protect:
        st.markdown("---")
        st.markdown("**Edit Scheduler Settings**")

        col1, col2 = st.columns(2)
        with col1:
            new_enabled = st.checkbox("Enable Scheduler", value=enabled, key="_scheduler_enabled")
        with col2:
            new_cadence = st.number_input(
                "Cadence (hours)",
                min_value=1,
                max_value=720,  # 30 days
                value=cadence_hours,
                step=24,
                key="_scheduler_cadence",
            )

        if st.button("Save Scheduler Settings"):
            try:
                new_prefs = {
                    "enabled": new_enabled,
                    "cadence_hours": new_cadence,
                    "last_run": last_run,
                }
                save_scheduler_prefs(new_prefs, context)
                st.success("✅ Scheduler settings saved")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save settings: {exc}")

    else:
        st.info("Write-protect ON — settings are read-only")


def _render_soft_import_settings(context) -> None:
    """Render soft import configuration."""
    st.markdown("**Soft Import Settings**")
    st.caption("Configure PaDNA soft-import behavior")

    st.info("Soft import settings UI — coming soon")
    st.markdown("Configure how Explorer handles PaDNA imports from external sources")


def _render_write_protect_settings(context) -> None:
    """Render write-protect status and controls."""
    st.markdown("**Write Protect Status**")
    st.caption("Current write protection mode")

    import os

    write_protect_env = os.getenv("WRITE_PROTECT", "true")
    write_protect_status = context.write_protect if context else True

    if write_protect_status:
        st.success("🔒 Write-protect is ON")
        st.info(
            "Changes are isolated to dev paths: `data/dev_users/` and `persona_config/dev_overrides/`. "
            "Set `WRITE_PROTECT=false` environment variable to write to live storage."
        )
    else:
        st.warning("⚠️ Write-protect is OFF")
        st.error(
            "Changes will apply directly to live storage. Proceed with caution. "
            "Set `WRITE_PROTECT=true` environment variable to enable protection."
        )

    st.markdown(f"**Environment Variable:** `WRITE_PROTECT={write_protect_env}`")


def _render_environment_variables() -> None:
    """Render environment variable viewer."""
    st.markdown("**Environment Variables**")
    st.caption("View current ReDNA-related environment variables")

    import os

    # Key environment variables to display
    env_vars = {
        "WRITE_PROTECT": os.getenv("WRITE_PROTECT", "not set"),
        "CORE_BASE": os.getenv("CORE_BASE", "not set"),
        "CORE_CURIOSITY_ENABLED": os.getenv("CORE_CURIOSITY_ENABLED", "not set"),
        "HOLISTIC_SCHEDULER_ENABLED": os.getenv("HOLISTIC_SCHEDULER_ENABLED", "not set"),
        "HOLISTIC_CADENCE_HOURS": os.getenv("HOLISTIC_CADENCE_HOURS", "not set"),
        "REACT_BASE": os.getenv("REACT_BASE", "not set"),
        "CP_PLUS_PLUS_BASE": os.getenv("CP_PLUS_PLUS_BASE", "not set"),
    }

    # Display as table
    try:
        import pandas as pd
        df = pd.DataFrame([
            {"Variable": k, "Value": v}
            for k, v in env_vars.items()
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    except ImportError:
        for var, value in env_vars.items():
            st.markdown(f"**{var}**: `{value}`")
