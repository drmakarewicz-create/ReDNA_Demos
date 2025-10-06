import re
from pathlib import Path

from ExplorerFinal.ui.tone.rc_filters import BAN, scrub


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def test_rc_tone_is_human():
    opener = (PROMPTS_DIR / "relationship_coach" / "opening.md").read_text(encoding="utf-8")
    cleaned = scrub(opener)
    assert not any(banned in cleaned for banned in BAN)
    segments = [seg.strip() for seg in re.split(r"[.!?]", cleaned) if seg.strip()]
    assert segments, "Opening prompt should yield sentences"
    assert max(len(seg.split()) for seg in segments) <= 22
