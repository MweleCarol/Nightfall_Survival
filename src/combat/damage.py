"""Damage calculation (LLD section 8). Armor and crits are ready for later."""
from __future__ import annotations


def calculate_damage(
    base_damage: float,
    armor: float = 0.0,
    critical: bool = False,
    critical_multiplier: float = 2.0,
) -> int:
    damage = max(0.0, base_damage - armor)
    if critical:
        damage *= critical_multiplier
    return round(damage)