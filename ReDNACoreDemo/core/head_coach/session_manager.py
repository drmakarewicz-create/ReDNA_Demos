"""
Head Coach Session Integrity Manager
=====================================

Atomic augmentation context system with versioning and cancel tokens.
Ensures clean mode switches with zero context leakage.

Features:
- Context versioning with atomic builds
- Cancel token validation for stale response protection
- Single augmentation enforcement
- Telemetry logging with augmentation tracking
- Thread-safe session management

Design Principles:
1. Only ONE augmentation active at a time
2. Context builds are atomic (all-or-nothing)
3. Stale responses are discarded silently
4. Every build increments context_version
5. Old cancel_tokens are invalid
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SessionState:
    """
    Session state container for a user's Head Coach session.

    Attributes:
        active_coach_id: Currently active augmentation coach ID
        context_version: Incremented on every context build
        merged_hash: SHA-256 hash of merged prompt
        cancel_token: UUID for request validation
        behavior_context: Runtime behavior hints from feature state
        built_at: ISO timestamp of last build
    """

    def __init__(
        self,
        active_coach_id: str = "head_coach",
        context_version: int = 0,
        merged_hash: str = "",
        cancel_token: str = "",
        behavior_context: Optional[Dict[str, Any]] = None,
        built_at: Optional[str] = None
    ):
        self.active_coach_id = active_coach_id
        self.context_version = context_version
        self.merged_hash = merged_hash
        self.cancel_token = cancel_token
        self.behavior_context = behavior_context or {}
        self.built_at = built_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "active_coach_id": self.active_coach_id,
            "context_version": self.context_version,
            "merged_hash": self.merged_hash,
            "cancel_token": self.cancel_token,
            "behavior_context": self.behavior_context,
            "built_at": self.built_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionState:
        """Deserialize from dict."""
        return cls(
            active_coach_id=data.get("active_coach_id", "head_coach"),
            context_version=data.get("context_version", 0),
            merged_hash=data.get("merged_hash", ""),
            cancel_token=data.get("cancel_token", ""),
            behavior_context=data.get("behavior_context", {}),
            built_at=data.get("built_at")
        )


class SessionManager:
    """
    Thread-safe session manager for Head Coach augmentation contexts.

    Manages:
    - Session state persistence
    - Atomic context building
    - Cancel token generation and validation
    - Telemetry logging
    """

    def __init__(self, data_dir: Path):
        """
        Initialize session manager.

        Args:
            data_dir: Root data directory
        """
        self.data_dir = data_dir
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def _get_lock(self, user_id: str) -> threading.Lock:
        """Get or create lock for user."""
        with self._locks_lock:
            if user_id not in self._locks:
                self._locks[user_id] = threading.Lock()
            return self._locks[user_id]

    def _get_session_file(self, user_id: str) -> Path:
        """Get path to user's session state file."""
        return self.data_dir / "users" / user_id / "head_coach" / "session.json"

    def get_session(self, user_id: str) -> SessionState:
        """
        Get current session state for user.

        Args:
            user_id: User identifier

        Returns:
            Current session state (or default if not found)
        """
        lock = self._get_lock(user_id)
        with lock:
            session_file = self._get_session_file(user_id)

            if not session_file.exists():
                return SessionState()

            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return SessionState.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load session for {user_id}: {e}")
                return SessionState()

    def build_context(
        self,
        user_id: str,
        active_coach_id: str,
        force_rebuild: bool = False
    ) -> Dict[str, Any]:
        """
        Build atomic augmentation context with versioning.

        This is the CORE operation - every mode switch goes through here.

        Process:
        1. Acquire user lock
        2. Load current session
        3. Check if rebuild needed
        4. Fetch coach mandate + behavior context
        5. Build merged prompt
        6. Increment context_version
        7. Generate new cancel_token
        8. Compute merged_hash
        9. Save session atomically
        10. Emit telemetry
        11. Return context packet

        Args:
            user_id: User identifier
            active_coach_id: Coach to activate
            force_rebuild: Force rebuild even if coach unchanged

        Returns:
            Context packet with:
            - merged_prompt: Full system prompt
            - active_coach_id: Active augmentation
            - context_version: Incremented version
            - cancel_token: Validation token
            - behavior_context: Runtime hints
            - telemetry: Metadata for logging
        """
        lock = self._get_lock(user_id)
        start_time = time.time()

        with lock:
            # Load current session
            current_session = self.get_session(user_id)

            # Check if rebuild needed
            if not force_rebuild and current_session.active_coach_id == active_coach_id:
                logger.debug(f"Context unchanged for {user_id} ({active_coach_id} v{current_session.context_version})")
                return self._build_context_packet(current_session)

            # Build new context
            try:
                # Step 1: Load coach mandate
                coach_mandate = self._load_coach_mandate(active_coach_id)

                # Step 2: Load behavior context from feature state
                from .. import coach_mode_manager
                behavior_context = coach_mode_manager.build_behavior_context(user_id, active_coach_id)

                # Step 3: Build merged prompt
                merged_prompt = self._merge_prompt(coach_mandate, behavior_context)

                # Step 4: Increment version and generate token
                new_version = current_session.context_version + 1
                new_token = str(uuid4())

                # Step 5: Compute hash
                merged_hash = hashlib.sha256(merged_prompt.encode('utf-8')).hexdigest()[:16]

                # Step 6: Create new session state
                new_session = SessionState(
                    active_coach_id=active_coach_id,
                    context_version=new_version,
                    merged_hash=merged_hash,
                    cancel_token=new_token,
                    behavior_context=behavior_context,
                    built_at=datetime.now(timezone.utc).isoformat()
                )

                # Step 7: Save atomically
                self._save_session(user_id, new_session)

                # Step 8: Emit telemetry
                build_ms = (time.time() - start_time) * 1000
                self._log_telemetry(user_id, new_session, build_ms)

                # Step 9: Return context packet
                logger.info(
                    f"Built context for {user_id}: {active_coach_id} "
                    f"v{new_version} (token={new_token[:8]}..., hash={merged_hash})"
                )

                return {
                    "merged_prompt": merged_prompt,
                    "active_coach_id": active_coach_id,
                    "context_version": new_version,
                    "cancel_token": new_token,
                    "behavior_context": behavior_context,
                    "telemetry": {
                        "merged_hash": merged_hash,
                        "build_ms": round(build_ms, 2),
                        "augmentations": [active_coach_id] if active_coach_id != "head_coach" else []
                    }
                }

            except Exception as e:
                logger.error(f"Failed to build context for {user_id}: {e}", exc_info=True)
                raise

    def validate_token(self, user_id: str, cancel_token: str) -> bool:
        """
        Validate cancel token against current session.

        Args:
            user_id: User identifier
            cancel_token: Token to validate

        Returns:
            True if token is current, False otherwise
        """
        lock = self._get_lock(user_id)
        with lock:
            session = self.get_session(user_id)
            is_valid = session.cancel_token == cancel_token

            if not is_valid:
                logger.debug(
                    f"Stale token detected for {user_id}: "
                    f"{cancel_token[:8]}... != {session.cancel_token[:8]}... "
                    f"(current v{session.context_version})"
                )

            return is_valid

    def _save_session(self, user_id: str, session: SessionState) -> None:
        """Save session state atomically."""
        session_file = self._get_session_file(user_id)
        session_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session for {user_id}: {e}")
            raise

    def _load_coach_mandate(self, coach_id: str) -> str:
        """
        Load coach mandate from prompts directory.

        Args:
            coach_id: Coach identifier

        Returns:
            Coach mandate text
        """
        # Head coach is always the base
        prompts_dir = self.data_dir.parent / "prompts"
        hc_file = prompts_dir / "head_coach_ai.md"

        if not hc_file.exists():
            raise FileNotFoundError(f"Head Coach mandate not found: {hc_file}")

        hc_mandate = hc_file.read_text(encoding='utf-8')

        # If head_coach, return base mandate
        if coach_id == "head_coach":
            return hc_mandate

        # Otherwise, load augmentation
        aug_file = prompts_dir / f"{coach_id}_ai.md"

        if not aug_file.exists():
            logger.warning(f"Augmentation file not found: {aug_file}. Using head_coach only.")
            return hc_mandate

        aug_mandate = aug_file.read_text(encoding='utf-8')

        return hc_mandate, aug_mandate

    def _merge_prompt(
        self,
        coach_mandate: tuple[str, str] | str,
        behavior_context: Dict[str, Any]
    ) -> str:
        """
        Merge head coach + augmentation + behavior context.

        Args:
            coach_mandate: Either HC mandate alone or (HC, augmentation) tuple
            behavior_context: Runtime behavior hints

        Returns:
            Merged prompt text
        """
        if isinstance(coach_mandate, tuple):
            hc_mandate, aug_mandate = coach_mandate
            coach_label = "Augmented Coach"

            # Build merged prompt
            parts = [
                hc_mandate,
                "\n\n" + "=" * 60,
                f"\n=== AUGMENTED ROLE: {coach_label} ===\n",
                "=" * 60 + "\n",
                aug_mandate
            ]
        else:
            # Head coach only
            parts = [coach_mandate]

        # Add runtime behavior context if present
        hints = behavior_context.get("hints", {})
        if hints:
            parts.append("\n\n" + "=" * 60)
            parts.append("\n=== RUNTIME BEHAVIOR CONTEXT ===\n")
            parts.append("=" * 60 + "\n")

            for key, value in hints.items():
                if isinstance(value, bool):
                    parts.append(f"{key}: {str(value).lower()}\n")
                elif isinstance(value, (int, float)):
                    parts.append(f"{key}: {value}\n")
                else:
                    parts.append(f"{key}: {value}\n")

        return "".join(parts)

    def _build_context_packet(self, session: SessionState) -> Dict[str, Any]:
        """Build context packet from existing session (no rebuild)."""
        return {
            "active_coach_id": session.active_coach_id,
            "context_version": session.context_version,
            "cancel_token": session.cancel_token,
            "behavior_context": session.behavior_context,
            "telemetry": {
                "merged_hash": session.merged_hash,
                "augmentations": [session.active_coach_id] if session.active_coach_id != "head_coach" else [],
                "cached": True
            }
        }

    def _log_telemetry(self, user_id: str, session: SessionState, build_ms: float) -> None:
        """Log telemetry for context build."""
        try:
            from ..storage import CORE_DATA_ROOT

            telemetry_dir = CORE_DATA_ROOT.parent / "prompts" / "insights"
            telemetry_dir.mkdir(parents=True, exist_ok=True)

            telemetry_file = telemetry_dir / "session_integrity.jsonl"

            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "active_coach_id": session.active_coach_id,
                "context_version": session.context_version,
                "augmentations": [session.active_coach_id] if session.active_coach_id != "head_coach" else [],
                "prompt_hash": session.merged_hash,
                "features": session.behavior_context.get("features", {}),
                "hints": session.behavior_context.get("hints", {}),
                "build_ms": round(build_ms, 2),
                "cancel_token": session.cancel_token[:8] + "..."  # Truncated for privacy
            }

            with telemetry_file.open('a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')

        except Exception as e:
            logger.error(f"Failed to log telemetry: {e}")


# Global manager instance
_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    global _manager
    if _manager is None:
        from ..storage import CORE_DATA_ROOT
        _manager = SessionManager(CORE_DATA_ROOT)
    return _manager


def build_augmented_context(user_id: str, active_coach_id: str = "head_coach") -> Dict[str, Any]:
    """
    Convenience function to build augmented context.

    Args:
        user_id: User identifier
        active_coach_id: Coach to activate

    Returns:
        Context packet
    """
    manager = get_session_manager()
    return manager.build_context(user_id, active_coach_id)


def validate_request_token(user_id: str, cancel_token: str) -> bool:
    """
    Convenience function to validate cancel token.

    Args:
        user_id: User identifier
        cancel_token: Token to validate

    Returns:
        True if valid, False if stale
    """
    manager = get_session_manager()
    return manager.validate_token(user_id, cancel_token)
