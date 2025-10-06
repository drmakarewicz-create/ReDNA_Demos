"""
UCN/RR Calculation Engine

This module provides the intelligence layer for assessing confidence in trait assignments
and driving the system's curiosity to refine user profiles.

Key Components:
- UCNCalculator: Calculates User Confidence Numbers (0-1000) for traits
- RRCalculator: Calculates Refinement Rank (0-100 percentile) vs population
- CuriosityEngine: Derives Curiosity = 100 - RR
- EvidenceWeighting: Weighs evidence sources by credibility, recency, corroboration
- DecayEngine: Manages adaptive decay rates for confidence over time
- ContradictionHandler: Detects and manages contradictory evidence
- ProvenanceLogger: Tracks all evidence attempts (successes and failures)
"""

from .ucn_calculator import UCNCalculator, calculate_ucn
from .rr_calculator import RRCalculator, calculate_rr
from .curiosity import CuriosityEngine, calculate_curiosity
from .evidence_weighting import EvidenceWeighting, EvidenceSource, SourceType
from .decay_engine import DecayEngine
from .contradiction_handler import ContradictionHandler, ContradictionSeverity
from .provenance import ProvenanceLogger, update_evidence, AttemptType, AttemptStatus

__all__ = [
    'UCNCalculator',
    'calculate_ucn',
    'RRCalculator',
    'calculate_rr',
    'CuriosityEngine',
    'calculate_curiosity',
    'EvidenceWeighting',
    'EvidenceSource',
    'SourceType',
    'DecayEngine',
    'ContradictionHandler',
    'ContradictionSeverity',
    'ProvenanceLogger',
    'update_evidence',
    'AttemptType',
    'AttemptStatus',
]

__version__ = '0.1.0'
