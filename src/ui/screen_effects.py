"""Full-screen feedback: the damage flash, low-health pulse and the vignette."""
from __future__ import annotations

import math

import pygame


class HurtFlash:
    """A value that jumps to 1 when the player is hurt and fades quickly."""

    def __init__(self, fade_time: float = 0.45) -> None:
        self.fade_time = fade_time
        self.intensity = 0.0

    def trigger(self, amount: float = 1.0) -> None:
        self.intensity = max(self.intensity, min(1.0, amount))

    def update(self, dt: float) -> None:
        self.intensity = max(0.0, self.intensity - dt / self.fade_time)


def low_health_intensity(fraction: float, time_seconds: float, threshold: float = 0.3) -> float:
    """0 when healthy; a pulsing 0-1 warning below the threshold, faster and stronger as health drops."""
    fraction = max(0.0, min(1.0, fraction))
    if fraction >= threshold or fraction <= 0.0:
        return 0.0
    severity = 1.0 - fraction / threshold
    pulse = 0.5 + 0.5 * math.sin(time_seconds * (3.0 + 4.0 * severity))
    return severity * (0.4 + 0.6 * pulse)


class Vignette:
    """Darkened screen edges (always a little, more at night) and red edges when hurt."""

    def __init__(self, width: int, height: int) -> None:
        self.dark = self._build(width, height, (0, 0, 0), 170)
        self.red = self._build(width, height, (150, 0, 0), 255)

    @staticmethod
    def _build(width: int, height: int, color: tuple[int, int, int], max_alpha: int) -> pygame.Surface:
        """Compute a tiny gradient, then scale it up: smooth and cheap."""
        small_w, small_h = 64, 36
        small = pygame.Surface((small_w, small_h), pygame.SRCALPHA)
        for y in range(small_h):
            for x in range(small_w):
                dx = (x + 0.5) / small_w * 2 - 1
                dy = (y + 0.5) / small_h * 2 - 1
                distance = min(1.0, math.hypot(dx, dy) / math.sqrt(2))     # 1.0 in the corners
                strength = max(0.0, (distance - 0.45) / 0.55) ** 2
                small.set_at((x, y), (*color, int(max_alpha * strength)))
        return pygame.transform.smoothscale(small, (width, height))

    def draw(self, surface: pygame.Surface, darkness: float, hurt: float, low_health: float) -> None:
        self.dark.set_alpha(int(255 * (0.35 + 0.65 * max(0.0, min(1.0, darkness)))))
        surface.blit(self.dark, (0, 0))
        red = max(hurt, low_health)
        if red > 0.01:
            self.red.set_alpha(int(255 * min(1.0, red)))
            surface.blit(self.red, (0, 0))