"""Day/night cycle. Pure logic (no Pygame), so it is easy to test."""
from __future__ import annotations

from enum import Enum

from src.core import settings
from src.core.event_bus import EventBus


class Phase(Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"


def _smoothstep(t: float) -> float:
    """Ease 0->1 with soft start and end (avoids a visible 'snap')."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


class DayNightCycle:
    def __init__(
        self,
        day_duration: float = settings.DAY_DURATION,
        night_duration: float = settings.NIGHT_DURATION,
        event_bus: EventBus | None = None,
        phase: Phase = Phase.DAY,
        day_number: int = 1,
    ) -> None:
        if day_duration <= 0 or night_duration <= 0:
            raise ValueError("Phase durations must be positive")
        self.day_duration = day_duration
        self.night_duration = night_duration
        self.event_bus = event_bus
        self.phase = phase
        self.day_number = day_number   # Night N follows Day N
        self.elapsed = 0.0

    # ---- state queries ----
    @property
    def is_day(self) -> bool:
        return self.phase is Phase.DAY

    @property
    def is_night(self) -> bool:
        return self.phase is Phase.NIGHT

    @property
    def phase_duration(self) -> float:
        return self.day_duration if self.is_day else self.night_duration

    @property
    def progress(self) -> float:
        """0.0 at the start of the current phase, 1.0 at its end."""
        return self.elapsed / self.phase_duration

    @property
    def label(self) -> str:
        return f"{self.phase.value} {self.day_number}"

    @property
    def darkness(self) -> float:
        """0.0 = bright daylight, 1.0 = full night. Ramps at dusk and dawn."""
        p = self.progress
        if self.is_day:
            span = 1.0 - settings.DUSK_START
            return _smoothstep((p - settings.DUSK_START) / span)
        if p < settings.DAWN_START:
            return 1.0
        span = 1.0 - settings.DAWN_START
        return 1.0 - _smoothstep((p - settings.DAWN_START) / span)

    @property
    def clock_hour(self) -> float:
        """In-game hour (0-24). Day: 08:00->20:00, night: 20:00->08:00."""
        if self.is_day:
            return settings.DAY_START_HOUR + 12.0 * self.progress
        return (settings.NIGHT_START_HOUR + 12.0 * self.progress) % 24.0

    def clock_text(self) -> str:
        hour = self.clock_hour
        return f"{int(hour):02d}:{int((hour % 1) * 60):02d}"

    # ---- updates ----
    def update(self, dt: float) -> None:
        self.elapsed += dt
        while self.elapsed >= self.phase_duration:   # handles very large dt
            self.elapsed -= self.phase_duration
            self._advance_phase()

    def skip_to_next_phase(self) -> None:
        """Jump straight to the next phase (rest at safehouse / debug)."""
        self.elapsed = 0.0
        self._advance_phase()

    def _advance_phase(self) -> None:
        if self.is_day:
            self.phase = Phase.NIGHT
            self._emit("NIGHT_STARTED", {"night": self.day_number})
        else:
            self._emit("NIGHT_COMPLETED", {"night": self.day_number})
            self.day_number += 1
            self.phase = Phase.DAY
            self._emit("DAY_STARTED", {"day": self.day_number})

    def _emit(self, event: str, data: dict) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)