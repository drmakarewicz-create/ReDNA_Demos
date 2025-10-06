"""Actionable Nudge Inbox for the main Explorer UI."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional, Set, Mapping

import streamlit as st

from ExplorerFinal.core import nudge_store
from ExplorerFinal.ui.components import compact_mode_enabled, render_css_once, render_chips, ChipSpec

_DEV_TRUE = {"1", "true", "yes", "on"}
WRITE_PROTECT = os.getenv("WRITE_PROTECT", "true").strip().lower() in _DEV_TRUE
ACTIONS_ENABLED = os.getenv("NUDGE_ACTIONS_ENABLED", "false").strip().lower() in _DEV_TRUE
FEEDBACK_ENABLED = os.getenv("FEEDBACK_ENABLED", "true").strip().lower() in _DEV_TRUE
DELIVER_TO_CHAT = os.getenv("NUDGE_DELIVER_TO_CHAT", "false").strip().lower() in _DEV_TRUE
RATE_LIMIT = int(os.getenv("NUDGE_RATE_LIMIT_PER_MIN", "20") or "20")

_STATUS_OPTIONS = {
    "Inbox": "inbox",
    "Snoozed": "inbox_snoozed",
    "Accepted": "accepted",
    "Dismissed": "dismissed",
    "Expired (inbox)": "expired_inbox",
    "All": "all",
}

_SNOOZE_MINUTES_DEFAULT = int(os.getenv("NUDGE_SNOOZE_MIN", "120") or "120")
_TTL_MINUTES_DEFAULT = int(os.getenv("NUDGE_TTL_MIN", "1440") or "1440")


def _status_badge(label: str, value: str, *, color: str) -> str:
    safe = value or "—"
    return (
        "<span style='display:inline-flex;align-items:center;padding:0.1rem 0.45rem;"
        "margin-right:0.35rem;border-radius:999px;font-size:0.7rem;font-weight:600;color:#fff;"
        f"background:{color};'><strong>{label}:</strong> {safe}</span>"
    )


def _rate_state(user_id: str) -> Dict[str, Any]:
    if not ACTIONS_ENABLED:
        return {"ok": False, "remaining": 0, "retry_in": 0}
    return nudge_store.enforce_rate_limit(
        user_id,
        action="accept",
        limit_per_minute=RATE_LIMIT,
        write_protect=WRITE_PROTECT,
    )


def _chunk(seq: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [seq[idx : idx + size] for idx in range(0, len(seq), size)]


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        value = datetime.fromisoformat(ts)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _format_remaining(seconds: float) -> str:
    minutes = max(int(seconds // 60), 1)
    if minutes >= 1440:
        return f"{minutes // 1440}d"
    if minutes >= 120:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def _ttl_badge(bundle: Dict[str, Any]) -> str:
    expiry = _parse_iso(bundle.get("expires_at"))
    if expiry is None:
        return ""
    now = datetime.now(timezone.utc)
    remaining = (expiry - now).total_seconds()
    if remaining <= 0:
        return _status_badge("TTL", "Expired", color="#dc3545")
    return _status_badge("TTL", _format_remaining(remaining), color="#20c997")


def _resume_badge(bundle: Dict[str, Any]) -> str:
    resume = _parse_iso(bundle.get("resume_at"))
    if resume is None:
        return ""
    now = datetime.now(timezone.utc)
    remaining = (resume - now).total_seconds()
    if remaining <= 0:
        return _status_badge("Resume", "due", color="#ffc107")
    return _status_badge("Resume", _format_remaining(remaining), color="#ffc107")


def _cohort_badge(bundle: Dict[str, Any]) -> str:
    cohort = bundle.get("cohort")
    if not cohort:
        return ""
    color = "#4e79a7" if cohort == "A" else "#e15759"
    return _status_badge("Cohort", str(cohort), color=color)


def _render_motivator_text(text: Optional[str], *, compact: bool) -> None:
    if not text:
        st.write("(empty)")
        return
    trimmed = text.strip()
    if not trimmed:
        st.write("(empty)")
        return
    if compact and len(trimmed) > 260:
        preview = trimmed[:220].rstrip() + "…"
        tooltip = escape(trimmed).replace("\n", " &#10;")
        st.markdown(
            f"<div title='{tooltip}'>{escape(preview)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.write(trimmed)


def _render_bundle_card(
    user_id: str,
    bundle: Dict[str, Any],
    *,
    index: int,
    selected_ids: Set[str],
    rerun_key: str,
    snooze_minutes: int,
    compact: bool,
) -> None:
    persona = bundle.get("persona_id") or "?"
    ts = bundle.get("ts") or "?"
    mode = bundle.get("mode") or "sim"
    status = bundle.get("status") or "inbox"
    snapshot_id = bundle.get("snapshot_id")
    bundle_id = str(bundle.get("id") or f"bundle_{index}")
    expired = bool(bundle.get("expired"))

    status_color = {
        "inbox": "#6f42c1",
        "inbox_snoozed": "#6c757d",
        "accepted": "#28a745",
        "dismissed": "#343a40",
    }.get(status, "#6f42c1")
    if expired and status == "inbox":
        status_color = "#dc3545"

    header = (
        f"{_status_badge('Persona', persona, color='#17a2b8')}"
        f"{_status_badge('Mode', mode, color='#28a745')}"
        f"{_status_badge('Status', status, color=status_color)}"
        f"{_status_badge('Timestamp', ts, color='#1f77b4')}"
    )
    if snapshot_id:
        header += _status_badge("Snapshot", snapshot_id, color="#fd7e14")
    ttl_badge = _ttl_badge(bundle)
    if ttl_badge:
        header += ttl_badge
    if status == "inbox_snoozed":
        resume_badge = _resume_badge(bundle)
        if resume_badge:
            header += resume_badge
    cohort_badge = _cohort_badge(bundle)
    if cohort_badge:
        header += cohort_badge

    with st.container(border=True):
        if ACTIONS_ENABLED:
            weights = [0.1, 0.9] if compact else [0.08, 0.92]
            select_cols = st.columns(weights)
            with select_cols[0]:
                checked = bundle_id in selected_ids
                new_checked = st.checkbox(
                    "",
                    value=checked,
                    key=f"select_{bundle_id}",
                    help="Include this bundle in batch actions.",
                )
                if new_checked:
                    selected_ids.add(bundle_id)
                else:
                    selected_ids.discard(bundle_id)
            with select_cols[1]:
                st.markdown(header, unsafe_allow_html=True)
        else:
            st.markdown(header, unsafe_allow_html=True)

        tone_meta = bundle.get("tone_meta")
        if tone_meta:
            st.caption(str(tone_meta))

        items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
        if not items:
            st.info("This bundle contains no motivators.")
        else:
            for idx, item in enumerate(items, start=1):
                container = str(item.get("container") or "")
                trait_id = str(item.get("trait_id") or "")
                trait_path = (
                    f"{container}.{trait_id}"
                    if container and trait_id
                    else trait_id or container or "trait"
                )
                template_source = str(item.get("template_source") or "—")
                chips = (
                    f"{_status_badge('Trait', trait_path, color='#20c997')}"
                    f"{_status_badge('Template', template_source, color='#ffc107')}"
                )
                st.markdown(chips, unsafe_allow_html=True)
                _render_motivator_text(item.get("text"), compact=compact)

        if ACTIONS_ENABLED:
            _render_bundle_actions(
                user_id,
                bundle,
                rerun_key=rerun_key,
                snooze_minutes=snooze_minutes,
            )
        else:
            st.caption(
                "Actions disabled · set NUDGE_ACTIONS_ENABLED=true in CP+ to enable editing."
            )

        if FEEDBACK_ENABLED:
            flash_key = f"_feedback_flash_{bundle_id}"
            note_toggle_key = f"_feedback_note_open_{bundle_id}"
            note_text_key = f"_feedback_note_text_{bundle_id}"

            flash_state = st.session_state.pop(flash_key, None)
            if isinstance(flash_state, dict):
                message = flash_state.get("message") or "Feedback recorded."
                status = flash_state.get("status")
                if status == "error":
                    st.error(message)
                elif status == "dry":
                    st.info(message)
                else:
                    st.success(message)

            def _submit_feedback(rating: str) -> None:
                note_value = st.session_state.get(note_text_key, "").strip()
                traits_payload: List[Dict[str, Any]] = []
                for item in bundle.get("items", []):
                    if not isinstance(item, Mapping):
                        continue
                    traits_payload.append(
                        {
                            "container": item.get("container") or item.get("container_id"),
                            "trait_id": item.get("trait_id") or item.get("trait"),
                        }
                    )
                try:
                    result = nudge_store.log_feedback(
                        user_id=user_id,
                        nudge_id=bundle_id,
                        persona_id=str(bundle.get("persona_id") or ""),
                        rating=rating,
                        note=note_value,
                        mode=str(bundle.get("mode") or "sim"),
                        snapshot_id=bundle.get("snapshot_id"),
                        traits=traits_payload,
                        write_protect=WRITE_PROTECT,
                    )
                except ValueError as exc:
                    st.session_state[flash_key] = {"status": "error", "message": str(exc)}
                else:
                    if result.get("dry_run"):
                        st.session_state[flash_key] = {
                            "status": "dry",
                            "message": "Dry-run: feedback stored in session only.",
                        }
                    else:
                        st.session_state[flash_key] = {
                            "status": "ok",
                            "message": "Feedback recorded.",
                        }
                st.session_state[note_text_key] = ""
                st.session_state[note_toggle_key] = False

            feedback_cols = st.columns([0.2, 0.2, 0.6])
            with feedback_cols[0]:
                if st.button("✅ Helpful", key=f"feedback_helpful_{bundle_id}"):
                    _submit_feedback("helpful")
            with feedback_cols[1]:
                if st.button("❌ Not Helpful", key=f"feedback_not_helpful_{bundle_id}"):
                    _submit_feedback("not_helpful")
            with feedback_cols[2]:
                if st.button("📝 Add Note", key=f"feedback_note_toggle_{bundle_id}"):
                    st.session_state[note_toggle_key] = not st.session_state.get(note_toggle_key, False)
                if st.session_state.get(note_toggle_key, False):
                    st.text_area(
                        "Optional note",
                        key=note_text_key,
                        placeholder="Share context for the coach inbox...",
                        height=80,
                    )
                    st.caption("Notes are saved alongside your next feedback rating.")

        provenance = bundle.get("provenance") if isinstance(bundle.get("provenance"), dict) else {}
        with st.expander("Provenance & meta", expanded=False):
            st.markdown(
                f"- **Persona:** {persona}\n"
                f"- **Snapshot:** {snapshot_id or '—'}\n"
                f"- **Cohort:** {bundle.get('cohort') or '—'}\n"
                f"- **TTL:** {bundle.get('ttl_minutes', _TTL_MINUTES_DEFAULT)} min"
            )
            if tone_meta:
                st.markdown("- **Tone meta:**")
                st.json(tone_meta)
            st.markdown("- **Raw provenance:**")
            st.json(provenance or {"note": "No provenance captured."})


def _render_bundle_actions(
    user_id: str,
    bundle: Dict[str, Any],
    *,
    rerun_key: str,
    snooze_minutes: int,
) -> None:
    cols = st.columns(4)
    bundle_id = str(bundle.get("id"))
    status = bundle.get("status")
    info_placeholder = st.empty()

    rate_state = _rate_state(user_id)
    rate_blocked = not rate_state.get("ok", False)
    rate_tooltip = (
        "Enable NUDGE_ACTIONS_ENABLED in CP+ to modify the inbox"
        if not ACTIONS_ENABLED
        else (
            f"Rate limit reached · try again in {rate_state.get('retry_in', 0)}s"
            if rate_blocked
            else f"Remaining actions this minute: {rate_state.get('remaining', RATE_LIMIT)}"
        )
    )

    with cols[0]:
        accepted_disabled = (not ACTIONS_ENABLED) or status == "accepted" or rate_blocked
        if st.button(
            "Accept",
            key=f"accept_{bundle_id}_{rerun_key}",
            disabled=accepted_disabled,
            help=rate_tooltip,
        ):
            if rate_blocked:
                st.warning(rate_tooltip)
            else:
                result = nudge_store.accept(
                    user_id,
                	bundle_id,
                    write_protect=WRITE_PROTECT,
                    deliver_to_chat=DELIVER_TO_CHAT,
                )
                if result.get("ok"):
                    info_placeholder.success("Accepted and queued for delivery.")
                    st.experimental_rerun()
                elif result.get("duplicate"):
                    info_placeholder.info("Ignored duplicate click — action already processed.")
                else:
                    info_placeholder.error(f"Accept failed: {result.get('error', 'unknown error')}")

    with cols[1]:
        dismissed_disabled = (not ACTIONS_ENABLED) or status == "dismissed" or rate_blocked
        if st.button(
            "Dismiss",
            key=f"dismiss_{bundle_id}_{rerun_key}",
            disabled=dismissed_disabled,
            help=rate_tooltip,
        ):
            if rate_blocked:
                st.warning(rate_tooltip)
            else:
                result = nudge_store.dismiss(
                    user_id,
                    bundle_id,
                    write_protect=WRITE_PROTECT,
                )
                if result.get("ok"):
                    info_placeholder.success("Dismissed.")
                    st.experimental_rerun()
                elif result.get("duplicate"):
                    info_placeholder.info("Ignored duplicate click — action already processed.")
                else:
                    info_placeholder.error(f"Dismiss failed: {result.get('error', 'unknown error')}")

    with cols[2]:
        if status == "inbox_snoozed":
            resume_disabled = not ACTIONS_ENABLED
            if st.button(
                "Resume",
                key=f"resume_{bundle_id}_{rerun_key}",
                disabled=resume_disabled,
                help="Return this bundle to the inbox.",
            ):
                result = nudge_store.resume(
                    user_id,
                    bundle_id,
                    write_protect=WRITE_PROTECT,
                )
                if result.get("ok"):
                    info_placeholder.info("Bundle resumed to inbox.")
                    st.experimental_rerun()
                elif result.get("duplicate"):
                    info_placeholder.info("Resume already processed.")
                else:
                    info_placeholder.error(f"Resume failed: {result.get('error', 'unknown error')}")
        else:
            snooze_disabled = (not ACTIONS_ENABLED) or status != "inbox"
            snooze_label = f"Snooze {snooze_minutes}m"
            if st.button(
                snooze_label,
                key=f"snooze_{bundle_id}_{rerun_key}",
                disabled=snooze_disabled,
                help=f"Hide for {snooze_minutes} minutes.",
            ):
                result = nudge_store.snooze(
                    user_id,
                    bundle_id,
                    minutes=snooze_minutes,
                    write_protect=WRITE_PROTECT,
                )
                if result.get("ok"):
                    info_placeholder.info("Snoozed.")
                    st.experimental_rerun()
                elif result.get("duplicate"):
                    info_placeholder.info("Already snoozed recently.")
                else:
                    info_placeholder.error(f"Snooze failed: {result.get('error', 'unknown error')}")

    with cols[3]:
        undo_disabled = (not ACTIONS_ENABLED) or status == "inbox"
        if st.button(
            "Undo",
            key=f"undo_{bundle_id}_{rerun_key}",
            disabled=undo_disabled,
            help="Revert the last accept/dismiss" if ACTIONS_ENABLED else "Enable NUDGE_ACTIONS_ENABLED to modify inbox.",
        ):
            result = nudge_store.undo(
                user_id,
                bundle_id,
                write_protect=WRITE_PROTECT,
                deliver_to_chat=DELIVER_TO_CHAT,
            )
            if result.get("ok"):
                info_placeholder.info("Reverted to inbox.")
                st.experimental_rerun()
            else:
                info_placeholder.error(f"Undo failed: {result.get('error', 'unknown error')}")


def render_nudge_inbox(*, default_user: str, active_user: str | None = None) -> None:
    compact_mode, _ = compact_mode_enabled()
    render_css_once(compact=compact_mode)
    st.markdown("### Nudge Inbox")
    description = "Manage bundles staged by Dev Explorer."
    st.caption(description)
    st.caption(f"Default TTL {_TTL_MINUTES_DEFAULT} min · Snooze {_SNOOZE_MINUTES_DEFAULT} min")

    if WRITE_PROTECT:
        st.warning("Write-protect ON — all inbox updates run in dry-run mode (no disk writes).")

    user_default = active_user or default_user
    user_id = st.text_input(
        "User id",
        value=user_default,
        key="nudge_inbox_user",
        help="Choose whose inbox to inspect.",
    ).strip()
    if not user_id:
        st.info("Enter a user id to view their inbox.")
        return

    status_label = st.selectbox(
        "Show",
        list(_STATUS_OPTIONS.keys()),
        index=0,
        key="nudge_status_filter",
    )
    status_filter = _STATUS_OPTIONS[status_label]

    list_filter = status_filter if status_filter != "expired_inbox" else "all"
    bundles = nudge_store.list_inbox(
        user_id,
        status_filter=list_filter,
        limit=200,
        write_protect=WRITE_PROTECT,
    )
    if status_filter == "expired_inbox":
        bundles = [
            bundle
            for bundle in bundles
            if bundle.get("status") == "inbox" and bundle.get("expired")
        ]

    expired_inbox_total = sum(
        1 for bundle in bundles if bundle.get("status") == "inbox" and bundle.get("expired")
    )
    snoozed_total = sum(1 for bundle in bundles if bundle.get("status") == "inbox_snoozed")

    if ACTIONS_ENABLED:
        rate_state_overview = _rate_state(user_id)
        remaining = int(rate_state_overview.get("remaining", RATE_LIMIT))
        used = max(0, RATE_LIMIT - remaining)
        retry_hint = rate_state_overview.get("retry_in")
        tooltip = (
            f"Rate limit resets in {retry_hint}s"
            if rate_state_overview.get("ok") is False and retry_hint
            else "Actions allowed per minute"
        )
        chips: List[ChipSpec] = [
            ChipSpec(label="Rate", value=f"{used}/{RATE_LIMIT}", color="#ff9f1c", tooltip=tooltip)
        ]
        if expired_inbox_total:
            chips.append(
                ChipSpec(
                    label="Expired",
                    value=str(expired_inbox_total),
                    color="#dc3545",
                    tooltip="Inbox bundles past TTL",
                )
            )
        if snoozed_total:
            chips.append(
                ChipSpec(
                    label="Snoozed",
                    value=str(snoozed_total),
                    color="#6c757d",
                    tooltip="Inbox bundles currently snoozed",
                )
            )
        render_chips(chips)

        if expired_inbox_total:
            if st.button(
                f"Dismiss expired ({expired_inbox_total})",
                key="dismiss_expired_btn",
                help="Dismiss inbox bundles past their TTL.",
            ):
                result = nudge_store.dismiss_expired(
                    user_id,
                    write_protect=WRITE_PROTECT,
                )
                if result.get("dismissed"):
                    st.success(
                        f"Dismissed {len(result['dismissed'])} expired bundle(s)."
                    )
                    st.experimental_rerun()
                else:
                    st.info("No expired bundles to dismiss.")

    search_term = st.text_input(
        "Search persona / trait / text",
        value=st.session_state.get("_nudge_search", ""),
        key="_nudge_search",
        help="Filter bundles by persona id, trait path, or motivator text.",
    ).strip()

    if search_term:
        lower = search_term.lower()

        def _matches(bundle: Dict[str, Any]) -> bool:
            persona = str(bundle.get("persona_id") or "").lower()
            if lower in persona:
                return True
            items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                container = str(item.get("container") or "").lower()
                trait_id = str(item.get("trait_id") or "").lower()
                text = str(item.get("text") or "").lower()
                path = f"{container}.{trait_id}" if container and trait_id else trait_id or container
                if lower in path or lower in text:
                    return True
            return False

        bundles = [bundle for bundle in bundles if _matches(bundle)]
        st.caption(f"Filtered results for '{search_term}' — {len(bundles)} bundle(s).")
    else:
        st.caption(
            "Showing newest bundles first. Status key: inbox · snoozed · accepted · dismissed."
        )

    source_map = {"From Core": "live", "Simulated": "simulated"}
    selected_sources = st.multiselect(
        "Source",
        list(source_map.keys()),
        key="_nudge_source_filter",
        help="Filter motivators by live vs simulated source.",
    )
    if selected_sources:
        allowed_sources = {source_map[label] for label in selected_sources}
        filtered_bundles: List[Dict[str, Any]] = []
        for bundle in bundles:
            items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
            if any(isinstance(item, dict) and item.get("source") in allowed_sources for item in items):
                filtered_bundles.append(bundle)
        bundles = filtered_bundles

    template_options = ["live", "draft", "fallback"]
    selected_templates = st.multiselect(
        "Template",
        template_options,
        key="_nudge_template_filter",
        help="Filter by template source.",
    )
    if selected_templates:
        filtered_templates: List[Dict[str, Any]] = []
        for bundle in bundles:
            items = bundle.get("items") if isinstance(bundle.get("items"), list) else []
            if any(
                isinstance(item, dict)
                and str(item.get("template_source") or "").lower() in selected_templates
                for item in items
            ):
                filtered_templates.append(bundle)
        bundles = filtered_templates

    cohort_choices = st.multiselect(
        "Cohort",
        ["A", "B", "None"],
        key="_nudge_cohort_filter",
        help="Filter bundles by assigned cohort.",
    )
    if cohort_choices:
        allowed_cohorts = {choice for choice in cohort_choices}
        bundles = [
            bundle
            for bundle in bundles
            if (bundle.get("cohort") or "None") in allowed_cohorts
        ]

    if not bundles:
        st.info(f"No nudge bundles found for `{user_id}` in this view.")
        return

    selection_map = st.session_state.setdefault("_nudge_selected_ids", {})
    selected_ids = set(selection_map.get(user_id, []))
    bundle_lookup = {str(bundle.get("id")): bundle for bundle in bundles if bundle.get("id")}
    selected_ids &= set(bundle_lookup.keys())

    batch_feedback = st.empty()
    if ACTIONS_ENABLED:
        accept_candidates = [
            bid for bid in selected_ids if bundle_lookup[bid].get("status") == "inbox"
        ]
        dismiss_candidates = [
            bid
            for bid in selected_ids
            if bundle_lookup[bid].get("status") in {"inbox", "inbox_snoozed"}
        ]
        batch_cols = st.columns([0.15, 0.18, 0.18, 0.18, 0.31])
        select_all_clicked = batch_cols[0].button(
            "Select all",
            help="Select all visible bundles in this view.",
        )
        accept_selected = batch_cols[1].button(
            "Accept selected",
            disabled=not bool(accept_candidates),
            help="Accept all selected inbox bundles respecting the rate limit.",
        )
        dismiss_selected = batch_cols[2].button(
            "Dismiss selected",
            disabled=not bool(dismiss_candidates),
            help="Dismiss all selected inbox bundles respecting the rate limit.",
        )
        clear_selected = batch_cols[3].button("Clear selection", help="Uncheck all bundles.")
        csv_bytes, json_bytes = nudge_store.export_visible(user_id, bundles)
        export_disabled = WRITE_PROTECT
        with batch_cols[4]:
            st.download_button(
                "Export CSV",
                data=csv_bytes,
                file_name=f"{user_id}_nudges.csv",
                mime="text/csv",
                disabled=export_disabled,
            )
            st.download_button(
                "Export JSON",
                data=json_bytes,
                file_name=f"{user_id}_nudges.json",
                mime="application/json",
                disabled=export_disabled,
            )

        if select_all_clicked:
            selected_ids = set(bundle_lookup.keys())
            selection_map[user_id] = list(selected_ids)
            st.experimental_rerun()

        if accept_selected:
            successes: List[str] = []
            skipped: List[str] = []
            errors: List[str] = []
            for bid in accept_candidates:
                rate = _rate_state(user_id)
                if not rate.get("ok", False):
                    skipped.append(bid)
                    break
                result = nudge_store.accept(
                    user_id,
                    bid,
                    write_protect=WRITE_PROTECT,
                    deliver_to_chat=DELIVER_TO_CHAT,
                )
                if result.get("ok"):
                    successes.append(bid)
                elif result.get("duplicate"):
                    continue
                else:
                    errors.append(bid)
            if successes:
                batch_feedback.success(f"Accepted {len(successes)} bundle(s): {', '.join(successes)}")
            if skipped:
                batch_feedback.warning(
                    f"Stopped — rate limit reached before processing {', '.join(skipped)}."
                )
            if errors:
                batch_feedback.error(f"Errors processing: {', '.join(errors)}")
            st.experimental_rerun()

        if dismiss_selected:
            successes = []
            skipped = []
            errors = []
            for bid in dismiss_candidates:
                rate = _rate_state(user_id)
                if not rate.get("ok", False):
                    skipped.append(bid)
                    break
                result = nudge_store.dismiss(
                    user_id,
                    bid,
                    write_protect=WRITE_PROTECT,
                )
                if result.get("ok"):
                    successes.append(bid)
                elif result.get("duplicate"):
                    continue
                else:
                    errors.append(bid)
            if successes:
                batch_feedback.success(f"Dismissed {len(successes)} bundle(s): {', '.join(successes)}")
            if skipped:
                batch_feedback.warning(
                    f"Stopped — rate limit reached before processing {', '.join(skipped)}."
                )
            if errors:
                batch_feedback.error(f"Errors processing: {', '.join(errors)}")
            st.experimental_rerun()

        if clear_selected:
            selected_ids.clear()
            selection_map[user_id] = []
            st.experimental_rerun()

    log_file = nudge_store.get_enqueue_log_path()
    mailbox_root = getattr(nudge_store, "MAILBOX_ROOT", None)
    if mailbox_root is not None:
        st.caption(f"Mailbox dir: {(mailbox_root / user_id).as_posix()}")
    if not WRITE_PROTECT and log_file.exists():
        st.caption(f"Enqueue log: {log_file.as_posix()}")

    render_index = 1
    if compact_mode:
        for pair in _chunk(bundles, 2):
            cols = st.columns(len(pair))
            for col, bundle in zip(cols, pair):
                with col:
                    _render_bundle_card(
                        user_id,
                        bundle,
                        index=render_index,
                        selected_ids=selected_ids,
                        rerun_key=str(render_index),
                        snooze_minutes=_SNOOZE_MINUTES_DEFAULT,
                        compact=True,
                    )
                render_index += 1
    else:
        for index, bundle in enumerate(bundles, start=1):
            _render_bundle_card(
                user_id,
                bundle,
                index=index,
                selected_ids=selected_ids,
                rerun_key=str(index),
                snooze_minutes=_SNOOZE_MINUTES_DEFAULT,
                compact=False,
            )

    selection_map[user_id] = list(selected_ids)


__all__ = ["render_nudge_inbox"]
