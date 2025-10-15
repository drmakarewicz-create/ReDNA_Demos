# ReDNACoreDemo/core/ingest/__init__.py
"""
Unified evidence ingestion pipeline.
Single source of truth for evidence schema, validation, and processing.
"""

from .evidence_schema import validate_batch, normalize_value
from .pipeline import ingest_evidence_roundtrip

__all__ = ["validate_batch", "normalize_value", "ingest_evidence_roundtrip"]
