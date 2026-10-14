"""A circular minimap: a pre-rendered map of the district, scrolled around the player."""
from __future__ import annotations

import pygame
from pygame import Vector2

from src.ui import theme

SCALE = 0.1          # one minimap pixel is ten world pixels


def project(offset: Vector2, scale: float, radius: float,
            margin: float = 7.0) -> tuple[Vector2, bool]:
    """Where a point (given relative to the player) appears inside the minimap circle.

    Returns (position relative to the centre, clamped). `clamped` is True when the point is
    outside the circle and was pulled to the rim, so it can be drawn as a direction marker.
    """
    point = Vector2(offset) * scale
    limit = radius - margin
    distance = point.length()
    if distance <= limit:
        return point, False
    return point * (limit / distance), True


class Minimap:
    def __init__(self, game_map, font: pygame.font.Font, radius: int = 66, scale: float = SCALE) -> None:
        self.radius = radius
        self.scale = scale
        diameter = radius * 2
        self._world = self._render_world(game_map)
        self._buffer = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        self._mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(self._mask, (255, 255, 255, 255), (radius, radius), radius)
        self._backdrop = self._build_backdrop(font)

    def _render_world(self, game_map) -> pygame.Surface:
        """The whole district drawn once, padded by one radius so the window never leaves it."""
        s, pad = self.scale, self.radius
        surface = pygame.Surface((int(game_map.width * s) + 2 * pad, int(game_map.height * s) + 2 * pad))
        surface.fill((11, 18, 30))
        for building in game_map.buildings:
            rect = pygame.Rect(int(building.rect.x * s) + pad, int(building.rect.y * s) + pad,
                               max(2, int(building.rect.width * s)), max(2, int(building.rect.height * s)))
            pygame.draw.rect(surface, (96, 70, 28) if building.type == "safehouse" else (34, 50, 76), rect)
            pygame.draw.rect(surface, (60, 84, 120), rect, 1)
        for obstacle in game_map.obstacles:
            rect = pygame.Rect(int(obstacle.rect.x * s) + pad, int(obstacle.rect.y * s) + pad,
                               max(1, int(obstacle.rect.width * s)), max(1, int(obstacle.rect.height * s)))
            pygame.draw.rect(surface, (30, 42, 62), rect)
        pygame.draw.rect(surface, (60, 84, 120),
                         (pad, pad, int(game_map.width * s), int(game_map.height * s)), 1)
        return surface

    def _build_backdrop(self, font: pygame.font.Font) -> pygame.Surface:
        r = self.radius
        size = 2 * (r + 26)
        backdrop = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        pygame.draw.circle(backdrop, (5, 10, 20, 210), center, r + 10)
        pygame.draw.circle(backdrop, theme.CYAN, center, r + 10, 2)
        for letter, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0))):
            text = font.render(letter, True, theme.TEXT)
            backdrop.blit(text, text.get_rect(center=(center[0] + dx * (r + 19), center[1] + dy * (r + 19))))
        return backdrop

    def draw(self, surface: pygame.Surface, center: tuple[int, int], player_position: Vector2,
             aim: Vector2, enemies: list[Vector2], crates: list[Vector2],
             objective: Vector2 | None) -> None:
        r, s = self.radius, self.scale
        window = pygame.Rect(int(player_position.x * s), int(player_position.y * s), 2 * r, 2 * r)
        self._buffer.fill((0, 0, 0, 0))
        self._buffer.blit(self._world, (0, 0), window)

        for position in crates:
            point, clamped = project(position - player_position, s, r)
            if not clamped:
                pygame.draw.circle(self._buffer, (230, 190, 70), (int(r + point.x), int(r + point.y)), 2)
        for position in enemies:
            point, clamped = project(position - player_position, s, r)
            if not clamped:
                pygame.draw.circle(self._buffer, (225, 50, 45), (int(r + point.x), int(r + point.y)), 2)
        if objective is not None:
            point, clamped = project(objective - player_position, s, r)
            self._draw_marker(r + point.x, r + point.y, 4 if clamped else 6)

        heading = Vector2(aim) if Vector2(aim).length_squared() > 0 else Vector2(1, 0)
        heading = heading.normalize()
        side = Vector2(-heading.y, heading.x)
        middle = Vector2(r, r)
        pygame.draw.polygon(self._buffer, theme.AMBER,
                            [middle + heading * 7, middle - heading * 4 + side * 4,
                             middle - heading * 4 - side * 4])
        self._buffer.blit(self._mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        surface.blit(self._backdrop, self._backdrop.get_rect(center=center))
        surface.blit(self._buffer, (center[0] - r, center[1] - r))

    def _draw_marker(self, x: float, y: float, size: int) -> None:
        points = [(x, y - size), (x + size, y), (x, y + size), (x - size, y)]
        pygame.draw.polygon(self._buffer, theme.AMBER, points)
        pygame.draw.polygon(self._buffer, (20, 14, 4), points, 1)