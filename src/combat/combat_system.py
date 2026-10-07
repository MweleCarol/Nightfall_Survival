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
    critical: bool = False


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
                    enemies: Sequence[Enemy], walls: Sequence[pygame.Rect],
                    crit_chance: float = 0.0) -> bool:
        """Try to fire. Returns True if a shot was actually fired."""
        if not weapon.fire():
            return False

        definition = weapon.definition
        direction = apply_spread(aim_direction, definition.spread, self.rng)
        hit = cast_ray(origin, direction, definition.range, enemies, walls)

        end = origin + direction * hit.distance
        muzzle = origin + direction * settings.MUZZLE_OFFSET
        critical = False

        if hit.enemy is not None:
            critical = crit_chance > 0 and self.rng.random() < crit_chance
            damage = calculate_damage(weapon.damage, critical=critical,
                                      critical_multiplier=settings.CRIT_MULTIPLIER)
            killed = hit.enemy.take_damage(damage)
            self._emit("ENEMY_HIT", {"damage": damage, "critical": critical})
            if killed:
                self._emit("ENEMY_DIED", {
                    "enemy_id": hit.enemy.definition.id,
                    "xp": hit.enemy.xp_reward,
                    "position": (hit.enemy.position.x, hit.enemy.position.y),
                })

        self.tracers.append(Tracer(muzzle, end, settings.TRACER_LIFETIME,
                                   hit.enemy is not None, critical))
        self._emit("SHOT_FIRED", {"weapon": definition.id})
        return True

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        for tracer in self.tracers:
            fade = max(0.0, tracer.life / settings.TRACER_LIFETIME)
            if tracer.critical:                              # criticals glow gold-white
                color = (int(255 * fade), int(245 * fade), int(170 * fade))
            else:
                color = (int(255 * fade), int(220 * fade), int(120 * fade))
            start = camera.world_to_screen(tracer.start)
            end = camera.world_to_screen(tracer.end)
            pygame.draw.line(surface, color, start, end, 3 if tracer.critical else 2)
            if fade > 0.5:                                  # muzzle flash
                pygame.draw.circle(surface, settings.COLOR_AMBER, start, 7)
            if tracer.hit_enemy:                            # impact spark
                spark = settings.COLOR_AMBER if tracer.critical else settings.COLOR_ACCENT
                pygame.draw.circle(surface, spark, end, 9 if tracer.critical else 6)

    def _emit(self, event: str, data: dict) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)