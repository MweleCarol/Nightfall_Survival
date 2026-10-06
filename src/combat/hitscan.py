"""Hitscan ray casting: geometry helpers and nearest-target search."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

import pygame
from pygame import Vector2

if TYPE_CHECKING:
    from src.enemies.enemy import Enemy


@dataclass
class HitResult:
    distance: float          # how far the shot travelled
    enemy: Enemy | None      # who was hit (None = hit a wall or reached max range)


def apply_spread(direction: Vector2, spread_degrees: float, rng: random.Random) -> Vector2:
    """Rotate the aim direction by a random angle within +/- spread."""
    direction = Vector2(direction)
    if direction.length_squared() == 0:
        direction = Vector2(1, 0)
    direction = direction.normalize()
    if spread_degrees <= 0:
        return direction
    return direction.rotate(rng.uniform(-spread_degrees, spread_degrees))


def ray_rect_distance(origin: Vector2, direction: Vector2, rect: pygame.Rect,
                      max_distance: float) -> float | None:
    """Distance along the ray to the rectangle, or None. ('Slab' method.)"""
    t_min, t_max = 0.0, max_distance
    for start, step, low, high in (
        (origin.x, direction.x, rect.left, rect.right),
        (origin.y, direction.y, rect.top, rect.bottom),
    ):
        if abs(step) < 1e-9:                      # ray parallel to this slab
            if start < low or start > high:
                return None
        else:
            t1, t2 = (low - start) / step, (high - start) / step
            if t1 > t2:
                t1, t2 = t2, t1
            t_min, t_max = max(t_min, t1), min(t_max, t2)
            if t_min > t_max:
                return None
    return t_min


def ray_circle_distance(origin: Vector2, direction: Vector2, center: Vector2,
                        radius: float, max_distance: float) -> float | None:
    """Distance along the ray to where it enters the circle, or None."""
    to_center = center - origin
    if to_center.length_squared() <= radius * radius:
        return 0.0                                # origin already inside
    along = to_center.dot(direction)
    if along < 0:
        return None                               # circle is behind the ray
    perpendicular_sq = to_center.length_squared() - along * along
    if perpendicular_sq > radius * radius:
        return None                               # ray passes beside it
    entry = along - math.sqrt(radius * radius - perpendicular_sq)
    return entry if entry <= max_distance else None


def cast_ray(origin: Vector2, direction: Vector2, max_range: float,
             enemies: Iterable[Enemy], walls: Iterable[pygame.Rect]) -> HitResult:
    """Find the first thing a shot hits: a wall, an enemy, or nothing in range."""
    limit = max_range
    for wall in walls:
        d = ray_rect_distance(origin, direction, wall, limit)
        if d is not None and d < limit:
            limit = d

    hit_enemy = None
    for enemy in enemies:
        if enemy.is_dead:
            continue
        d = ray_circle_distance(origin, direction, enemy.position, enemy.radius, limit)
        if d is not None and d <= limit:
            limit, hit_enemy = d, enemy
    return HitResult(distance=limit, enemy=hit_enemy)