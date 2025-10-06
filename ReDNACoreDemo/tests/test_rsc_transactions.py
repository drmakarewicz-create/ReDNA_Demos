from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ReDNACoreDemo.rsc import transactions as rsc_tx


@pytest.fixture(autouse=True)
def _temp_data_root(tmp_path, monkeypatch):
    data_root = tmp_path / "rsc_sessions"
    data_root.mkdir()
    monkeypatch.setattr(rsc_tx, "DATA_ROOT", data_root)
    yield


def _create_session(expiry_minutes: int = 30) -> rsc_tx.RscSession:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    return rsc_tx.create_transaction_rsc(
        "alpha",
        "beta",
        "trust_building",
        expires_at,
        "balanced",
        shared_context={"focus": "Support __PARTNER_NAME__ feeling heard."},
    )


def test_create_accept_post_and_expire():
    session = _create_session()
    path = rsc_tx.DATA_ROOT / f"{session.session_id}.json"
    assert path.exists()

    rsc_tx.accept_rsc(session.session_id, "beta", session.consent_token)
    rsc_tx.post_micro_action(
        session.session_id,
        "alpha",
        {"type": "prompt", "text": "Ask for a 2-minute highlight."},
        honesty_level="gentle",
    )

    refreshed = rsc_tx.session_snapshot(session.session_id)
    assert refreshed["accepted"]
    assert len(refreshed["log"]) == 1

    rsc_tx.expire_session(session.session_id)

    with pytest.raises(rsc_tx.RscSessionError):
        rsc_tx.post_micro_action(
            session.session_id,
            "alpha",
            {"type": "prompt", "text": "Check-in message"},
            honesty_level="gentle",
        )


def test_revocation_and_honesty_guard():
    session = _create_session()
    rsc_tx.accept_rsc(session.session_id, "beta", session.consent_token)

    with pytest.raises(rsc_tx.RscSessionError):
        rsc_tx.post_micro_action(
            session.session_id,
            "alpha",
            {"type": "prompt", "text": "Too candid"},
            honesty_level="candid",
        )

    rsc_tx.revoke_session(session.session_id, "alpha", "boundary change")

    with pytest.raises(rsc_tx.RscSessionError):
        rsc_tx.post_micro_action(
            session.session_id,
            "alpha",
            {"type": "prompt", "text": "Should be blocked"},
            honesty_level="gentle",
        )
