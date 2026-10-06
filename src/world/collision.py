"""Axis-separated rectangle collision helpers."""
from __future__ import annotations

from typing import Iterable

import pygame


def collide_axis(
    rect: pygame.Rect, walls: Iterable[pygame.Rect], axis: str, delta: float
) -> bool:
    """Push `rect` out of any wall it overlaps along one axis.

    `delta` is the movement just applied on that axis; its sign tells us
    which side of the wall to snap to. Returns True if a collision occurred.
    """
    collided = False
    for wall in walls:
        if not rect.colliderect(wall):
            continue
        collided = True
        if axis == "x":
            if delta > 0:
                rect.right = wall.left
            elif delta < 0:
                rect.left = wall.right
        else:
            if delta > 0:
                rect.bottom = wall.top
            elif delta < 0:
                rect.top = wall.bottom
    return collided