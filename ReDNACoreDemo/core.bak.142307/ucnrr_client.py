"""
UCNRR Client
============

Client for UCN/RR (User Confidence Number / Rarity Rating) scoring service.

Provides both mock and real implementations for rescoring user traits.

Mock Mode (default):
- Returns synthetic UCN/RR scores for testing
- No external dependencies

Real Mode (enable_ucnrr=true):
- Calls actual UCNRR service endpoint
- Requires UCNRR service to be running

Environment Variables:
- UCNRR_SERVICE_URL: URL of UCNRR service (default: http://localhost:8002)
- UCNRR_TIMEOUT_SEC: Request timeout in seconds (default: 10)
"""

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class UCNRRClient:
    """
    Client for UCNRR scoring service.

    Supports both mock and real implementations.
    """

    def __init__(
        self,
        service_url: Optional[str] = None,
        timeout_sec: int = 10,
        mock_mode: bool = True
    ):
        """
        Initialize UCNRR client.

        Args:
            service_url: URL of UCNRR service
            timeout_sec: Request timeout in seconds
            mock_mode: If True, use mock responses; if False, call real service
        """
        self.service_url = service_url or os.getenv(
            "UCNRR_SERVICE_URL",
            "http://localhost:8002"
        )
        self.timeout_sec = int(os.getenv("UCNRR_TIMEOUT_SEC", str(timeout_sec)))
        self.mock_mode = mock_mode

    def rescore_user(self, user_id: str) -> Dict[str, Any]:
        """
        Rescore all traits for a user.

        Args:
            user_id: User identifier

        Returns:
            {
                "user_id": "alice",
                "rr_by_trait": {
                    "PaDNA.EyeDNA.Iris.BaseColor": 150.0,
                    "PaDNA.SkinDNA.Freckles.Density": 400.0,
                    ...
                },
                "ucn_by_trait": {
                    "PaDNA.EyeDNA.Iris.BaseColor": 750.0,
                    "PaDNA.SkinDNA.Freckles.Density": 600.0,
                    ...
                }
            }

        Raises:
            UCNRRError: If service call fails
        """
        if self.mock_mode:
            return self._mock_rescore(user_id)
        else:
            return self._real_rescore(user_id)

    def _mock_rescore(self, user_id: str) -> Dict[str, Any]:
        """
        Generate mock UCN/RR scores.

        Returns synthetic scores for common traits.

        Args:
            user_id: User identifier

        Returns:
            Mock scoring response
        """
        logger.info(f"UCNRR mock rescore for {user_id}")

        # Synthetic scores for common traits
        mock_scores = {
            "user_id": user_id,
            "rr_by_trait": {
                "PaDNA.EyeDNA.Iris.BaseColor": 150.0,
                "PaDNA.EyeDNA.Iris.Flecks": 300.0,
                "PaDNA.EyeDNA.Iris.Pattern": 450.0,
                "PaDNA.SkinDNA.Freckles.Density": 400.0,
                "PaDNA.SkinDNA.Freckles.Distribution": 350.0,
                "PaDNA.SkinDNA.Texture": 250.0,
                "PaDNA.HairDNA.Color": 200.0,
                "PaDNA.HairDNA.Texture": 300.0,
            },
            "ucn_by_trait": {
                "PaDNA.EyeDNA.Iris.BaseColor": 750.0,
                "PaDNA.EyeDNA.Iris.Flecks": 600.0,
                "PaDNA.EyeDNA.Iris.Pattern": 550.0,
                "PaDNA.SkinDNA.Freckles.Density": 600.0,
                "PaDNA.SkinDNA.Freckles.Distribution": 650.0,
                "PaDNA.SkinDNA.Texture": 700.0,
                "PaDNA.HairDNA.Color": 800.0,
                "PaDNA.HairDNA.Texture": 650.0,
            }
        }

        return mock_scores

    def _real_rescore(self, user_id: str) -> Dict[str, Any]:
        """
        Call real UCNRR service for rescoring.

        Args:
            user_id: User identifier

        Returns:
            UCNRR service response

        Raises:
            UCNRRError: If service call fails
        """
        import requests

        url = f"{self.service_url}/rescore/{user_id}"

        try:
            logger.info(f"UCNRR real rescore for {user_id}: {url}")

            response = requests.post(
                url,
                timeout=self.timeout_sec
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"UCNRR rescore successful for {user_id}")
            return data

        except requests.exceptions.Timeout:
            raise UCNRRError(f"UCNRR service timeout after {self.timeout_sec}s")

        except requests.exceptions.ConnectionError:
            raise UCNRRError(f"Cannot connect to UCNRR service at {self.service_url}")

        except requests.exceptions.HTTPError as e:
            raise UCNRRError(f"UCNRR service error: {e}")

        except Exception as e:
            raise UCNRRError(f"Unexpected UCNRR error: {e}")

    def apply_scores_to_traits(
        self,
        traits: Dict[str, Any],
        scores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply UCN/RR scores to traits dictionary.

        Mutates the traits dict in place, adding ucn and rr fields.

        Args:
            traits: Traits dictionary (from resolved state)
            scores: UCNRR scores response

        Returns:
            Updated traits dictionary
        """
        rr_by_trait = scores.get("rr_by_trait", {})
        ucn_by_trait = scores.get("ucn_by_trait", {})

        for trait_path, rr in rr_by_trait.items():
            if trait_path in traits and isinstance(traits[trait_path], dict):
                traits[trait_path]["rr"] = rr

        for trait_path, ucn in ucn_by_trait.items():
            if trait_path in traits and isinstance(traits[trait_path], dict):
                traits[trait_path]["ucn"] = ucn

        return traits


class UCNRRError(Exception):
    """UCNRR service error."""
    pass


# Singleton instance
_ucnrr_client = None

def get_ucnrr_client(mock_mode: bool = True) -> UCNRRClient:
    """
    Get singleton UCNRR client instance.

    Args:
        mock_mode: If True, use mock responses; if False, call real service

    Returns:
        UCNRRClient instance
    """
    global _ucnrr_client
    if _ucnrr_client is None:
        _ucnrr_client = UCNRRClient(mock_mode=mock_mode)
    return _ucnrr_client


def rescore_user_safe(user_id: str, mock_mode: bool = True) -> Optional[Dict[str, Any]]:
    """
    Safely rescore a user, returning None on failure.

    This is a non-blocking wrapper that logs errors but doesn't raise.

    Args:
        user_id: User identifier
        mock_mode: If True, use mock responses

    Returns:
        UCNRR scores or None if failed
    """
    try:
        client = get_ucnrr_client(mock_mode=mock_mode)
        return client.rescore_user(user_id)
    except Exception as e:
        logger.warning(f"UCNRR rescore failed for {user_id}: {e}")
        return None
