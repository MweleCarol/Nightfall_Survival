"""Stalker: fast but fragile. Forces the player to keep moving."""
from __future__ import annotations

from src.enemies.enemy import Enemy


class Stalker(Enemy):
    """Uses the base AI. Its speed and low health in enemies.json define it."""