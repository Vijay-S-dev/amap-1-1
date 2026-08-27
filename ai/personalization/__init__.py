"""
AMAP Evidence-Based Adaptation & Personalization Engine.
"""

from ai.personalization.analyzer import (
    DifficultyPatternAnalyzer,
    InteractionEventRecord,
)
from ai.personalization.recommender import AdaptationEngine

__all__ = [
    "AdaptationEngine",
    "DifficultyPatternAnalyzer",
    "InteractionEventRecord",
]
