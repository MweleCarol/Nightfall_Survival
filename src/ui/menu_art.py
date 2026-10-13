"""Procedural artwork for the main menu, drawn in code in the design's palette.

If real art exists (assets/images/ui/menu_background.png and logo.png) the menu uses that instead.
"""
from __future__ import annotations

import random

import pygame

from src.services.asset_manager import AssetManager
from src.ui import theme
from src.ui.widgets import render_tracked

SKY_STOPS = [
    (0.00, (5, 8, 18)),
    (0.45, (14, 26, 48)),
    (0.62, (46, 36, 44)),
    (0.70, (18, 24, 40)),
    (1.00, (6, 9, 16)),
]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _gradient(surface: pygame.Surface, stops: list[tuple[float, tuple[int, int, int]]]) -> None:
    width, height = surface.get_size()
    for y in range(height):
        t = y / height
        color = stops[-1][1]
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                color = _lerp(c0, c1, (t - t0) / (t1 - t0))
                break
        pygame.draw.line(surface, color, (0, y), (width, y))


def _add_glow(surface: pygame.Surface, center: tuple[int, int], radius: int,
              color: tuple[int, int, int]) -> None:
    """A soft light, added to whatever is underneath (fires, the moon)."""
    sprite = pygame.Surface((radius * 2, radius * 2))
    for i in range(radius, 0, -3):
        strength = (1 - i / radius) ** 2                      # brighter towards the centre
        pygame.draw.circle(sprite, tuple(int(c * strength) for c in color), (radius, radius), i)
    surface.blit(sprite, (center[0] - radius, center[1] - radius), special_flags=pygame.BLEND_RGB_ADD)


def _skyline(surface: pygame.Surface, rng: random.Random, base_y: int,
             color: tuple[int, int, int], window_chance: float, min_h: float, max_h: float,
             min_w: int, max_w: int, window_color: tuple[int, int, int]) -> None:
    width, height = surface.get_size()
    x = -rng.randint(0, 20)
    while x < width:
        bw = rng.randint(max(4, min_w), max(5, max_w))
        bh = int(height * rng.uniform(min_h, max_h))
        if rng.random() < 0.12:
            bh = int(bh * 1.7)                                 # the occasional tower
        top = base_y - bh
        pygame.draw.rect(surface, color, (x, top, bw, bh + 4))
        for wx in range(x + 4, x + bw - 5, 8):
            for wy in range(top + 6, base_y - 4, 11):
                if rng.random() < window_chance:
                    pygame.draw.rect(surface, window_color, (wx, wy, 3, 4))
        x += bw + rng.randint(0, 5)


def _ground(surface: pygame.Surface, rng: random.Random) -> None:
    width, height = surface.get_size()
    base = int(height * 0.88)
    points = [(0, height)]
    x = 0
    while x <= width:
        points.append((x, base + rng.randint(-int(height * 0.03), int(height * 0.03))
                       + int(height * 0.04 * x / width)))
        x += max(8, int(width * 0.03))
    points.append((width, height))
    pygame.draw.polygon(surface, (6, 9, 15), points)
    for _ in range(26):                                        # broken slabs of concrete
        bx = rng.randint(0, width)
        by = rng.randint(int(height * 0.86), int(height * 0.97))
        bw = rng.randint(10, max(11, int(width * 0.05)))
        bh = rng.randint(6, max(7, int(height * 0.04)))
        pygame.draw.polygon(surface, (4, 6, 11), [(bx, by), (bx + bw, by - rng.randint(2, 8)),
                                                  (bx + bw - 3, by + bh), (bx + 2, by + bh)])


def _survivor(surface: pygame.Surface, x: int, ground_y: int, height: int) -> None:
    """A hooded silhouette with a backpack and a rifle, looking out over the city."""
    s = height / 720.0
    color = (7, 9, 14)

    def p(dx: float, dy: float) -> tuple[int, int]:
        return (x + int(dx * s), ground_y + int(dy * s))

    pygame.draw.polygon(surface, color, [p(-26, 0), p(-8, 0), p(-6, -120), p(-30, -120)])
    pygame.draw.polygon(surface, color, [p(6, 0), p(26, 0), p(30, -120), p(8, -120)])
    pygame.draw.polygon(surface, color, [p(-34, -120), p(34, -120), p(40, -210), p(30, -250),
                                         p(-30, -250), p(-42, -210)])
    pygame.draw.polygon(surface, color, [p(-62, -230), p(-34, -236), p(-34, -130), p(-60, -136)])
    pygame.draw.circle(surface, color, p(0, -272), max(2, int(24 * s)))
    pygame.draw.polygon(surface, color, [p(-26, -262), p(0, -312), p(26, -262), p(30, -240), p(-30, -240)])
    pygame.draw.line(surface, color, p(30, -200), p(70, -70), max(2, int(7 * s)))
    pygame.draw.line(surface, (40, 58, 88), p(34, -120), p(40, -210), max(1, int(2 * s)))   # moonlight rim


def fire_points(width: int, height: int) -> list[tuple[int, int]]:
    """Where the city fires burn (for the glow, the river reflections and the embers)."""
    spots = [(0.35, 0.70), (0.48, 0.74), (0.62, 0.71), (0.56, 0.82), (0.72, 0.80)]
    return [(int(width * fx), int(height * fy)) for fx, fy in spots]


def build_menu_background(width: int, height: int, seed: int = 7) -> pygame.Surface:
    """The night city scene. Built once, then drawn every frame as a plain image."""
    rng = random.Random(seed)
    surface = pygame.Surface((width, height))
    _gradient(surface, SKY_STOPS)

    fires = fire_points(width, height)
    for point in fires:
        _add_glow(surface, point, max(10, int(height * 0.22)), (150, 70, 20))

    moon = (int(width * 0.745), int(height * 0.16))
    _add_glow(surface, moon, max(10, int(height * 0.20)), (50, 70, 110))
    pygame.draw.circle(surface, theme.MOON, moon, max(3, int(height * 0.045)))
    pygame.draw.circle(surface, (150, 175, 210),
                       (moon[0] + int(height * 0.012), moon[1] - int(height * 0.008)),
                       max(1, int(height * 0.012)))

    _skyline(surface, rng, int(height * 0.66), (14, 22, 38), 0.05, 0.12, 0.30,
             int(width * 0.025), int(width * 0.05), (120, 100, 70))
    _skyline(surface, rng, int(height * 0.71), (9, 14, 26), 0.09, 0.08, 0.24,
             int(width * 0.02), int(width * 0.045), (190, 140, 70))

    river_top, river_bottom = int(height * 0.71), int(height * 0.84)
    for y in range(river_top, river_bottom):
        t = (y - river_top) / max(1, river_bottom - river_top)
        pygame.draw.line(surface, _lerp((12, 20, 34), (6, 10, 18), t), (0, y), (width, y))
    for fx, _fy in fires:                                      # firelight on the water
        for _ in range(6):
            sx = fx + rng.randint(-8, 8)
            pygame.draw.line(surface, (110, 55, 22), (sx, river_top + rng.randint(0, 10)),
                             (sx, river_top + rng.randint(20, max(21, int(height * 0.1)))), 2)

    _ground(surface, rng)
    _survivor(surface, int(width * 0.79), int(height * 0.90), height)
    return surface


def cover_scale(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Scale an image to fill `size` completely, cropping the overflow (like CSS 'cover')."""
    iw, ih = image.get_size()
    scale = max(size[0] / iw, size[1] / ih)
    scaled = pygame.transform.smoothscale(image, (max(1, int(iw * scale)), max(1, int(ih * scale))))
    result = pygame.Surface(size)
    left, top = (scaled.get_width() - size[0]) // 2, (scaled.get_height() - size[1]) // 2
    result.blit(scaled, (0, 0), pygame.Rect(left, top, size[0], size[1]))
    return result


def build_logo(assets: AssetManager) -> pygame.Surface:
    """The NIGHTFALL / SURVIVAL / LAST STAND logo: a PNG if provided, otherwise drawn from text."""
    image = assets.image("ui/logo.png")
    if image is not None:
        scale = min(1.0, 600 / image.get_width())
        return pygame.transform.smoothscale(
            image, (int(image.get_width() * scale), int(image.get_height() * scale)))

    survival_font = assets.font(78, bold=True)
    night = render_tracked("NIGHTFALL", assets.font(86, bold=True), (226, 234, 247), 4)
    survival = render_tracked("SURVIVAL", survival_font, theme.RED, 8)
    glow = render_tracked("SURVIVAL", survival_font, (120, 10, 8), 8)
    last = render_tracked("LAST STAND", assets.font(20), theme.TEXT, 14)

    width = max(night.get_width(), survival.get_width(), last.get_width() + 140) + 24
    height = night.get_height() + survival.get_height() + last.get_height() + 24
    logo = pygame.Surface((width, height), pygame.SRCALPHA)

    logo.blit(night, (0, 0))
    y = night.get_height() - 8
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):   # a dark-red halo
        logo.blit(glow, (14 + dx, y + dy))
    logo.blit(survival, (14, y))

    y += survival.get_height() + 6
    logo.blit(last, (70, y))
    mid = y + last.get_height() // 2
    pygame.draw.line(logo, theme.MUTED, (0, mid), (56, mid), 2)
    pygame.draw.line(logo, theme.MUTED, (70 + last.get_width() + 14, mid),
                     (70 + last.get_width() + 70, mid), 2)
    return logo