from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
import streamlit as st

from ui.nav import render_top_nav, side_nav

# Ensure PhotoRefinementCoach packages are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for candidate in (
    PROJECT_ROOT,
    PROJECT_ROOT / "PhotoRefinementCoach",
    PROJECT_ROOT / "PhotoRefinementCoach" / "src",
):
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in st.session_state.get("_vision_diag_sys_path", []):
        import sys

        sys.path.insert(0, candidate_str)
        st.session_state.setdefault("_vision_diag_sys_path", []).append(candidate_str)

try:  # pragma: no cover - runtime import
    from PhotoRefinementCoach.src.vision.model import (
        Llama3VisionAdapter,
        MockVision,
        RecencyTag,
        VisionModel,
        _prep_image,
    )
except Exception as exc:  # pragma: no cover - fall back with message
    Llama3VisionAdapter = MockVision = None  # type: ignore
    import_error = exc
else:
    import_error = None


def _check_endpoint(base_url: str) -> Dict[str, Any]:
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/version", timeout=2)
        return {"ok": resp.ok, "status": resp.status_code, "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text}
    except Exception as exc:  # pragma: no cover - network failure
        return {"ok": False, "error": str(exc)}


def _analyze_photo(adapter_name: str, base_url: str, model_name: str, image_bytes: bytes) -> Dict[str, Any]:
    adapter: VisionModel
    if adapter_name == "llama3-vision" and Llama3VisionAdapter is not None:
        adapter = Llama3VisionAdapter()
        # override env driven options
        adapter.host = base_url.rstrip("/")
        adapter.model = model_name
    else:
        adapter = MockVision()

    jpeg, _ = _prep_image(image_bytes)
    image_b64 = base64.b64encode(jpeg).decode("utf-8")

    raw_response = None
    try:
        raw_response = adapter._chat(image_b64) if hasattr(adapter, "_chat") else None  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - diagnostics
        raw_response = {"error": str(exc)}

    observation = adapter.analyze(image_bytes, RecencyTag.RECENT)
    tokens = observation.tokens

    return {
        "model_name": observation.model_name,
        "model_version": observation.model_version,
        "tokens": tokens,
        "raw": raw_response,
    }


def main() -> None:
    st.set_page_config(page_title="Vision Diagnostics", layout="wide")
    side_nav(active="vision_diag")
    render_top_nav(active="vision_diag")

    st.title("🔍 Vision Diagnostics")
    st.caption("Use this sandbox to call the vision adapter directly and inspect its output.")

    if import_error:
        st.error(f"Failed to import PhotoRefinementCoach adapter utilities: {import_error}")
        st.stop()

    default_base = st.session_state.get("vision_diag_base", "http://127.0.0.1:11434")
    default_model = st.session_state.get("vision_diag_model", "llama3.2-vision")

    config_col, status_col = st.columns([0.6, 0.4])
    with config_col:
        base_url = st.text_input("Vision service base URL", value=default_base, help="Root URL of the Ollama vision endpoint.")
        model_name = st.text_input("Vision model name", value=default_model, help="Model identifier to send in the request (e.g., llama3.2-vision).")
        adapter_choice = st.selectbox("Adapter", ["llama3-vision", "mock-vision"], help="Use mock for offline sanity checks.")
        st.session_state["vision_diag_base"] = base_url
        st.session_state["vision_diag_model"] = model_name

    with status_col:
        endpoint_status = _check_endpoint(base_url)
        if endpoint_status.get("ok"):
            st.success(f"Endpoint reachable (status {endpoint_status.get('status')})")
            if endpoint_status.get("data"):
                st.json(endpoint_status["data"], expanded=False)
        else:
            st.warning(f"Endpoint check failed: {endpoint_status.get('error') or endpoint_status.get('status')}")

    st.divider()
    uploaded_files = st.file_uploader(
        "Upload 1..N photos for analysis",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="vision_diag_uploader",
    )

    run_clicked = st.button("Run vision analysis", type="primary", use_container_width=False)

    if not run_clicked:
        st.stop()

    if not uploaded_files:
        st.info("Add at least one photo before running analysis.")
        st.stop()

    results: List[Dict[str, Any]] = []
    for uploaded in uploaded_files:
        try:
            payload_bytes = uploaded.getvalue()
        except Exception:
            payload_bytes = uploaded.read()
        if not payload_bytes:
            st.warning(f"Skipping empty file: {uploaded.name}")
            continue
        try:
            result = _analyze_photo(adapter_choice, base_url, model_name, payload_bytes)
            result["filename"] = uploaded.name
            results.append(result)
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            results.append({"filename": uploaded.name, "error": str(exc)})

    if not results:
        st.error("No analyzable photos processed.")
        st.stop()

    for result in results:
        st.subheader(result.get("filename", "Photo"))
        cols = st.columns([0.4, 0.6])
        with cols[0]:
            st.write(f"Model: {result.get('model_name')} ({result.get('model_version')})")
            tokens = result.get("tokens") or {}
            if tokens:
                st.markdown("**Extracted traits**")
                for path, meta in tokens.items():
                    value = meta.get("value")
                    conf = meta.get("confidence")
                    st.write(f"- `{path}` → {value} (conf {conf})")
            else:
                st.warning("No traits returned. See diagnostics for details.")
        with cols[1]:
            st.markdown("**Raw response**")
            raw = result.get("raw")
            if isinstance(raw, (dict, list)):
                st.code(json.dumps(raw, indent=2), language="json")
            elif isinstance(raw, str):
                st.code(raw, language="text")
            else:
                st.write(raw)

    st.success("Vision analysis complete. Use these diagnostics to refine the adapter prompt or service configuration.")


if __name__ == "__main__":  # pragma: no cover
    main()
