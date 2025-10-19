"""
Curiosity Engine v2
===================

Adaptive curiosity and motivation engine that prioritizes which containers/traits
to explore next based on Self-Improvement analytics and data coverage.
"""

from .curiosity_engine_v2 import CuriosityEngine, generate_agenda

__all__ = ["CuriosityEngine", "generate_agenda"]
