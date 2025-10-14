"""
Vault module - Refinement plane I/O operations.

IMPORTANT: This module handles REFINEMENT operations (vault-internal).
For USE operations (external read/write/export), see core/use_api.
"""

from .vault_client import VaultClient, get_vault_client

__all__ = ["VaultClient", "get_vault_client"]
