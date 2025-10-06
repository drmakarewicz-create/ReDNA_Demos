from __future__ import annotations
import io, json, hashlib
from typing import Dict, Any
import streamlit as st
from PIL import Image
from src.ui.session import CoachState, PhotoItem
from src.vision.model import RecencyTag

def _img_hash(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()[:16]

def _preview_image(data: bytes, caption: str, width: int = 140):
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        st.image(im, caption=caption, width=width)
    except Exception:
        st.text(caption)

def photos_uploader(state: CoachState):
    st.markdown("Upload photos of **the same person**. Label each with recency.")
    up = st.file_uploader(
        "Add 1..N face/torso photos (JPG/PNG)",
        type=["jpg","jpeg","png"],
        accept_multiple_files=True,
        key="photos_uploader",
    )

    # Initialize a set of hashes we already have (prevents duplicates on rerun)
    existing = { getattr(p, "name", "") + ":" + getattr(p, "hash", "") for p in state.photos }

    if up:
        for f in up:
            raw = f.read()
            h = _img_hash(raw)
            key = f.name + ":" + h
            if key in existing:
                continue
            state.photos.append(PhotoItem(name=f.name, recency=RecencyTag.RECENT, data=raw))
            setattr(state.photos[-1], "hash", h)
            existing.add(key)

    if not state.photos:
        return

    cols = st.columns([0.25, 0.5, 0.25])
    with cols[0]:
        if st.button("Clear all photos", use_container_width=True):
            state.photos.clear()
            st.experimental_rerun()
    with cols[1]:
        st.caption(f"{len(state.photos)} photo(s) ready")
    with cols[2]:
        pass

    # Per-photo controls
    for idx, p in enumerate(state.photos):
        with st.expander(f"{p.name} ({getattr(p, 'hash', 'no-hash')})", expanded=False):
            row = st.columns([0.25, 0.4, 0.2, 0.15])
            with row[0]:
                _preview_image(p.data, p.name)
            with row[1]:
                state.photos[idx].recency = st.selectbox(
                    "Recency",
                    options=[RecencyTag.RECENT, RecencyTag.OLD, RecencyTag.RETRO],
                    index=[RecencyTag.RECENT, RecencyTag.OLD, RecencyTag.RETRO].index(p.recency),
                    key=f"rec_{idx}"
                )
                state.photos[idx].notes = st.text_area(
                    "Photo notes (optional)",
                    value=p.notes or "",
                    key=f"note_{idx}",
                    height=60
                )
            with row[2]:
                st.write(f"Size: {len(p.data or b'')//1024} KB")
                st.caption(f"Captured: {getattr(p, 'timestamp_iso', '—')}")
            with row[3]:
                if st.button("Remove", key=f"rm_{idx}"):
                    state.photos.pop(idx)
                    st.experimental_rerun()

    st.markdown("---")
    st.markdown("**Optional: Upload a previous explorer bundle to refine**")
    prev = st.file_uploader("Previous explorer_bundle.json", type=["json"], accept_multiple_files=False, key="prev_bundle")
    if prev is not None:
        try:
            state.previous_bundle = json.loads(prev.read().decode("utf-8"))
            st.success("Previous bundle loaded – new run will refine it conceptually (aggregation only).")
        except Exception as e:
            st.warning(f"Could not parse JSON: {e}")

def show_refinement_plots(aggregate: Dict[str, Any]):
    import pandas as pd
    import streamlit as st
    curve = aggregate.get("ucn_curve", [])
    if not curve: return
    df = pd.DataFrame(curve)
    st.markdown("**Refinement curves (per trait)**")
    st.line_chart(df.pivot(index="n_photos", columns="trait", values="ucn"), height=260)

def download_buttons(bundle: Dict[str, Any]):
    import json
    st.download_button(
        "Download explorer_bundle.json",
        data=json.dumps(bundle, indent=2),
        file_name="explorer_bundle.json",
        mime="application/json"
    )
