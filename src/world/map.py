"""Temporary hard-coded test map. Later this becomes data-driven."""
from __future__ import annotations

import pygame

from src.core import settings
from src.world.camera import Camera

# (x, y, width, height)
BUILDINGS: list[tuple[int, int, int, int]] = [
    (200, 200, 600, 400), (1000, 200, 500, 400),
    (1800, 200, 700, 400), (2700, 200, 300, 400),
    (200, 900, 600, 400), (1000, 900, 400, 400),
    (1800, 900, 500, 400), (2600, 900, 400, 400),
    (200, 1700, 700, 500), (1100, 1700, 500, 500),
    (1900, 1700, 600, 500), (2700, 1700, 300, 500),
    # small obstacles (abandoned vehicles)
    (1500, 650, 120, 60), (1650, 1500, 120, 60),
]

SPAWN_POINT = (1600, 1100)
GRID_SIZE = 100

COLOR_GROUND = (18, 22, 34)
COLOR_GRID = (26, 32, 48)
COLOR_BUILDING = (40, 52, 76)
COLOR_BUILDING_EDGE = (70, 88, 120)


class GameMap:
    def __init__(self) -> None:
        self.width = settings.WORLD_WIDTH
        self.height = settings.WORLD_HEIGHT
        self.walls: list[pygame.Rect] = [pygame.Rect(b) for b in BUILDINGS]

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.fill(COLOR_GROUND)
        view = camera.view_rect()

        # Grid lines give a sense of movement while the world is plain.
        start_x = view.left - view.left % GRID_SIZE
        for x in range(start_x, view.right + GRID_SIZE, GRID_SIZE):
            sx = x - round(camera.offset.x)
            pygame.draw.line(surface, COLOR_GRID, (sx, 0), (sx, view.height))
        start_y = view.top - view.top % GRID_SIZE
        for y in range(start_y, view.bottom + GRID_SIZE, GRID_SIZE):
            sy = y - round(camera.offset.y)
            pygame.draw.line(surface, COLOR_GRID, (0, sy), (view.width, sy))

        # Culling: only draw walls that are on screen.
        for wall in self.walls:
            if wall.colliderect(view):
                screen_rect = camera.apply(wall)
                pygame.draw.rect(surface, COLOR_BUILDING, screen_rect)
                pygame.draw.rect(surface, COLOR_BUILDING_EDGE, screen_rect, 2)