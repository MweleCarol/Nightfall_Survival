"""Screen shake driven by 'trauma' (0 to 1): the bigger the trauma, the stronger the shake."""
from __future__ import annotations

import math
import random

from pygame import Vector2


class ScreenShake:
    def __init__(self, max_offset: float = 14.0, decay: float = 1.6,
                 rng: random.Random | None = None) -> None:
        self.max_offset = max_offset            # pixels at full trauma
        self.decay = decay                      # trauma lost per second
        self.trauma = 0.0
        self._time = 0.0
        rng = rng or random.Random()
        self._phase = [rng.uniform(0.0, 6.28) for _ in range(2)]

    def add_trauma(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + max(0.0, amount))

    def update(self, dt: float) -> None:
        self.trauma = max(0.0, self.trauma - self.decay * dt)
        self._time += dt

    @property
    def offset(self) -> Vector2:
        """How far to move the picture this frame."""
        if self.trauma <= 0.0:
            return Vector2(0, 0)
        magnitude = self.max_offset * self.trauma ** 2        # squared: small hits barely register
        return Vector2(magnitude * math.sin(self._time * 47.0 + self._phase[0]),
                       magnitude * math.sin(self._time * 53.0 + self._phase[1]))