"""Shooting: applies spread, finds what was hit, deals damage, draws tracers."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

import pygame
from pygame import Vector2

from src.combat.damage import calculate_damage
from src.combat.hitscan import apply_spread, cast_ray
from src.combat.weapon import Weapon
from src.core import settings
from src.core.event_bus import EventBus
from src.enemies.enemy import Enemy
from src.world.camera import Camera


@dataclass
class Tracer:
    """A short-lived bullet trail (pure visual feedback)."""
    start: Vector2
    end: Vector2
    life: float
    hit_enemy: bool


class CombatSystem:
    def __init__(self, event_bus: EventBus | None = None,
                 rng: random.Random | None = None) -> None:
        self.event_bus = event_bus
        self.rng = rng or random.Random()
        self.tracers: list[Tracer] = []

    def update(self, dt: float) -> None:
        for tracer in self.tracers:
            tracer.life -= dt
        self.tracers = [t for t in self.tracers if t.life > 0]

    def fire_weapon(self, origin: Vector2, aim_direction: Vector2, weapon: Weapon,
                    enemies: Sequence[Enemy], walls: Sequence[pygame.Rect]) -> bool:
        """Try to fire. Returns True if a shot was actually fired."""
        if not weapon.fire():
            return False

        definition = weapon.definition
        direction = apply_spread(aim_direction, definition.spread, self.rng)
        hit = cast_ray(origin, direction, definition.range, enemies, walls)

        end = origin + direction * hit.distance
        muzzle = origin + direction * settings.MUZZLE_OFFSET
        self.tracers.append(Tracer(muzzle, end, settings.TRACER_LIFETIME,
                                   hit.enemy is not None))
        self._emit("SHOT_FIRED", {"weapon": definition.id})

        if hit.enemy is not None:
            damage = calculate_damage(definition.damage)
            if hit.enemy.take_damage(damage):
                self._emit("ENEMY_DIED", {
                    "enemy_id": hit.enemy.definition.id,
                    "xp": hit.enemy.xp_reward,
                    "position": (hit.enemy.position.x, hit.enemy.position.y),
                })
        return True

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        for tracer in self.tracers:
            fade = max(0.0, tracer.life / settings.TRACER_LIFETIME)
            color = (int(255 * fade), int(220 * fade), int(120 * fade))
            start = camera.world_to_screen(tracer.start)
            end = camera.world_to_screen(tracer.end)
            pygame.draw.line(surface, color, start, end, 2)
            if fade > 0.5:                                  # muzzle flash
                pygame.draw.circle(surface, settings.COLOR_AMBER, start, 7)
            if tracer.hit_enemy:                            # impact spark
                pygame.draw.circle(surface, settings.COLOR_ACCENT, end, 6)

    def _emit(self, event: str, data: dict) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)