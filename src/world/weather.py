"""Night weather: rain and fog that grow with the darkness, plus lightning in heavy rain."""
from __future__ import annotations

import random

import pygame

from src.ui.effects import FogLayer, LightningFlash, RainField


def rain_fraction(darkness: float) -> float:
    """0 in daylight, rising as dusk deepens, 1 at full night."""
    return max(0.0, min(1.0, (darkness - 0.15) / 0.55))


class WeatherSystem:
    def __init__(self, width: int, height: int, rng: random.Random | None = None) -> None:
        rng = rng or random.Random()
        self.rain = RainField(width, height, count=320, rng=rng, wind=-130.0)
        self.fog = FogLayer(width, height, speed=10.0, alpha=30, band=(0.55, 1.0), seed=21)
        self.lightning = LightningFlash(width, height, rng=rng, min_gap=9.0, max_gap=22.0)
        self.intensity = 0.0

    def update(self, dt: float, darkness: float) -> None:
        self.intensity = rain_fraction(darkness)
        if self.intensity > 0.0:
            self.rain.update(dt)
            self.fog.update(dt)
        if self.intensity > 0.6:                      # lightning only in heavy rain
            self.lightning.update(dt)
        else:
            self.lightning.flash = max(0.0, self.lightning.flash - dt * 3.0)   # finish any flash

    def draw_fog(self, surface: pygame.Surface) -> None:
        if self.intensity > 0.05:
            self.fog.surface.set_alpha(int(255 * self.intensity))
            self.fog.draw(surface)

    def draw_rain(self, surface: pygame.Surface) -> None:
        count = int(len(self.rain.drops) * self.intensity)         # fewer drops in light rain
        wind = self.rain.wind
        for x, y, speed, length in self.rain.drops[:count]:
            slant = wind / speed * length
            pygame.draw.line(surface, (110, 130, 165), (x, y), (x - slant, y - length), 1)

    def draw_lightning(self, surface: pygame.Surface) -> None:
        self.lightning.draw(surface)