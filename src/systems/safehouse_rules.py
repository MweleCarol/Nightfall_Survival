"""Rules that stop the safehouse from being a free pass. Pure logic, no Pygame."""
from __future__ import annotations

from src.core import settings


class SafeZoneRules:
    """Rule A: the safe zone only protects you while you are not shooting out of it."""

    def __init__(self, break_duration: float = settings.TRUCE_BREAK_TIME) -> None:
        self.break_duration = break_duration
        self.break_remaining = 0.0

    @property
    def truce_broken(self) -> bool:
        return self.break_remaining > 0

    def update(self, dt: float) -> None:
        self.break_remaining = max(0.0, self.break_remaining - dt)

    def on_shot_fired(self, in_safe_zone: bool) -> bool:
        """Call whenever the player fires. Returns True if this shot newly broke the truce."""
        if not in_safe_zone:
            return False
        newly_broken = not self.truce_broken
        self.break_remaining = self.break_duration       # every shot restarts the timer
        return newly_broken

    def protects(self, in_safe_zone: bool) -> bool:
        """Enemies leave you alone only while you are inside the zone with the truce intact."""
        return in_safe_zone and not self.truce_broken

    def reset(self) -> None:
        self.break_remaining = 0.0


class NightResult:
    """Rule B: a night only counts as survived if every one of its waves was cleared."""

    def __init__(self) -> None:
        self.cleared = False

    def start_night(self) -> None:
        self.cleared = False

    def mark_cleared(self) -> None:
        self.cleared = True

    @property
    def counts_as_survived(self) -> bool:
        return self.cleared