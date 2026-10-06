"""Walker: slow, common enemy that applies basic pressure in groups."""
from __future__ import annotations

from src.enemies.enemy import Enemy


class Walker(Enemy):
    """Uses the base AI unchanged. Its identity comes from its data in enemies.json."""