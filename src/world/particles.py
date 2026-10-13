"""World-space particles: sparks, blood, smoke. Pure logic plus simple drawing."""
from __future__ import annotations

import random

import pygame
from pygame import Vector2

from src.world.camera import Camera


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color", "drag")

    def __init__(self, x: float, y: float, vx: float, vy: float, life: float, size: int,
                 color: tuple[int, int, int], drag: float) -> None:
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.size = size
        self.color = color
        self.drag = drag


class ParticleSystem:
    """Short-lived dots that fly out, slow down (drag), shrink and disappear."""

    def __init__(self, rng: random.Random | None = None, max_particles: int = 500) -> None:
        self.rng = rng or random.Random()
        self.max_particles = max_particles          # a hard cap keeps big fights cheap
        self.particles: list[Particle] = []

    def burst(self, position: Vector2, direction: Vector2, count: int,
              speed: tuple[float, float] = (60.0, 220.0), spread: float = 40.0,
              life: tuple[float, float] = (0.25, 0.6), size: tuple[int, int] = (2, 4),
              color: tuple[int, int, int] = (255, 200, 80), drag: float = 3.0) -> None:
        """Throw `count` particles in a cone around `direction` (all directions if it is zero)."""
        base = Vector2(direction)
        radial = base.length_squared() == 0
        if not radial:
            base = base.normalize()
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                return
            if radial:
                heading = Vector2(1, 0).rotate(self.rng.uniform(0, 360))
            else:
                heading = base.rotate(self.rng.uniform(-spread, spread))
            velocity = heading * self.rng.uniform(*speed)
            self.particles.append(Particle(
                position.x, position.y, velocity.x, velocity.y, self.rng.uniform(*life),
                self.rng.randint(size[0], size[1]), color, drag))

    def update(self, dt: float) -> None:
        for p in self.particles:
            p.life -= dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            damping = max(0.0, 1.0 - p.drag * dt)
            p.vx *= damping
            p.vy *= damping
        self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        width, height = surface.get_size()
        for p in self.particles:
            sx, sy = int(p.x - camera.offset.x), int(p.y - camera.offset.y)
            if -10 <= sx <= width + 10 and -10 <= sy <= height + 10:        # skip off-screen ones
                radius = max(1, int(p.size * p.life / p.max_life))          # shrinks as it dies
                pygame.draw.circle(surface, p.color, (sx, sy), radius)