"""Health and stamina rules. Pure logic, no Pygame, easy to test."""
from __future__ import annotations

from src.core import settings


class Stats:
    def __init__(
        self,
        max_health: int = settings.PLAYER_MAX_HEALTH,
        max_stamina: float = settings.PLAYER_MAX_STAMINA,
        health: int | None = None,
        stamina: float | None = None,
        drain_rate: float = settings.STAMINA_DRAIN_PER_SEC,
        regen_rate: float = settings.STAMINA_REGEN_PER_SEC,
        regen_delay: float = settings.STAMINA_REGEN_DELAY,
    ) -> None:
        self.max_health = max_health
        self.max_stamina = max_stamina
        self.health = max_health if health is None else health
        self.stamina = max_stamina if stamina is None else stamina
        self.drain_rate = drain_rate
        self.regen_rate = regen_rate
        self.regen_delay = regen_delay
        self._regen_cooldown = 0.0

    @property
    def is_dead(self) -> bool:
        return self.health <= 0

    def take_damage(self, amount: int) -> int:
        """Reduce health. Returns the damage actually dealt."""
        if amount <= 0 or self.is_dead:
            return 0
        dealt = min(amount, self.health)
        self.health -= dealt
        return dealt

    def heal(self, amount: int) -> int:
        """Restore health up to the maximum. Returns the amount healed."""
        if amount <= 0 or self.is_dead:
            return 0
        healed = min(amount, self.max_health - self.health)
        self.health += healed
        return healed

    def update_stamina(self, dt: float, sprinting: bool) -> None:
        if sprinting:
            self.stamina = max(0.0, self.stamina - self.drain_rate * dt)
            self._regen_cooldown = self.regen_delay
        elif self._regen_cooldown > 0:
            self._regen_cooldown -= dt
        else:
            self.stamina = min(self.max_stamina, self.stamina + self.regen_rate * dt)