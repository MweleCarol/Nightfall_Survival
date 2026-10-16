"""Armor: how much of a hit is absorbed. Pure maths."""
from __future__ import annotations

from src.core import settings


def damage_reduction(armor: float) -> float:
    """Fraction of incoming damage absorbed. Diminishing returns: it never reaches the cap."""
    if armor <= 0:
        return 0.0
    return settings.ARMOR_MAX_REDUCTION * armor / (armor + settings.ARMOR_HALF_POINT)