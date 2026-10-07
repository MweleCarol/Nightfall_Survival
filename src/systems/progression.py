"""XP, levels and skill points (LLD section 14). Pure logic: no Pygame, no UI."""
from __future__ import annotations

from typing import Any

from src.core import settings
from src.core.event_bus import EventBus


class Progression:
    def __init__(self, level: int = 1, xp: int = 0, skill_points: int = 0,
                 event_bus: EventBus | None = None,
                 base_xp: int = settings.XP_BASE,
                 growth: float = settings.XP_GROWTH,
                 max_level: int = settings.MAX_LEVEL) -> None:
        if level < 1 or base_xp <= 0 or growth < 1.0 or max_level < 1:
            raise ValueError("Invalid progression settings")
        self.base_xp = base_xp
        self.growth = growth
        self.max_level = max_level
        self.event_bus = event_bus
        self.level = min(level, max_level)
        self.xp = max(0, xp)
        self.skill_points = max(0, skill_points)

    # ---- queries ----
    def xp_required(self, level: int | None = None) -> int:
        """XP needed to go from `level` to the next one."""
        current = self.level if level is None else level
        return max(1, round(self.base_xp * self.growth ** (current - 1)))

    @property
    def is_max_level(self) -> bool:
        return self.level >= self.max_level

    @property
    def progress(self) -> float:
        """0.0 -> 1.0 through the current level (for the XP bar)."""
        if self.is_max_level:
            return 1.0
        return min(1.0, self.xp / self.xp_required())

    # ---- changes ----
    def add_xp(self, amount: int) -> int:
        """Add XP. Returns how many levels were gained (can be several at once)."""
        if amount <= 0 or self.is_max_level:
            return 0
        self.xp += amount
        self._emit("XP_GAINED", {"amount": amount})
        gained = 0
        while not self.is_max_level and self.xp >= self.xp_required():
            self.xp -= self.xp_required()
            self.level += 1
            self.skill_points += 1
            gained += 1
            self._emit("LEVEL_UP", {"level": self.level, "skill_points": self.skill_points})
        if self.is_max_level:
            self.xp = 0                       # nothing left to earn
        return gained

    def spend_skill_point(self) -> bool:
        if self.skill_points <= 0:
            return False
        self.skill_points -= 1
        return True

    # ---- persistence (used by the save system in Milestone 10) ----
    def serialize(self) -> dict[str, int]:
        return {"level": self.level, "xp": self.xp, "skill_points": self.skill_points}

    @classmethod
    def deserialize(cls, data: dict[str, Any], **kwargs: Any) -> Progression:
        def whole(key: str, default: int, minimum: int) -> int:
            value = data.get(key, default)
            valid = isinstance(value, int) and not isinstance(value, bool) and value >= minimum
            return value if valid else default
        return cls(level=whole("level", 1, 1), xp=whole("xp", 0, 0),
                   skill_points=whole("skill_points", 0, 0), **kwargs)

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)