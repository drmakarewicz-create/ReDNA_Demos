"""Relationship Synergy Coach transactional session scaffolding."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data" / "rsc_sessions"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

class RscSessionError(RuntimeError):
    """Raised when RSC session operations fail."""


@dataclass(slots=True)
class RscLogEntry:
    ts: str
    author_id: str
    payload: Dict[str, Any]


@dataclass(slots=True)
class RscRevocation:
    ts: str
    actor_id: str
    reason: str


@dataclass(slots=True)
class RscSession:
    session_id: str
    creator_id: str
    partner_id: str
    scope: str
    honesty_ceiling: str
    created_at: str
    expires_at: str
    consent_token: str
    accepted: bool = False
    accepted_at: Optional[str] = None
    revoked: bool = False
    revocations: List[RscRevocation] = field(default_factory=list)
    log: List[RscLogEntry] = field(default_factory=list)
    shared_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["revocations"] = [asdict(entry) for entry in self.revocations]
        payload["log"] = [asdict(entry) for entry in self.log]
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RscSession":
        revocations = [RscRevocation(**item) for item in payload.get("revocations", [])]
        log = [RscLogEntry(**item) for item in payload.get("log", [])]
        return cls(
            session_id=payload["session_id"],
            creator_id=payload["creator_id"],
            partner_id=payload["partner_id"],
            scope=payload["scope"],
            honesty_ceiling=payload["honesty_ceiling"],
            created_at=payload["created_at"],
            expires_at=payload["expires_at"],
            consent_token=payload["consent_token"],
            accepted=payload.get("accepted", False),
            accepted_at=payload.get("accepted_at"),
            revoked=payload.get("revoked", False),
            revocations=revocations,
            log=log,
            shared_context=payload.get("shared_context", {}),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    if not value:
        raise ValueError("empty timestamp")
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _path_for(session_id: str) -> Path:
    safe = session_id.replace("..", "_")
    return DATA_ROOT / f"{safe}.json"


def _load(session_id: str) -> RscSession:
    path = _path_for(session_id)
    if not path.exists():
        raise RscSessionError(f"Session '{session_id}' not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return RscSession.from_dict(data)


def _save(session: RscSession) -> None:
    path = _path_for(session.session_id)
    path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")


def _is_expired(session: RscSession) -> bool:
    try:
        expires = _parse_iso(session.expires_at)
    except Exception:
        return False
    return datetime.now(timezone.utc) >= expires


def _ensure_participant(session: RscSession, user_id: str) -> None:
    if user_id not in {session.creator_id, session.partner_id}:
        raise RscSessionError("User is not part of this RSC session")


def _redact_partner_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = value.replace(session_sensitive_marker(), "[partner]")
        else:
            sanitized[key] = value
    return sanitized


def session_sensitive_marker() -> str:
    return "__PARTNER_NAME__"


def _honesty_rank(level: str) -> int:
    order = ["gentle", "balanced", "direct", "candid"]
    try:
        return order.index(level)
    except ValueError:
        return len(order)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_sessions() -> List[RscSession]:
    sessions: List[RscSession] = []
    for path in DATA_ROOT.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(RscSession.from_dict(data))
        except Exception:
            continue
    return sorted(sessions, key=lambda s: s.created_at)


def create_transaction_rsc(
    creator_id: str,
    partner_id: str,
    scope: str,
    expires_at: Any,
    honesty_ceiling: str,
    *,
    shared_context: Optional[Dict[str, Any]] = None,
) -> RscSession:
    if not creator_id or not partner_id:
        raise RscSessionError("Both creator and partner ids are required")
    if creator_id == partner_id:
        raise RscSessionError("Creator and partner must be different users")

    created_at = _iso_now()
    if isinstance(expires_at, str):
        expires_iso = _to_iso(_parse_iso(expires_at))
    elif isinstance(expires_at, datetime):
        expires_iso = _to_iso(expires_at)
    else:
        raise RscSessionError("expires_at must be datetime or ISO string")
    session_id = secrets.token_hex(8)
    consent_token = secrets.token_urlsafe(12)

    session = RscSession(
        session_id=session_id,
        creator_id=creator_id,
        partner_id=partner_id,
        scope=scope,
        honesty_ceiling=honesty_ceiling,
        created_at=created_at,
        expires_at=expires_iso,
        consent_token=consent_token,
        shared_context=_redact_partner_context(shared_context or {}),
    )
    _save(session)
    return session


def accept_rsc(session_id: str, user_id: str, token: str) -> RscSession:
    session = _load(session_id)
    if session.revoked:
        raise RscSessionError("Session has been revoked")
    if session.accepted:
        return session
    if token != session.consent_token:
        raise RscSessionError("Invalid consent token")
    if user_id != session.partner_id:
        raise RscSessionError("Only the invited partner can accept")
    if _is_expired(session):
        raise RscSessionError("Session already expired")

    session.accepted = True
    session.accepted_at = _iso_now()
    _save(session)
    return session


def post_micro_action(
    session_id: str,
    author_id: str,
    action: Dict[str, Any],
    *,
    honesty_level: Optional[str] = None,
) -> RscSession:
    session = _load(session_id)
    if session.revoked:
        raise RscSessionError("Session revoked")
    if _is_expired(session):
        raise RscSessionError("Session expired")
    if not session.accepted:
        raise RscSessionError("Session not yet accepted")
    _ensure_participant(session, author_id)

    if honesty_level:
        if _honesty_rank(honesty_level) > _honesty_rank(session.honesty_ceiling):
            raise RscSessionError("Honesty level exceeds session ceiling")

    entry = RscLogEntry(ts=_iso_now(), author_id=author_id, payload=action)
    session.log.append(entry)
    _save(session)
    return session


def revoke_session(session_id: str, actor_id: str, reason: str) -> RscSession:
    session = _load(session_id)
    _ensure_participant(session, actor_id)
    session.revoked = True
    session.revocations.append(RscRevocation(ts=_iso_now(), actor_id=actor_id, reason=reason))
    _save(session)
    return session


def expire_session(session_id: str) -> RscSession:
    session = _load(session_id)
    session.expires_at = _iso_now()
    _save(session)
    return session


def session_snapshot(session_id: str, viewer_id: Optional[str] = None) -> Dict[str, Any]:
    session = _load(session_id)
    snapshot = session.to_dict()
    snapshot["expired"] = _is_expired(session)
    if viewer_id and viewer_id not in {session.creator_id, session.partner_id}:
        raise RscSessionError("Viewer not part of session")
    if viewer_id == session.partner_id:
        snapshot["shared_context"] = _redact_partner_context(session.shared_context)
    return snapshot


def shared_feed(session_id: str) -> List[Dict[str, Any]]:
    session = _load(session_id)
    return [asdict(entry) for entry in session.log]


__all__ = [
    "RscSession",
    "RscSessionError",
    "create_transaction_rsc",
    "accept_rsc",
    "post_micro_action",
    "revoke_session",
    "expire_session",
    "session_snapshot",
    "shared_feed",
    "list_sessions",
]
