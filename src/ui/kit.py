"""Shared pieces for the HUD and the hub screens: cut-corner panels, key caps, bars, icons."""
from __future__ import annotations

import re

import pygame

from src.ui import theme

CUT = 10
_PROMPT = re.compile(r"^Press ([A-Za-z0-9]+) (.*)$")
_ICON_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}


def cut_panel(width: int, height: int, border: tuple[int, int, int] = theme.CYAN,
              fill: tuple[int, int, int, int] = (9, 16, 28, 205), cut: int = CUT,
              border_width: int = 2) -> pygame.Surface:
    """A translucent panel with chamfered top-left and bottom-right corners, built once and reused."""
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    points = [(cut, 0), (width - 1, 0), (width - 1, height - 1 - cut),
              (width - 1 - cut, height - 1), (0, height - 1), (0, cut)]
    pygame.draw.polygon(panel, fill, points)
    pygame.draw.polygon(panel, border, points, border_width)
    return panel


def draw_bar(surface: pygame.Surface, rect: pygame.Rect, fraction: float,
             color: tuple[int, int, int], back: tuple[int, int, int] = (12, 20, 34),
             border: tuple[int, int, int] = theme.BORDER) -> None:
    fraction = max(0.0, min(1.0, fraction))
    pygame.draw.rect(surface, back, rect)
    fill = int(rect.width * fraction)
    if fill > 0:
        pygame.draw.rect(surface, color, (rect.x, rect.y, fill, rect.height))
        light = tuple(min(255, c + 70) for c in color)
        pygame.draw.line(surface, light, (rect.x, rect.y), (rect.x + fill - 1, rect.y))
    pygame.draw.rect(surface, border, rect, 1)


def draw_keycap(surface: pygame.Surface, font: pygame.font.Font, key: str,
                topleft: tuple[int, int]) -> pygame.Rect:
    """A small keyboard key with a letter. Returns its rectangle."""
    text = font.render(key, True, theme.TEXT)
    rect = pygame.Rect(topleft, (max(22, text.get_width() + 12), text.get_height() + 6))
    pygame.draw.rect(surface, theme.PANEL_DARK, rect, border_radius=3)
    pygame.draw.rect(surface, theme.CYAN_BRIGHT, rect, 1, border_radius=3)
    surface.blit(text, text.get_rect(center=rect.center))
    return rect


def draw_checkbox(surface: pygame.Surface, rect: pygame.Rect, checked: bool) -> None:
    pygame.draw.rect(surface, theme.PANEL_DARK, rect)
    pygame.draw.rect(surface, theme.CYAN if checked else theme.MUTED, rect, 1)
    if checked:
        points = [(rect.x + 3, rect.centery), (rect.x + rect.width * 0.4, rect.bottom - 4),
                  (rect.right - 3, rect.y + 3)]
        pygame.draw.lines(surface, theme.CYAN_BRIGHT, False, points, 2)


def fit_text(text: str, max_chars: int) -> str:
    """Collapse whitespace and shorten with '...' if the text is too long."""
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def parse_prompt(prompt: str) -> tuple[str | None, str]:
    """Split 'Press E to search' into ('E', 'to search') so the key can be drawn as a key cap."""
    match = _PROMPT.match(prompt)
    if match:
        return match.group(1).upper(), match.group(2)
    return None, prompt


def draw_hud_icon(surface: pygame.Surface, name: str, center: tuple[float, float],
                  color: tuple[int, int, int], size: int = 16) -> None:
    """Small vector icons for the HUD. Unknown names draw nothing."""
    cx, cy = center
    r = size / 2
    dark = (10, 14, 22)

    def box(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))

    if name == "heart":
        pygame.draw.circle(surface, color, (cx - r * 0.5, cy - r * 0.2), max(1, int(r * 0.55)))
        pygame.draw.circle(surface, color, (cx + r * 0.5, cy - r * 0.2), max(1, int(r * 0.55)))
        pygame.draw.polygon(surface, color, [(cx - r * 1.02, cy - r * 0.05),
                                             (cx + r * 1.02, cy - r * 0.05), (cx, cy + r)])
    elif name == "bolt":
        pygame.draw.polygon(surface, color, [(cx + 1, cy - r), (cx - r * 0.6, cy + r * 0.1),
                                             (cx, cy + r * 0.1), (cx - 1, cy + r),
                                             (cx + r * 0.6, cy - r * 0.1), (cx, cy - r * 0.1)])
    elif name == "skull":
        pygame.draw.circle(surface, color, (cx, cy - r * 0.15), max(1, int(r * 0.75)))
        pygame.draw.rect(surface, color, box(cx - r * 0.4, cy + r * 0.35, r * 0.8, r * 0.55))
        for side in (-1, 1):
            pygame.draw.circle(surface, dark, (cx + side * r * 0.3, cy - r * 0.15), max(1, int(r * 0.2)))
    elif name == "warning":
        points = [(cx, cy - r), (cx + r, cy + r * 0.85), (cx - r, cy + r * 0.85)]
        pygame.draw.polygon(surface, color, points, 2)
        pygame.draw.line(surface, color, (cx, cy - r * 0.3), (cx, cy + r * 0.2), 2)
        pygame.draw.circle(surface, color, (cx, cy + r * 0.55), 1)
    elif name == "diamond":
        points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surface, color, points, 2)
        pygame.draw.polygon(surface, color, [(cx, cy - r * 0.4), (cx + r * 0.4, cy),
                                             (cx, cy + r * 0.4), (cx - r * 0.4, cy)])
    elif name == "radio":
        pygame.draw.rect(surface, color, box(cx - r * 0.55, cy - r * 0.5, r * 1.1, r * 1.5), 2)
        pygame.draw.line(surface, color, (cx + r * 0.25, cy - r * 0.5), (cx + r * 0.25, cy - r), 2)
        pygame.draw.circle(surface, color, (cx, cy + r * 0.25), max(1, int(r * 0.3)), 2)
    elif name == "sun":
        pygame.draw.circle(surface, color, (cx, cy), max(1, int(r * 0.5)))
        for step in range(8):
            ray = pygame.Vector2(1, 0).rotate(step * 45)
            pygame.draw.line(surface, color, (cx, cy) + ray * (r * 0.7), (cx, cy) + ray * r, 2)
    elif name == "moon":
        pygame.draw.circle(surface, theme.MOON, (cx, cy), max(1, int(r * 0.8)))
        pygame.draw.circle(surface, theme.PANEL_DARK, (cx + r * 0.4, cy - r * 0.25), max(1, int(r * 0.7)))
    elif name == "gun":
        pygame.draw.rect(surface, color, box(cx - r, cy - r * 0.45, r * 1.7, r * 0.5))
        pygame.draw.polygon(surface, color, [(cx - r * 0.2, cy + r * 0.05), (cx + r * 0.35, cy + r * 0.05),
                                             (cx + r * 0.2, cy + r * 0.95), (cx - r * 0.3, cy + r * 0.95)])
    elif name == "mag":
        for offset in (-1, 0, 1):
            pygame.draw.rect(surface, color, box(cx + offset * r * 0.55 - 2, cy - r * 0.6, 4, r * 1.4))


def draw_item_icon(surface: pygame.Surface, assets, item_id: str, item_type: str,
                   rect: pygame.Rect) -> None:
    """An item's icon: assets/images/ui/icons/<item_id>.png if it exists, else a drawn symbol."""
    image = assets.image(f"ui/icons/{item_id}.png") if assets is not None else None
    if image is not None:
        key = (item_id, rect.width, rect.height)
        scaled = _ICON_CACHE.get(key)
        if scaled is None:
            scaled = pygame.transform.smoothscale(image, rect.size)
            _ICON_CACHE[key] = scaled
        surface.blit(scaled, rect)
        return

    cx, cy = rect.center
    r = max(4, min(rect.size) // 2)
    if item_id == "medkit":
        body = pygame.Rect(0, 0, r * 2, int(r * 1.5))
        body.center = (cx, cy + 2)
        pygame.draw.rect(surface, (200, 50, 50), body, border_radius=4)
        pygame.draw.rect(surface, (255, 255, 255), (cx - 2, body.y + 4, 4, body.height - 8))
        pygame.draw.rect(surface, (255, 255, 255), (cx - r // 2, cy + 2 - 2, r, 4))
    elif item_id == "bandage":
        roll = pygame.Rect(0, 0, r * 2, int(r * 1.2))
        roll.center = (cx, cy)
        pygame.draw.rect(surface, (225, 225, 215), roll, border_radius=r // 2)
        pygame.draw.line(surface, (190, 60, 60), (roll.x + 4, cy), (roll.right - 4, cy), 2)
    elif item_id.startswith("ammo"):
        for offset in (-1, 0, 1):
            x = cx + offset * (r // 2 + 2)
            pygame.draw.rect(surface, (214, 170, 70), (x - 3, cy - r // 2, 6, r))
            pygame.draw.circle(surface, (170, 130, 50), (x, cy - r // 2), 3)
    else:
        colors = {"resource": (150, 160, 175), "consumable": (220, 70, 70),
                  "quest": (110, 190, 255), "ammo": (214, 170, 70)}
        color = colors.get(item_type, theme.MUTED)
        body = pygame.Rect(0, 0, r * 2, r * 2)
        body.center = (cx, cy)
        pygame.draw.rect(surface, color, body, border_radius=4)
        pygame.draw.rect(surface, tuple(min(255, c + 60) for c in color), body.inflate(-r, -r),
                         border_radius=3)