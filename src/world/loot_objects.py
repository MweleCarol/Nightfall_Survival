"""World objects the player can loot: searchable crates and dropped pickups."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame
from pygame import Vector2

from src.core import settings
from src.world.camera import Camera


@dataclass
class Pickup:
    """An item lying on the ground. Walk over it to collect it."""
    item_id: str
    quantity: int
    position: Vector2
    color: tuple[int, int, int]
    label: str
    age: float = 0.0

    @property
    def expired(self) -> bool:
        return self.age >= settings.PICKUP_LIFETIME

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, camera: Camera,
             font: pygame.font.Font, show_label: bool) -> None:
        bob = math.sin(self.age * 4.0) * 2.0
        center = camera.world_to_screen(self.position) + Vector2(0, bob)
        r = 8
        points = [(center.x, center.y - r), (center.x + r, center.y),
                  (center.x, center.y + r), (center.x - r, center.y)]
        pygame.draw.polygon(surface, self.color, points)
        pygame.draw.polygon(surface, (15, 18, 26), points, 2)
        if show_label:
            text = font.render(f"{self.label} x{self.quantity}", True, settings.COLOR_TEXT)
            surface.blit(text, text.get_rect(midbottom=(center.x, center.y - r - 4)))


class LootContainer:
    """A searchable crate. Restocks every new day."""

    def __init__(self, container_id: str, position: tuple[int, int], category: str) -> None:
        self.id = container_id
        self.position = Vector2(position)
        self.category = category
        self.opened = False

    def reset(self) -> None:
        self.opened = False

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        rect = pygame.Rect(0, 0, 30, 22)
        rect.center = camera.world_to_screen(self.position)
        fill = (46, 50, 60) if self.opened else (150, 108, 40)
        edge = (80, 88, 104) if self.opened else settings.COLOR_AMBER
        pygame.draw.rect(surface, fill, rect)
        pygame.draw.rect(surface, edge, rect, 2)
        if not self.opened:
            pygame.draw.line(surface, edge, rect.midleft, rect.midright, 2)