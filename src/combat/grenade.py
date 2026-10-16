"""Grenades: data definitions, flight, blast damage and the system that runs them."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import pygame
from pygame import Vector2

from src.combat.hitscan import ray_rect_distance
from src.core import settings
from src.core.event_bus import EventBus
from src.enemies.enemy import Enemy
from src.player.inventory import ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field
from src.world.camera import Camera
from src.world.collision import collide_axis

_NUMBER = (int, float)
GRENADE_SIZE = 10            # pixels: the size of a grenade for wall collisions
MAX_SUBSTEP = 4.0            # a grenade never moves more than this between wall checks
BLAST_LIFETIME = 0.45        # seconds the expanding ring stays on screen


def _number(data: dict, key: str, where: str, minimum: float = 0.0,
            exclusive: bool = False) -> float:
    value = float(require_field(data, key, _NUMBER, where))
    if value < minimum or (exclusive and value == minimum):
        raise DataLoadError(
            f"{where}: field '{key}' must be {'>' if exclusive else '>='} {minimum:g}")
    return value


@dataclass(frozen=True)
class GrenadeDef:
    id: str                    # also the id of the inventory item that is thrown
    name: str
    damage: int                # at the centre of the blast
    radius: float
    fuse: float                # seconds from the throw to the explosion
    throw_speed: float
    max_range: float
    knockback: float           # how far a zombie at the centre is shoved
    self_damage_factor: float  # fraction of the damage the player takes (0 to 1)

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> GrenadeDef:
        item_id = require_field(data, "id", str, where)
        if item_id not in item_defs:
            raise DataLoadError(f"{where}: unknown item '{item_id}'")
        if item_defs[item_id].type != "throwable":
            raise DataLoadError(f"{where}: item '{item_id}' must have type 'throwable'")
        damage = require_field(data, "damage", int, where)
        if damage <= 0:
            raise DataLoadError(f"{where}: field 'damage' must be > 0")
        factor = _number(data, "self_damage_factor", where)
        if factor > 1.0:
            raise DataLoadError(f"{where}: field 'self_damage_factor' must be between 0 and 1")
        return cls(
            id=item_id, name=require_field(data, "name", str, where), damage=damage,
            radius=_number(data, "radius", where, 0.0, True),
            fuse=_number(data, "fuse", where, 0.0, True),
            throw_speed=_number(data, "throw_speed", where, 0.0, True),
            max_range=_number(data, "max_range", where, 0.0, True),
            knockback=_number(data, "knockback", where), self_damage_factor=factor)


def load_grenade_defs(item_defs: dict[str, ItemDef],
                      path: str = settings.GRENADES_FILE) -> dict[str, GrenadeDef]:
    data = load_json(path)
    items = require_field(data, "grenades", list, path)
    definitions: dict[str, GrenadeDef] = {}
    for index, raw in enumerate(items):
        where = f"{path}: grenades[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = GrenadeDef.from_dict(raw, item_defs, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


# ---------------------------------------------------------------- pure helpers
def blast_damage(definition: GrenadeDef, distance: float) -> int:
    """Damage at a distance from the centre: 100% in the middle, 40% at the edge, 0 outside."""
    if distance >= definition.radius:
        return 0
    falloff = 1.0 - 0.6 * distance / definition.radius
    return round(definition.damage * falloff)


def has_line_of_sight(origin: Vector2, target: Vector2, walls: Sequence[pygame.Rect]) -> bool:
    """False if a wall lies between the two points (walls shield from the blast)."""
    offset = target - origin
    distance = offset.length()
    if distance == 0:
        return True
    direction = offset / distance
    for wall in walls:
        hit = ray_rect_distance(origin, direction, wall, distance)
        if hit is not None and hit < distance - 1.0:
            return False
    return True


def apply_knockback(enemy: Enemy, direction: Vector2, distance: float,
                    walls: Sequence[pygame.Rect]) -> None:
    """Shove an enemy away from a blast. It stops at walls and at the edge of the world."""
    if distance <= 0 or direction.length_squared() == 0:
        return
    step = direction.normalize() * distance
    enemy.position.x += step.x
    enemy.rect.center = (round(enemy.position.x), round(enemy.position.y))
    if collide_axis(enemy.rect, walls, "x", step.x):
        enemy.position.x = enemy.rect.centerx
    enemy.position.y += step.y
    enemy.rect.center = (round(enemy.position.x), round(enemy.position.y))
    if collide_axis(enemy.rect, walls, "y", step.y):
        enemy.position.y = enemy.rect.centery
    r = enemy.radius
    enemy.position.x = max(r, min(settings.WORLD_WIDTH - r, enemy.position.x))
    enemy.position.y = max(r, min(settings.WORLD_HEIGHT - r, enemy.position.y))
    enemy.rect.center = (round(enemy.position.x), round(enemy.position.y))


# ---------------------------------------------------------------- a grenade in the air
class Grenade:
    def __init__(self, definition: GrenadeDef, origin: Vector2, target: Vector2) -> None:
        self.definition = definition
        self.position = Vector2(origin)
        offset = Vector2(target) - Vector2(origin)
        self.heading = offset.normalize() if offset.length_squared() > 0 else Vector2(1, 0)
        self.travel_left = min(offset.length(), definition.max_range)
        self.fuse = definition.fuse
        self.rect = pygame.Rect(0, 0, GRENADE_SIZE, GRENADE_SIZE)
        self._sync()

    def _sync(self) -> None:
        self.rect.center = (round(self.position.x), round(self.position.y))

    def update(self, dt: float, walls: Sequence[pygame.Rect]) -> bool:
        """Fly towards the target, then wait. Returns True when the fuse has run out."""
        self.fuse -= dt
        remaining = min(self.definition.throw_speed * dt, self.travel_left) if self.travel_left > 0 else 0.0
        while remaining > 0:
            distance = min(remaining, MAX_SUBSTEP)          # small steps: no jumping over walls
            remaining -= distance
            self.travel_left -= distance
            if self._move(self.heading * distance, walls):
                self.travel_left = 0.0                      # it hit something and stops here
                break
        return self.fuse <= 0

    def _move(self, step: Vector2, walls: Sequence[pygame.Rect]) -> bool:
        """Move with wall collision, one axis at a time. Returns True if a wall stopped it."""
        blocked = False
        if step.x != 0:
            self.position.x += step.x
            self._sync()
            if collide_axis(self.rect, walls, "x", step.x):
                self.position.x = self.rect.centerx
                blocked = True
        if step.y != 0:
            self.position.y += step.y
            self._sync()
            if collide_axis(self.rect, walls, "y", step.y):
                self.position.y = self.rect.centery
                blocked = True
        return blocked
@dataclass
class Blast:
    """The visual of an explosion: an expanding ring."""
    position: Vector2
    radius: float
    age: float = 0.0


class GrenadeSystem:
    """Runs every grenade in flight and applies the explosions.

    Events: GRENADE_THROWN, GRENADE_EXPLODED, plus ENEMY_HIT / ENEMY_DIED / PLAYER_DAMAGED
    (the same ones the guns use, so XP, loot, missions and effects just work).
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus
        self.grenades: list[Grenade] = []
        self.blasts: list[Blast] = []

    def throw(self, definition: GrenadeDef, origin: Vector2, target: Vector2) -> Grenade:
        grenade = Grenade(definition, origin, target)
        self.grenades.append(grenade)
        self._emit("GRENADE_THROWN", {"grenade": definition.id, "origin": (origin.x, origin.y),
                                      "target": (target.x, target.y)})
        return grenade

    def update(self, dt: float, enemies: Sequence[Enemy], player,
               walls: Sequence[pygame.Rect]) -> None:
        for blast in self.blasts:
            blast.age += dt
        self.blasts = [b for b in self.blasts if b.age < BLAST_LIFETIME]
        for grenade in list(self.grenades):
            if grenade.update(dt, walls):
                self.grenades.remove(grenade)
                self._explode(grenade, enemies, player, walls)

    def _explode(self, grenade: Grenade, enemies: Sequence[Enemy], player,
                 walls: Sequence[pygame.Rect]) -> None:
        definition = grenade.definition
        center = Vector2(grenade.position)
        self.blasts.append(Blast(center, definition.radius))
        self._emit("GRENADE_EXPLODED", {"position": (center.x, center.y), "radius": definition.radius})

        for enemy in enemies:
            if enemy.is_dead:
                continue
            offset = enemy.position - center
            distance = max(0.0, offset.length() - enemy.radius)        # to the zombie's edge
            damage = blast_damage(definition, distance)
            if damage <= 0 or not has_line_of_sight(center, enemy.position, walls):
                continue
            direction = offset.normalize() if offset.length_squared() > 0 else Vector2(1, 0)
            before = enemy.health
            killed = enemy.take_damage(damage)
            dealt = before - enemy.health
            if dealt <= 0:
                continue                                               # e.g. a boss in its intro
            self._emit("ENEMY_HIT", {
                "damage": dealt, "critical": False, "enemy_id": enemy.definition.id,
                "position": (enemy.position.x, enemy.position.y),
                "direction": (direction.x, direction.y)})
            if killed:
                self._emit("ENEMY_DIED", {
                    "enemy_id": enemy.definition.id, "xp": enemy.xp_reward,
                    "position": (enemy.position.x, enemy.position.y)})
            elif enemy.definition.type != "boss":                      # bosses are too heavy to shove
                push = definition.knockback * (1.0 - distance / definition.radius)
                apply_knockback(enemy, direction, push, walls)

        if player is not None and not player.stats.is_dead:
            distance = max(0.0, (player.position - center).length() - settings.PLAYER_SIZE / 2)
            damage = round(blast_damage(definition, distance) * definition.self_damage_factor)
            if damage > 0 and has_line_of_sight(center, player.position, walls):
                dealt = player.take_damage(damage)
                if dealt:
                    self._emit("PLAYER_DAMAGED", {"amount": dealt})

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        for grenade in self.grenades:
            center = camera.world_to_screen(grenade.position)
            pygame.draw.circle(surface, (70, 92, 60), center, 7)
            pygame.draw.circle(surface, (24, 32, 20), center, 7, 2)
            if int(grenade.fuse * 6) % 2 == 0:                         # a blinking red light
                pygame.draw.circle(surface, (255, 60, 40), center, 3)
        for blast in self.blasts:
            progress = blast.age / BLAST_LIFETIME
            fade = max(0.0, 1.0 - progress)
            center = camera.world_to_screen(blast.position)
            if progress < 0.3:                                         # the initial white flash
                flash = int(blast.radius * 0.45 * (1 - progress / 0.3)) + 4
                pygame.draw.circle(surface, (255, 235, 190), center, flash)
            radius = int(blast.radius * (0.3 + 0.7 * min(1.0, progress * 1.6)))
            ring = (int(255 * fade), int(150 * fade), int(40 * fade))
            pygame.draw.circle(surface, ring, center, radius, max(2, int(10 * fade)))

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)