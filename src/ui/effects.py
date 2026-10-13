"""Reusable visual effects: rain, embers, fog and lightning. Used by the menu now, the game in 9b."""
from __future__ import annotations

import random

import pygame


class RainField:
    """Screen-space rain. Drops fall at an angle and respawn at the top."""

    def __init__(self, width: int, height: int, count: int = 220,
                 rng: random.Random | None = None, wind: float = -90.0,
                 speed: tuple[float, float] = (700.0, 1000.0),
                 length: tuple[float, float] = (14.0, 26.0)) -> None:
        self.width, self.height = width, height
        self.wind = wind
        self.speed_range, self.length_range = speed, length
        self.rng = rng or random.Random()
        self.drops = [self._new_drop(anywhere=True) for _ in range(count)]   # [x, y, speed, length]

    def _new_drop(self, anywhere: bool) -> list[float]:
        x = self.rng.uniform(0, self.width + 60)
        y = self.rng.uniform(0, self.height) if anywhere else self.rng.uniform(-60, 0)
        return [x, y, self.rng.uniform(*self.speed_range), self.rng.uniform(*self.length_range)]

    def update(self, dt: float) -> None:
        for index, drop in enumerate(self.drops):
            drop[1] += drop[2] * dt
            drop[0] += self.wind * dt
            if drop[1] > self.height or drop[0] < -30:
                self.drops[index] = self._new_drop(anywhere=False)

    def draw(self, surface: pygame.Surface, color: tuple[int, int, int] = (120, 140, 175)) -> None:
        for x, y, speed, length in self.drops:
            slant = self.wind / speed * length
            pygame.draw.line(surface, color, (x, y), (x - slant, y - length), 1)


class Ember:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size")

    def __init__(self, x: float, y: float, vx: float, vy: float, life: float, size: int) -> None:
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size = size


class EmberField:
    """Glowing sparks that rise from fixed points and fade out."""

    def __init__(self, sources: list[tuple[int, int]], rate: float = 12.0,
                 rng: random.Random | None = None, max_particles: int = 140) -> None:
        self.sources = list(sources)
        self.rate = rate                      # new embers per second
        self.rng = rng or random.Random()
        self.max_particles = max_particles
        self.particles: list[Ember] = []
        self._carry = 0.0

    def update(self, dt: float) -> None:
        if self.sources and self.rate > 0:
            self._carry += self.rate * dt
            while self._carry >= 1.0:
                self._carry -= 1.0
                if len(self.particles) < self.max_particles:
                    self.particles.append(self._spawn())
        for ember in self.particles:
            ember.life -= dt
            ember.vx += self.rng.uniform(-30, 30) * dt       # a little random drift
            ember.x += ember.vx * dt
            ember.y += ember.vy * dt
        self.particles = [e for e in self.particles if e.life > 0]

    def _spawn(self) -> Ember:
        sx, sy = self.rng.choice(self.sources)
        return Ember(sx + self.rng.uniform(-10, 10), sy, self.rng.uniform(-12, 12),
                     -self.rng.uniform(25, 70), self.rng.uniform(1.8, 4.0),
                     self.rng.choice((1, 2, 2, 3)))

    def draw(self, surface: pygame.Surface) -> None:
        for e in self.particles:
            fade = e.life / e.max_life
            color = (int(255 * fade), int(130 * fade), int(30 * fade))   # dims as it dies
            pygame.draw.circle(surface, color, (int(e.x), int(e.y)), e.size)


class FogLayer:
    """A seamless, slowly scrolling band of soft fog (also used for clouds)."""

    def __init__(self, width: int, height: int, speed: float = 12.0, alpha: int = 40,
                 seed: int = 3, band: tuple[float, float] = (0.45, 1.0),
                 color: tuple[int, int, int] = (170, 185, 210),
                 size: tuple[tuple[int, int], tuple[int, int]] = ((240, 520), (60, 140)),
                 count: int = 26) -> None:
        rng = random.Random(seed)
        self.width = width
        self.speed = speed
        self.offset = 0.0
        self.surface = pygame.Surface((width, height), pygame.SRCALPHA)
        (min_w, max_w), (min_h, max_h) = size
        for _ in range(count):
            w, h = rng.randint(min_w, max_w), rng.randint(min_h, max_h)
            cx = rng.randint(0, width)
            cy = rng.randint(int(height * band[0]), int(height * band[1]))
            for shift in (-width, 0, width):                  # copies on both sides make it tile
                for layer in range(5):                        # concentric ellipses = soft edges
                    scale = 1.0 - layer * 0.18
                    rect = pygame.Rect(0, 0, int(w * scale), int(h * scale))
                    rect.center = (cx + shift, cy)
                    pygame.draw.ellipse(self.surface, (*color, int(alpha * (layer + 1) / 5)), rect)

    def update(self, dt: float) -> None:
        self.offset = (self.offset + self.speed * dt) % self.width

    def draw(self, surface: pygame.Surface) -> None:
        x = int(self.offset)
        surface.blit(self.surface, (x - self.width, 0))
        surface.blit(self.surface, (x, 0))


class LightningFlash:
    """An occasional white-blue flash that fades quickly."""

    def __init__(self, width: int, height: int, rng: random.Random | None = None,
                 min_gap: float = 6.0, max_gap: float = 16.0) -> None:
        self.rng = rng or random.Random()
        self.min_gap, self.max_gap = min_gap, max_gap
        self.timer = self.rng.uniform(min_gap, max_gap)
        self.flash = 0.0                                      # 1.0 right after a strike
        self._overlay = pygame.Surface((width, height))
        self._overlay.fill((190, 205, 255))

    def update(self, dt: float) -> None:
        self.timer -= dt
        if self.timer <= 0:
            self.flash = 1.0
            self.timer = self.rng.uniform(self.min_gap, self.max_gap)
        else:
            self.flash = max(0.0, self.flash - dt * 3.0)

    def draw(self, surface: pygame.Surface) -> None:
        if self.flash > 0.01:
            self._overlay.set_alpha(int(110 * self.flash))
            surface.blit(self._overlay, (0, 0))