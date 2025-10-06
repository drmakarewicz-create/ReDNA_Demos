from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

from src.vision.model import RecencyTag


PHOTO_IMPORT_STRICT = os.getenv("PHOTO_IMPORT_STRICT", "false").lower() == "true"
DEFAULT_SOFT_IMPORT_ENABLED = not PHOTO_IMPORT_STRICT

@dataclass
class PhotoItem:
    name: str
    recency: RecencyTag
    data: Optional[bytes] = None
    timestamp_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None

@dataclass
class CoachState:
    user_id: str = "user-demo"
    snapshot_id: str = "snap-1"
    photos: List[PhotoItem] = field(default_factory=list)
    previous_bundle: Optional[Dict[str, Any]] = None
    last_bundle: Optional[Dict[str, Any]] = None
    last_aggregate: Optional[Dict[str, Any]] = None
    last_result: Optional[Dict[str, Any]] = None
    notes: str = ""
    import_payload: Optional[Dict[str, Any]] = None
    import_report: Optional[Dict[str, Any]] = None
    import_errors: List[str] = field(default_factory=list)
    import_warnings: List[str] = field(default_factory=list)
    import_preview: List[Dict[str, Any]] = field(default_factory=list)
    import_filename: Optional[str] = None
    import_status: Optional[Dict[str, Any]] = None
    import_compute_rr: bool = True
    import_use_inbound_rr: bool = False
    import_large_confirmed: bool = False
    import_digest: Optional[str] = None
    import_soft_enabled: bool = DEFAULT_SOFT_IMPORT_ENABLED
    import_assisted: List[Dict[str, Any]] = field(default_factory=list)
    import_quarantined: List[Dict[str, Any]] = field(default_factory=list)
    import_counts: Dict[str, int] = field(default_factory=dict)
    import_raw_payload: Optional[Dict[str, Any]] = None
    import_raw_text: Optional[str] = None

def get_state() -> CoachState:
    if "coach_state" not in st.session_state:
        st.session_state.coach_state = CoachState()
    return st.session_state.coach_state
