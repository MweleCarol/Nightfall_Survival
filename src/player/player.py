"""The player: position, movement, collision, aim, weapon."""
from __future__ import annotations

from typing import Sequence

import pygame
from pygame import Vector2

from src.combat.weapon import Weapon
from src.core import settings
from src.player.stats import Stats
from src.world.camera import Camera
from src.world.collision import collide_axis
from src.player.inventory import Inventory


class Player:
    def __init__(self, position: tuple[float, float],weapon: Weapon | None = None,
                 inventory: Inventory | None = None) -> None:
        self.position = Vector2(position)
        self.velocity = Vector2(0, 0)
        self.stats = Stats()
        self.weapon = weapon
        self.inventory = inventory
        self.rect = pygame.Rect(0, 0, settings.PLAYER_SIZE, settings.PLAYER_SIZE)
        self.aim_direction = Vector2(1, 0)
        self.is_sprinting = False
        self.hurt_timer = 0.0
        self._sync_rect()

    # ---- input-facing API ----
    def aim_at(self, world_target: Vector2) -> None:
        offset = world_target - self.position
        if offset.length_squared() > 0:
            self.aim_direction = offset.normalize()

    def take_damage(self, amount: int) -> int:
        """Apply damage and trigger the hurt flash. Returns damage actually dealt."""
        dealt = self.stats.take_damage(amount)
        if dealt:
            self.hurt_timer = settings.PLAYER_HURT_FLASH
        return dealt

    def use_item(self, item_id: str) -> bool:
        """Use a consumable from the inventory. Returns True if it was used."""
        if self.inventory is None or self.stats.is_dead:
            return False
        definition = self.inventory.definitions.get(item_id)
        if definition is None or definition.type != "consumable":
            return False
        if not self.inventory.has(item_id):
            return False
        if definition.heal > 0:
            if self.stats.health >= self.stats.max_health:
                return False                      # don't waste it at full health
            self.stats.heal(definition.heal)
        self.inventory.remove(item_id, 1)
        return True

    def quick_heal(self) -> str | None:
        """Use the smallest healing item that covers the missing health (else the biggest)."""
        if self.inventory is None or self.stats.is_dead:
            return None
        missing = self.stats.max_health - self.stats.health
        if missing <= 0:
            return None
        options = sorted(
            (d for d in self.inventory.definitions.values()
             if d.type == "consumable" and d.heal > 0 and self.inventory.has(d.id)),
            key=lambda d: d.heal)
        if not options:
            return None
        chosen = next((d for d in options if d.heal >= missing), options[-1])
        return chosen.name if self.use_item(chosen.id) else None

    def update(self, dt: float, direction: Vector2, sprint_held: bool,
               walls: Sequence[pygame.Rect]) -> None:
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        if self.stats.is_dead:
            self.velocity = Vector2(0, 0)
            self.is_sprinting = False
            return

        if self.weapon is not None:
            self.weapon.update(dt)

        moving = direction.length_squared() > 0
        if moving:
            direction = direction.normalize()  # W+D is not faster than W

        self.is_sprinting = self._resolve_sprint(sprint_held and moving)
        speed = settings.PLAYER_SPEED
        if self.is_sprinting:
            speed *= settings.PLAYER_SPRINT_MULTIPLIER
        self.velocity = direction * speed

        self._move_x(dt, walls)
        self._move_y(dt, walls)
        self._clamp_to_world()
        self.stats.update_stamina(dt, self.is_sprinting)

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        center = camera.world_to_screen(self.position)
        radius = settings.PLAYER_SIZE // 2
        if self.hurt_timer > 0:
            color = settings.COLOR_ACCENT
        elif self.is_sprinting:
            color = settings.COLOR_AMBER
        else:
            color = settings.COLOR_TEXT
        pygame.draw.circle(surface, color, center, radius)
        tip = center + self.aim_direction * (radius + 12)
        pygame.draw.line(surface, settings.COLOR_ACCENT, center, tip, 4)

    # ---- internals ----
    def _resolve_sprint(self, wants_sprint: bool) -> bool:
        if not wants_sprint:
            return False
        if self.is_sprinting:               # keep going until empty
            return self.stats.stamina > 0
        return self.stats.stamina >= settings.STAMINA_MIN_TO_SPRINT

    def _sync_rect(self) -> None:
        self.rect.center = (round(self.position.x), round(self.position.y))

    def _move_x(self, dt: float, walls: Sequence[pygame.Rect]) -> None:
        delta = self.velocity.x * dt
        if delta == 0:
            return
        self.position.x += delta
        self._sync_rect()
        if collide_axis(self.rect, walls, "x", delta):
            self.position.x = self.rect.centerx

    def _move_y(self, dt: float, walls: Sequence[pygame.Rect]) -> None:
        delta = self.velocity.y * dt
        if delta == 0:
            return
        self.position.y += delta
        self._sync_rect()
        if collide_axis(self.rect, walls, "y", delta):
            self.position.y = self.rect.centery

    def _clamp_to_world(self) -> None:
        half = settings.PLAYER_SIZE / 2
        self.position.x = max(half, min(settings.WORLD_WIDTH - half, self.position.x))
        self.position.y = max(half, min(settings.WORLD_HEIGHT - half, self.position.y))
        self._sync_rect()