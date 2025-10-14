"""
Consent Service - Storage Layer

Manages capability and ledger persistence using JSON files.
For production, this could be upgraded to a database.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from .models import CapabilityToken, LedgerEvent, LedgerEventType

logger = logging.getLogger(__name__)

# Storage root (overridable for tests via CONSENT_DATA_DIR)
DEFAULT_CONSENT_ROOT = Path(__file__).parent.parent.parent.parent / "data" / "consent"
CONSENT_ROOT = Path(os.getenv("CONSENT_DATA_DIR", str(DEFAULT_CONSENT_ROOT)))
CAPABILITIES_FILE = CONSENT_ROOT / "capabilities.json"
LEDGER_FILE = CONSENT_ROOT / "ledger.jsonl"  # Append-only log


class ConsentStorage:
    """Storage layer for consent service."""

    def __init__(self):
        """Initialize storage, creating directories if needed."""
        CONSENT_ROOT.mkdir(parents=True, exist_ok=True)

        # Initialize capabilities file if it doesn't exist
        if not CAPABILITIES_FILE.exists():
            with open(CAPABILITIES_FILE, "w") as f:
                json.dump({"capabilities": []}, f, indent=2)
            logger.info(f"Initialized capabilities file: {CAPABILITIES_FILE}")

        # Initialize ledger file if it doesn't exist
        if not LEDGER_FILE.exists():
            LEDGER_FILE.touch()
            logger.info(f"Initialized ledger file: {LEDGER_FILE}")

    def save_capability(self, capability: CapabilityToken) -> None:
        """
        Save a capability to storage.

        Args:
            capability: Capability token to save
        """
        try:
            # Load existing capabilities
            with open(CAPABILITIES_FILE, "r") as f:
                data = json.load(f)

            capabilities = data.get("capabilities", [])

            # Check if capability already exists (update)
            existing_idx = None
            for idx, cap in enumerate(capabilities):
                if cap.get("cap_id") == capability.cap_id:
                    existing_idx = idx
                    break

            cap_dict = capability.model_dump()

            if existing_idx is not None:
                # Update existing
                capabilities[existing_idx] = cap_dict
                logger.debug(f"Updated capability: cap_id={capability.cap_id}")
            else:
                # Add new
                capabilities.append(cap_dict)
                logger.info(f"Saved new capability: cap_id={capability.cap_id}, grantee={capability.grantee_id}")

            # Save back to file
            data["capabilities"] = capabilities
            with open(CAPABILITIES_FILE, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save capability {capability.cap_id}: {e}")
            raise

    def get_capability(self, cap_id: str) -> Optional[CapabilityToken]:
        """
        Retrieve a capability by ID.

        Args:
            cap_id: Capability ID

        Returns:
            CapabilityToken if found, None otherwise
        """
        try:
            with open(CAPABILITIES_FILE, "r") as f:
                data = json.load(f)

            capabilities = data.get("capabilities", [])

            for cap_dict in capabilities:
                if cap_dict.get("cap_id") == cap_id:
                    return CapabilityToken(**cap_dict)

            logger.debug(f"Capability not found: cap_id={cap_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to get capability {cap_id}: {e}")
            raise

    def list_capabilities(self, user_id: Optional[str] = None, grantee_id: Optional[str] = None) -> List[CapabilityToken]:
        """
        List capabilities, optionally filtered by user or grantee.

        Args:
            user_id: Optional user ID filter
            grantee_id: Optional grantee ID filter

        Returns:
            List of CapabilityTokens
        """
        try:
            with open(CAPABILITIES_FILE, "r") as f:
                data = json.load(f)

            capabilities = data.get("capabilities", [])

            # Apply filters
            filtered = []
            for cap_dict in capabilities:
                if user_id and cap_dict.get("user_id") != user_id:
                    continue
                if grantee_id and cap_dict.get("grantee_id") != grantee_id:
                    continue
                filtered.append(CapabilityToken(**cap_dict))

            logger.debug(f"Listed {len(filtered)} capabilities (user={user_id}, grantee={grantee_id})")
            return filtered

        except Exception as e:
            logger.error(f"Failed to list capabilities: {e}")
            raise

    def append_ledger_event(self, event: LedgerEvent) -> None:
        """
        Append an event to the ledger (append-only log).

        Args:
            event: Ledger event to append
        """
        try:
            # Append to JSONL file (one event per line)
            with open(LEDGER_FILE, "a") as f:
                event_json = event.model_dump_json()
                f.write(event_json + "\n")

            logger.info(f"Appended ledger event: {event.event_type}, cap_id={event.cap_id}")

        except Exception as e:
            logger.error(f"Failed to append ledger event: {e}")
            raise

    def read_ledger(self, user_id: Optional[str] = None, cap_id: Optional[str] = None, event_type: Optional[LedgerEventType] = None) -> List[LedgerEvent]:
        """
        Read ledger events, optionally filtered.

        Args:
            user_id: Optional user ID filter
            cap_id: Optional capability ID filter
            event_type: Optional event type filter

        Returns:
            List of LedgerEvents
        """
        try:
            events = []

            with open(LEDGER_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    event_dict = json.loads(line)

                    # Apply filters
                    if user_id and event_dict.get("user_id") != user_id:
                        continue
                    if cap_id and event_dict.get("cap_id") != cap_id:
                        continue
                    if event_type and event_dict.get("event_type") != event_type:
                        continue

                    events.append(LedgerEvent(**event_dict))

            logger.debug(f"Read {len(events)} ledger events (user={user_id}, cap_id={cap_id}, type={event_type})")
            return events

        except Exception as e:
            logger.error(f"Failed to read ledger: {e}")
            raise

    def create_ledger_event(
        self,
        event_type: LedgerEventType,
        user_id: str,
        cap_id: Optional[str] = None,
        grantee_id: Optional[str] = None,
        purpose: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        ttl: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LedgerEvent:
        """
        Create and append a ledger event in one step.

        Args:
            event_type: Type of event
            user_id: User ID
            cap_id: Optional capability ID
            grantee_id: Optional grantee ID
            purpose: Optional purpose
            scopes: Optional scopes
            ttl: Optional TTL
            reason: Optional reason (for deny/revoke)
            metadata: Optional additional metadata

        Returns:
            Created LedgerEvent
        """
        event = LedgerEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type,
            user_id=user_id,
            cap_id=cap_id,
            grantee_id=grantee_id,
            purpose=purpose,
            scopes=scopes,
            ttl=ttl,
            reason=reason,
            metadata=metadata,
        )

        self.append_ledger_event(event)
        return event
