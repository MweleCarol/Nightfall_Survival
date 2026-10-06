"""Enemy definitions (from JSON) and the base Enemy with its AI state machine."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import pygame
from pygame import Vector2

from src.core import settings
from src.services.data_loader import DataLoadError, load_json, require_field
from src.world.camera import Camera
from src.world.collision import collide_axis

_NUMBER = (int, float)


class AIState(Enum):
    IDLE = "IDLE"
    CHASE = "CHASE"
    ATTACK = "ATTACK"
    SEARCH = "SEARCH"
    DEAD = "DEAD"


@dataclass(frozen=True)
class EnemyDef:
    """Static enemy stats: one per entry in enemies.json."""
    id: str
    name: str
    type: str
    max_health: int
    speed: float
    detection_range: float
    attack_range: float
    attack_damage: int
    attack_cooldown: float
    attack_windup: float
    search_time: float
    xp_reward: int
    radius: int
    color: tuple[int, int, int]

    @classmethod
    def from_dict(cls, data: dict, where: str) -> EnemyDef:
        color = require_field(data, "color", list, where)
        if len(color) != 3 or not all(
                isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255
                for c in color):
            raise DataLoadError(f"{where}: field 'color' must be [r, g, b] integers 0-255")
        definition = cls(
            id=require_field(data, "id", str, where),
            name=require_field(data, "name", str, where),
            type=require_field(data, "type", str, where),
            max_health=require_field(data, "max_health", int, where),
            speed=float(require_field(data, "speed", _NUMBER, where)),
            detection_range=float(require_field(data, "detection_range", _NUMBER, where)),
            attack_range=float(require_field(data, "attack_range", _NUMBER, where)),
            attack_damage=require_field(data, "attack_damage", int, where),
            attack_cooldown=float(require_field(data, "attack_cooldown", _NUMBER, where)),
            attack_windup=float(require_field(data, "attack_windup", _NUMBER, where)),
            search_time=float(require_field(data, "search_time", _NUMBER, where)),
            xp_reward=require_field(data, "xp_reward", int, where),
            radius=require_field(data, "radius", int, where),
            color=(color[0], color[1], color[2]),
        )
        if (definition.max_health <= 0 or definition.detection_range <= 0
                or definition.attack_range <= 0 or definition.attack_cooldown <= 0
                or definition.radius <= 0):
            raise DataLoadError(
                f"{where}: max_health, detection_range, attack_range, "
                f"attack_cooldown and radius must be > 0")
        if (definition.speed < 0 or definition.attack_damage < 0 or definition.attack_windup < 0
                or definition.search_time < 0 or definition.xp_reward < 0):
            raise DataLoadError(
                f"{where}: speed, attack_damage, attack_windup, search_time "
                f"and xp_reward must be >= 0")
        return definition


def load_enemy_defs(path: str = settings.ENEMIES_FILE) -> dict[str, EnemyDef]:
    data = load_json(path)
    items = require_field(data, "enemies", list, path)
    definitions: dict[str, EnemyDef] = {}
    for index, item in enumerate(items):
        where = f"{path}: enemies[{index}]"
        if not isinstance(item, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = EnemyDef.from_dict(item, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


class Enemy:
    """Base enemy: position, health and a finite-state-machine AI."""

    def __init__(self, definition: EnemyDef, position: tuple[float, float],
                 health_multiplier: float = 1.0, damage_multiplier: float = 1.0) -> None:
        self.definition = definition
        self.position = Vector2(position)
        self.max_health = max(1, round(definition.max_health * health_multiplier))
        self.health = self.max_health
        self.attack_damage = round(definition.attack_damage * damage_multiplier)

        self.state = AIState.IDLE
        self.last_known = Vector2(position)   # where the player was last seen
        self.alerted = False                  # set when shot while IDLE
        self.attack_timer = 0.0
        self.search_timer = 0.0
        self.hit_flash = 0.0
        self.death_timer = 0.0
        self.facing = Vector2(1, 0)
        self.rect = pygame.Rect(0, 0, definition.radius * 2, definition.radius * 2)
        self._sync_rect()

    # ---- queries ----
    @property
    def radius(self) -> int:
        return self.definition.radius

    @property
    def xp_reward(self) -> int:
        return self.definition.xp_reward

    @property
    def is_dead(self) -> bool:
        return self.state is AIState.DEAD

    @property
    def is_removable(self) -> bool:
        return self.is_dead and self.death_timer <= 0

    # ---- damage ----
    def take_damage(self, amount: int) -> bool:
        """Apply damage. Returns True only if this call killed the enemy."""
        if self.is_dead or amount <= 0:
            return False
        self.health = max(0, self.health - amount)
        self.hit_flash = 0.12
        self.alerted = True                   # being shot wakes an idle enemy
        if self.health == 0:
            self.state = AIState.DEAD
            self.death_timer = settings.ENEMY_CORPSE_TIME
            return True
        return False

    # ---- AI ----
    def update(self, dt: float, target: Vector2, target_valid: bool,
               walls: Sequence[pygame.Rect]) -> int:
        """Advance the AI. Returns damage dealt to the target this frame (usually 0).

        `target_valid` is False when the player is dead or inside the safe zone.
        """
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.attack_timer = max(0.0, self.attack_timer - dt)

        if self.is_dead:
            self.death_timer -= dt
            return 0

        self._think(target, target_valid, dt)

        if self.state is AIState.CHASE:
            self._move_towards(target, dt, walls)
        elif self.state is AIState.SEARCH:
            self._move_towards(self.last_known, dt, walls)
        elif self.state is AIState.ATTACK:
            self._face(target)
            if self.attack_timer <= 0:
                self.attack_timer = self.definition.attack_cooldown
                return self.attack_damage
        return 0

    def _think(self, target: Vector2, target_valid: bool, dt: float) -> None:
        """Decide state transitions (the 'brain'). Movement happens afterwards."""
        d = self.definition
        if not target_valid:
            self._set_state(AIState.IDLE)
            self.alerted = False
            return

        distance = self.position.distance_to(target)

        if self.state is AIState.IDLE:
            if distance <= d.detection_range or self.alerted:
                self.last_known = Vector2(target)
                self._set_state(AIState.CHASE)

        elif self.state is AIState.CHASE:
            if distance <= d.attack_range:
                self.last_known = Vector2(target)
                self._set_state(AIState.ATTACK)
            elif distance > d.detection_range * settings.ENEMY_LOSE_INTEREST_FACTOR:
                self._set_state(AIState.SEARCH)      # keeps the old last_known
            else:
                self.last_known = Vector2(target)

        elif self.state is AIState.ATTACK:
            self.last_known = Vector2(target)
            if distance > d.attack_range * settings.ENEMY_ATTACK_HYSTERESIS:
                self._set_state(AIState.CHASE)

        elif self.state is AIState.SEARCH:
            if distance <= d.detection_range:
                self.last_known = Vector2(target)
                self._set_state(AIState.CHASE)
            else:
                self.search_timer -= dt
                arrived = (self.position.distance_to(self.last_known)
                           < settings.ENEMY_ARRIVE_DISTANCE)
                if arrived or self.search_timer <= 0:
                    self._set_state(AIState.IDLE)

    def _set_state(self, new_state: AIState) -> None:
        if new_state is self.state:
            return
        self.state = new_state
        if new_state is AIState.CHASE:
            self.alerted = False
        elif new_state is AIState.ATTACK:   # wind-up: the first hit is never instant
            self.attack_timer = max(self.attack_timer, self.definition.attack_windup)
        elif new_state is AIState.SEARCH:
            self.search_timer = self.definition.search_time

    # ---- movement ----
    def _face(self, point: Vector2) -> None:
        offset = point - self.position
        if offset.length_squared() > 0:
            self.facing = offset.normalize()

    def _move_towards(self, goal: Vector2, dt: float, walls: Sequence[pygame.Rect]) -> None:
        offset = goal - self.position
        if offset.length_squared() < 1.0:
            return
        direction = offset.normalize()
        self.facing = direction
        step = direction * self.definition.speed * dt

        if step.x != 0:
            self.position.x += step.x
            self._sync_rect()
            if collide_axis(self.rect, walls, "x", step.x):
                self.position.x = self.rect.centerx
        if step.y != 0:
            self.position.y += step.y
            self._sync_rect()
            if collide_axis(self.rect, walls, "y", step.y):
                self.position.y = self.rect.centery
        self._clamp_to_world()

    def _clamp_to_world(self) -> None:
        r = self.radius
        self.position.x = max(r, min(settings.WORLD_WIDTH - r, self.position.x))
        self.position.y = max(r, min(settings.WORLD_HEIGHT - r, self.position.y))
        self._sync_rect()

    def _sync_rect(self) -> None:
        self.rect.center = (round(self.position.x), round(self.position.y))

    # ---- drawing ----
    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        center = camera.world_to_screen(self.position)
        r = self.radius

        if self.is_dead:                       # shrinking dark corpse
            fade = max(0.0, self.death_timer / settings.ENEMY_CORPSE_TIME)
            pygame.draw.circle(surface, (36, 40, 46), center, max(2, int(r * (0.4 + 0.6 * fade))))
            return

        body = (255, 255, 255) if self.hit_flash > 0 else self.definition.color
        pygame.draw.circle(surface, body, center, r)
        outline = settings.COLOR_ACCENT if self.state is AIState.ATTACK else (20, 24, 32)
        pygame.draw.circle(surface, outline, center, r, 3)
        eye = center + self.facing * (r * 0.55)
        pygame.draw.circle(surface, settings.COLOR_ACCENT, eye, 4)

        if self.health < self.max_health:      # health bar above the head
            width = 36
            x, y = int(center.x - width / 2), int(center.y - r - 12)
            pygame.draw.rect(surface, (20, 26, 40), (x, y, width, 5))
            pygame.draw.rect(surface, settings.COLOR_ACCENT,
                             (x, y, int(width * self.health / self.max_health), 5))

    def draw_debug(self, surface: pygame.Surface, camera: Camera,
                   font: pygame.font.Font) -> None:
        """F3 overlay: detection range (yellow), attack range (red), AI state."""
        center = camera.world_to_screen(self.position)
        pygame.draw.circle(surface, (255, 255, 0), center, int(self.definition.detection_range), 1)
        pygame.draw.circle(surface, (255, 0, 0), center, int(self.definition.attack_range), 1)
        label = font.render(self.state.value, True, (255, 255, 255))
        surface.blit(label, (center.x - label.get_width() / 2, center.y - self.radius - 34))