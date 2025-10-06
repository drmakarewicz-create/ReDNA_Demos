#!/usr/bin/env python3
"""Streamlit demo for the PaDNA Outbound avatar renderer."""

from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st

from src.vision.palette_loader import load_palettes
from src.vision.renderer_v2 import render_svg

st.set_page_config(page_title="PaDNA Outbound Avatar", page_icon="🎨", layout="wide")
st.title("🎨 PaDNA Outbound Avatar Renderer")

left, right = st.columns([0.4, 0.6])

bundle: Dict[str, Any] = {}

with left:
    st.subheader("Load bundle")
    option = st.radio(
        "Source",
        ["Explorer bundle", "Photo Coach output", "Raw JSON"],
        index=0,
        help="Any payload that includes results.descriptors or padna map will work.",
    )

    uploaded = st.file_uploader("Upload JSON", type=["json"])
    if uploaded is not None:
        try:
            candidate = json.load(uploaded)
            if option == "Photo Coach output" and "bundle" in candidate:
                bundle = candidate["bundle"]
            else:
                bundle = candidate
            st.success("Bundle loaded.")
        except Exception as exc:  # pragma: no cover - user input branch
            st.error(f"Could not parse JSON: {exc}")

    with st.expander("Sample payloads", expanded=False):
        st.caption("Drop any of these into the uploader if you want to experiment quickly.")
        st.markdown("- `PhotoRefinementCoach/samples/photo_set_A/explorer_bundle.json`")
        st.markdown("- `PaDNAOutboundDemo/samples/explorer_bundle_padna_sample_A.json`")
        st.markdown("- `PaDNAOutboundDemo/samples/explorer_bundle_padna_sample_B.json`")

with right:
    st.subheader("Avatar preview")
    if not bundle:
        st.info("Upload a bundle to render an avatar. The renderer is read-only and does not call Core.")
    else:
        palettes = load_palettes()
        skin_options = sorted((palettes.get("skin") or {}).keys()) or ["fair_neutral"]
        hair_options = sorted((palettes.get("hair") or {}).keys()) or ["medium_brown"]
        eye_options = sorted((palettes.get("eyes") or {}).keys()) or ["brown_light"]
        lip_options = sorted((palettes.get("lips") or {}).keys()) or ["natural_pink"]
        brow_options = sorted((palettes.get("brows") or {}).keys()) or ["medium_brown"]
        accent_options = sorted((palettes.get("accent") or {}).keys()) or ["neutral"]

        # Establish per-bundle session config so palette overrides persist between rerenders.
        config_state_key = "padna_renderer_config"
        bundle_sig_key = "padna_renderer_signature"
        try:
            bundle_signature = hash(json.dumps(bundle, sort_keys=True, default=str))
        except TypeError:
            bundle_signature = hash(str(bundle))

        if st.session_state.get(bundle_sig_key) != bundle_signature:
            initial_result = render_svg(bundle)
            st.session_state[config_state_key] = {
                "theme": initial_result["config"].get("theme", "flat_cartoon"),
                "palette_keys": initial_result["config"].get("palette_keys", {}),
                "feature_toggles": initial_result["config"].get("feature_toggles", {}),
                "debug_layers": initial_result["config"].get("debug_layers", False),
            }
            st.session_state[bundle_sig_key] = bundle_signature

        config = st.session_state.get(config_state_key, {})
        palette_keys = config.get("palette_keys", {})
        feature_toggles = config.get("feature_toggles", {})

        st.markdown("### Theme & appearance")
        col_theme, col_debug = st.columns([0.7, 0.3])
        with col_theme:
            selected_theme = st.selectbox(
                "Theme",
                ["flat_cartoon", "shaded", "line_art"],
                index=["flat_cartoon", "shaded", "line_art"].index(config.get("theme", "flat_cartoon")),
            )
        with col_debug:
            debug_layers = st.checkbox("Debug layers", value=config.get("debug_layers", False))

        st.markdown("##### Palette overrides")
        skin_choice = st.selectbox(
            "Skin palette",
            skin_options,
            index=max(0, skin_options.index(palette_keys.get("skin", skin_options[0])) if palette_keys.get("skin") in skin_options else 0),
        )
        hair_choice = st.selectbox(
            "Hair palette",
            hair_options,
            index=max(0, hair_options.index(palette_keys.get("hair", hair_options[0])) if palette_keys.get("hair") in hair_options else 0),
        )
        eye_choice = st.selectbox(
            "Eye palette",
            eye_options,
            index=max(0, eye_options.index(palette_keys.get("eyes", eye_options[0])) if palette_keys.get("eyes") in eye_options else 0),
        )
        brow_choice = st.selectbox(
            "Brow palette",
            brow_options,
            index=max(0, brow_options.index(palette_keys.get("brows", brow_options[0])) if palette_keys.get("brows") in brow_options else 0),
        )
        lip_choice = st.selectbox(
            "Lip palette",
            lip_options,
            index=max(0, lip_options.index(palette_keys.get("lips", lip_options[0])) if palette_keys.get("lips") in lip_options else 0),
        )
        accent_choice = st.selectbox(
            "Accent palette",
            accent_options,
            index=max(0, accent_options.index(palette_keys.get("accent", accent_options[0])) if palette_keys.get("accent") in accent_options else 0),
        )

        st.markdown("##### Feature toggles")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            show_ears = st.checkbox("Ears", value=feature_toggles.get("show_ears", False))
        with col2:
            show_neck_ring = st.checkbox("Neck ring", value=feature_toggles.get("show_neck_ring", False))
        with col3:
            show_cheek_shade = st.checkbox("Cheek shade", value=feature_toggles.get("show_cheek_shade", True))
        with col4:
            show_hair_shadow = st.checkbox("Hair shadow", value=feature_toggles.get("show_hair_shadow", True))
        with col5:
            show_freckles = st.checkbox("Freckles", value=feature_toggles.get("show_freckles", True))

        # Update bundle renderer config prior to rendering.
        updated_config = {
            "theme": selected_theme,
            "palette_keys": {
                "skin": skin_choice,
                "hair": hair_choice,
                "eyes": eye_choice,
                "brows": brow_choice,
                "lips": lip_choice,
                "accent": accent_choice,
            },
            "feature_toggles": {
                "show_ears": show_ears,
                "show_neck_ring": show_neck_ring,
                "show_cheek_shade": show_cheek_shade,
                "show_hair_shadow": show_hair_shadow,
                "show_freckles": show_freckles,
            },
            "debug_layers": debug_layers,
        }

        bundle["renderer"] = updated_config
        st.session_state[config_state_key] = updated_config

        result = render_svg(bundle)
        st.markdown(
            f"<div style='text-align:center;'>"
            f"<img src='{result['data_url']}' alt='PaDNA avatar' width='360' />"
            f"</div>",
            unsafe_allow_html=True,
        )
        palette_summary = result.get("palette", {})
        st.caption(
            "Palette → Skin: {skin}, Hair: {hair}, Eyes: {eyes}, Accent: {accent}".format(
                skin=palette_summary.get("skin", {}).get("fill", "?"),
                hair=palette_summary.get("hair", {}).get("base", "?"),
                eyes=palette_summary.get("eyes", {}).get("iris", "?"),
                accent=palette_summary.get("accent", {}).get("primary", "?"),
            )
        )

        st.download_button(
            "Download SVG",
            data=result["svg"],
            file_name="padna_avatar.svg",
            mime="image/svg+xml",
        )

        with st.expander("Descriptor inputs", expanded=False):
            st.json(result.get("padna", {}), expanded=False)

        with st.expander("Renderer metadata", expanded=False):
            st.json(
                {
                    "posture": result.get("posture"),
                    "tattoos": result.get("tattoos"),
                    "config": result.get("config"),
                    "apparel": result.get("apparel"),
                },
                expanded=False,
            )

        debug_payload = result.get("debug", {})
        if debug_payload:
            with st.expander("Trait mapping debug", expanded=False):
                notes = debug_payload.get("mapping_notes", [])
                if notes:
                    st.markdown("**Mapping notes**")
                    for note in notes:
                        st.write(f"- {note}")
                st.markdown("**Traits used**")
                st.json(debug_payload.get("traits_used", {}), expanded=False)
                st.markdown("**Palette keys**")
                st.json(debug_payload.get("palette_keys", {}), expanded=False)

st.markdown("---")
st.subheader("API usage")
st.code(
    """curl -X POST http://localhost:8055/render \
  -H 'Content-Type: application/json' \
  -d '{"bundle": {...}}'""",
    language="bash",
)
st.caption("See `PaDNAOutboundDemo/api.py` for the FastAPI implementation.")
