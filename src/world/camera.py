"""Smooth-follow camera with map bounds."""
from __future__ import annotations

import math

import pygame
from pygame import Vector2

from src.core import settings


class Camera:
    def __init__(self, view_width: int, view_height: int,
                 world_width: int, world_height: int) -> None:
        self.view_width = view_width
        self.view_height = view_height
        self.world_width = world_width
        self.world_height = world_height
        self.offset = Vector2(0, 0)  # world position of the screen's top-left

    def snap_to(self, target: Vector2) -> None:
        """Jump instantly to the target (used when a level starts)."""
        self.offset = self._clamp(self._desired(target))

    def update(self, target: Vector2, dt: float) -> None:
        desired = self._desired(target)
        # Frame-rate independent smoothing (exponential decay).
        t = 1.0 - math.exp(-settings.CAMERA_SMOOTHING * dt)
        self.offset += (desired - self.offset) * t
        self.offset = self._clamp(self.offset)

    def world_to_screen(self, pos: Vector2) -> Vector2:
        return Vector2(pos) - self.offset

    def screen_to_world(self, pos: tuple[int, int] | Vector2) -> Vector2:
        return Vector2(pos) + self.offset

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-round(self.offset.x), -round(self.offset.y))

    def view_rect(self) -> pygame.Rect:
        """The part of the world currently visible (used for culling)."""
        return pygame.Rect(round(self.offset.x), round(self.offset.y),
                           self.view_width, self.view_height)

    def _desired(self, target: Vector2) -> Vector2:
        return Vector2(target.x - self.view_width / 2,
                       target.y - self.view_height / 2)

    def _clamp(self, offset: Vector2) -> Vector2:
        max_x = max(0, self.world_width - self.view_width)
        max_y = max(0, self.world_height - self.view_height)
        return Vector2(max(0, min(offset.x, max_x)),
                       max(0, min(offset.y, max_y)))