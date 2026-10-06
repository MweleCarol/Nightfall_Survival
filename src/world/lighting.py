"""Night darkness overlay with soft pools of light cut out of it."""
from __future__ import annotations

import pygame

from src.core import settings
from src.world.camera import Camera


def make_light_sprite(radius: int, steps: int = 40) -> pygame.Surface:
    """A soft round gradient: alpha 255 in the centre, fading to 0 at the edge."""
    size = radius * 2
    sprite = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(steps):
        t = (i + 1) / steps                    # 0 -> 1 towards the centre
        alpha = int(255 * t * t * (3 - 2 * t))
        r = max(1, int(radius * (1 - i / steps)))
        pygame.draw.circle(sprite, (0, 0, 0, alpha), (radius, radius), r)
    return sprite


class Lighting:
    def __init__(self, width: int, height: int) -> None:
        self.overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        self.player_light = make_light_sprite(settings.PLAYER_LIGHT_RADIUS)
        self.street_light = make_light_sprite(settings.STREET_LIGHT_RADIUS)

    def render(self, surface: pygame.Surface, camera: Camera, darkness: float,
               street_lights: list[tuple[int, int]], player_pos: pygame.Vector2) -> None:
        alpha = int(darkness * settings.NIGHT_MAX_DARKNESS)
        if alpha <= 0:
            return                              # full daylight: skip all the work

        self.overlay.fill((*settings.NIGHT_TINT, alpha))

        # SUBTRACTING a light sprite's alpha from the overlay makes a hole in the dark.
        radius = settings.STREET_LIGHT_RADIUS
        view = camera.view_rect().inflate(2 * radius, 2 * radius)
        for pos in street_lights:
            if view.collidepoint(pos):
                sx, sy = camera.world_to_screen(pygame.Vector2(pos))
                self.overlay.blit(self.street_light, (sx - radius, sy - radius),
                                  special_flags=pygame.BLEND_RGBA_SUB)

        radius = settings.PLAYER_LIGHT_RADIUS
        px, py = camera.world_to_screen(player_pos)
        self.overlay.blit(self.player_light, (px - radius, py - radius),
                          special_flags=pygame.BLEND_RGBA_SUB)

        surface.blit(self.overlay, (0, 0))