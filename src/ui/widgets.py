"""Small shared UI helpers. Full button widgets and polish arrive in Milestone 9."""
from __future__ import annotations

import pygame

from src.core import settings


class SelectionList:
    """Tracks which row of a vertical list is highlighted."""

    def __init__(self) -> None:
        self.selected = 0

    def reset(self) -> None:
        self.selected = 0

    def move(self, delta: int, count: int) -> None:
        if count <= 0:
            self.selected = 0
        else:
            self.selected = max(0, min(self.selected + delta, count - 1))


def make_dim() -> pygame.Surface:
    """A translucent black layer drawn behind overlay panels."""
    dim = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 170))
    return dim


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Split text into lines that fit inside max_width pixels."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, title: str,
               title_font: pygame.font.Font, right_text: str | None = None,
               right_font: pygame.font.Font | None = None) -> None:
    pygame.draw.rect(surface, (12, 18, 30), rect)
    pygame.draw.rect(surface, (70, 88, 120), rect, 2)
    surface.blit(title_font.render(title, True, settings.COLOR_TEXT), (rect.x + 24, rect.y + 16))
    if right_text and right_font:
        text = right_font.render(right_text, True, settings.COLOR_MUTED)
        surface.blit(text, text.get_rect(topright=(rect.right - 24, rect.y + 22)))


def draw_row_highlight(surface: pygame.Surface, rect: pygame.Rect, selected: bool) -> None:
    if selected:
        pygame.draw.rect(surface, (30, 44, 70), rect)
        pygame.draw.rect(surface, settings.COLOR_AMBER, rect, 2)



# ===================================================================
# Menu widgets (Milestone 9): slanted buttons, icons, tracked text
# ===================================================================
from src.ui import theme as _theme  # noqa: E402


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def render_tracked(text: str, font: pygame.font.Font, color: tuple[int, int, int],
                   tracking: int = 0) -> pygame.Surface:
    """Render text with extra space between the letters (pygame has no built-in tracking)."""
    glyphs = [font.render(char, True, color) for char in text]
    width = sum(g.get_width() for g in glyphs) + tracking * max(0, len(glyphs) - 1)
    height = max((g.get_height() for g in glyphs), default=font.get_height())
    surface = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
    x = 0
    for glyph in glyphs:
        surface.blit(glyph, (x, 0))
        x += glyph.get_width() + tracking
    return surface


def draw_icon(surface: pygame.Surface, name: str, center: tuple[int, int],
              color: tuple[int, int, int], size: int = 18) -> None:
    """Small vector icons for the menu buttons."""
    cx, cy = center
    r = size / 2

    def box(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(int(x), int(y), int(w), int(h))

    if name == "play":
        pygame.draw.polygon(surface, color, [(cx - r * 0.5, cy - r), (cx - r * 0.5, cy + r), (cx + r, cy)])
    elif name == "loop":
        ring = box(cx - r, cy - r, size, size)
        pygame.draw.arc(surface, color, ring, 0.5, 5.8, 2)
        pygame.draw.polygon(surface, color, [(cx + r - 1, cy - r * 0.2), (cx + r + 4, cy - r * 0.9),
                                             (cx + r - 6, cy - r * 0.9)])
    elif name == "gear":
        pygame.draw.circle(surface, color, center, int(r * 0.62), 3)
        for step in range(8):
            d = pygame.Vector2(1, 0).rotate(step * 45)
            pygame.draw.line(surface, color, (cx + d.x * r * 0.7, cy + d.y * r * 0.7),
                             (cx + d.x * r * 1.05, cy + d.y * r * 1.05), 3)
    elif name == "trophy":
        pygame.draw.polygon(surface, color, [(cx - r, cy - r), (cx + r, cy - r),
                                             (cx + r * 0.55, cy + r * 0.2), (cx - r * 0.55, cy + r * 0.2)], 2)
        pygame.draw.line(surface, color, (cx, cy + r * 0.2), (cx, cy + r * 0.75), 2)
        pygame.draw.line(surface, color, (cx - r * 0.55, cy + r), (cx + r * 0.55, cy + r), 3)
    elif name == "door":
        pygame.draw.rect(surface, color, box(cx - r * 0.55, cy - r, r * 1.1, r * 2), 2)
        pygame.draw.circle(surface, color, (int(cx + r * 0.2), int(cy)), 2)
        pygame.draw.line(surface, color, (cx + r * 0.55, cy), (cx + r * 1.15, cy), 2)
    elif name == "book":
        pygame.draw.rect(surface, color, box(cx - r, cy - r * 0.8, r * 2, r * 1.6), 2)
        pygame.draw.line(surface, color, (cx, cy - r * 0.8), (cx, cy + r * 0.8), 2)
    elif name == "disk":
        pygame.draw.rect(surface, color, box(cx - r, cy - r, r * 2, r * 2), 2)
        pygame.draw.rect(surface, color, box(cx - r * 0.5, cy - r, r, r * 0.7), 2)
        pygame.draw.rect(surface, color, box(cx - r * 0.55, cy + r * 0.1, r * 1.1, r * 0.8), 2)


class MenuModel:
    """Which entry of a menu is highlighted. Disabled entries are skipped. Pure logic."""

    def __init__(self, enabled: list[bool]) -> None:
        self.enabled = list(enabled)
        self.selected = next((i for i, on in enumerate(self.enabled) if on), 0)
        self.hover: int | None = None        # the entry under the mouse (may be disabled)

    def move(self, step: int) -> None:
        count = len(self.enabled)
        if count == 0 or not any(self.enabled):
            return
        index = self.selected
        for _ in range(count):
            index = (index + step) % count
            if self.enabled[index]:
                self.selected = index
                return

    def select(self, index: int) -> bool:
        """Highlight an entry. Returns False for disabled or unknown entries."""
        if 0 <= index < len(self.enabled) and self.enabled[index]:
            self.selected = index
            return True
        return False

    def set_enabled(self, index: int, value: bool) -> None:
        if 0 <= index < len(self.enabled):
            self.enabled[index] = value


class MenuButton:
    """A slanted button: idle panel, amber glow when highlighted, greyed out when disabled."""

    SLANT = 18
    DIVIDER = 46

    def __init__(self, label: str, icon: str, rect: pygame.Rect,
                 font: pygame.font.Font, enabled: bool = True) -> None:
        self.label = label
        self.icon = icon
        self.rect = pygame.Rect(rect)
        self.enabled = enabled
        self.glow = 0.0                                  # 0 = idle, 1 = fully highlighted
        self._idle = self._make_panel(lit=False)         # built once, reused every frame
        self._lit = self._make_panel(lit=True)
        self._text_idle = font.render(label, True, _theme.TEXT)
        self._text_lit = font.render(label, True, _theme.AMBER)
        self._text_off = font.render(label, True, _theme.DISABLED)

    def _make_panel(self, lit: bool) -> pygame.Surface:
        w, h = self.rect.size
        panel = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
        points = [(2, 2), (w + 2, 2), (w + 2 - self.SLANT, h + 2), (2, h + 2)]
        fill = (46, 32, 10, 225) if lit else (15, 26, 43, 190)
        edge = _theme.AMBER if lit else _theme.BORDER
        pygame.draw.polygon(panel, fill, points)
        pygame.draw.polygon(panel, edge, points, 2)
        pygame.draw.line(panel, edge, (2 + self.DIVIDER, 10), (2 + self.DIVIDER, h - 6), 1)
        return panel

    def contains(self, position: tuple[int, int]) -> bool:
        return self.rect.collidepoint(position)

    def update(self, dt: float, highlighted: bool) -> None:
        target = 1.0 if (highlighted and self.enabled) else 0.0
        step = 8.0 * dt
        if self.glow < target:
            self.glow = min(target, self.glow + step)
        else:
            self.glow = max(target, self.glow - step)

    def draw(self, surface: pygame.Surface) -> None:
        slide = int(8 * self.glow)                       # the highlighted button slides right
        x, y = self.rect.x + slide, self.rect.y
        surface.blit(self._idle, (x - 2, y - 2))
        if self.glow > 0.01:
            self._lit.set_alpha(int(255 * self.glow))
            surface.blit(self._lit, (x - 2, y - 2))

        text_y = y + (self.rect.height - self._text_idle.get_height()) // 2
        if not self.enabled:
            surface.blit(self._text_off, (x + 62, text_y))
            icon_color = _theme.DISABLED
        else:
            surface.blit(self._text_idle, (x + 62, text_y))
            if self.glow > 0.01:
                self._text_lit.set_alpha(int(255 * self.glow))
                surface.blit(self._text_lit, (x + 62, text_y))
            icon_color = _mix(_theme.ICON, _theme.AMBER, self.glow)
        draw_icon(surface, self.icon, (x + 2 + self.DIVIDER // 2, y + self.rect.height // 2),
                  icon_color, 20)


def handle_menu_input(event: pygame.event.Event, buttons: list[MenuButton],
                      model: MenuModel) -> int | None:
    """Keyboard and mouse navigation shared by every button menu.

    Returns the index of an entry when it was activated (Enter, Space or a click).
    """
    if event.type == pygame.MOUSEMOTION:
        model.hover = next((i for i, b in enumerate(buttons) if b.contains(event.pos)), None)
        if model.hover is not None:
            model.select(model.hover)                    # ignored for disabled entries
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for index, button in enumerate(buttons):
            if button.contains(event.pos) and model.select(index):
                return index
    elif event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_UP, pygame.K_w):
            model.move(-1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            model.move(1)
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if model.enabled and model.enabled[model.selected]:
                return model.selected
    return None