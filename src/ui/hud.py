"""HUD: vitals, time of day, prompts and notifications, in the style of the menu."""
from __future__ import annotations

import math

import pygame

from src.core import settings
from src.player.stats import Stats
from src.ui import theme
from src.ui.widgets import render_tracked
from src.world.day_night import DayNightCycle

SLANT = 14
PANEL_FILL = (12, 20, 34)


def make_panel(width: int, height: int, border: tuple[int, int, int] = theme.BORDER) -> pygame.Surface:
    """A translucent panel with a slanted right edge, built once and reused."""
    panel = pygame.Surface((width + 4, height + 4), pygame.SRCALPHA)
    points = [(2, 2), (width + 2, 2), (width + 2 - SLANT, height + 2), (2, height + 2)]
    pygame.draw.polygon(panel, (*PANEL_FILL, 185), points)
    pygame.draw.polygon(panel, border, points, 2)
    return panel


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


class HUD:
    def __init__(self, assets=None) -> None:
        self.assets = assets
        self.font = self._font(18)
        self.small_font = self._font(15)
        self.tiny_font = self._font(12)
        self.label_font = self._font(20)
        self.clock_font = self._font(28)
        self.notice_font = self._font(44)
        self.big_font = self._font(64)
        self._vitals_panel = make_panel(300, 70)
        self._clock_panel = make_panel(222, 74)
        self._notices: list[list] = []          # [text, seconds_remaining]

    def _font(self, size: int) -> pygame.font.Font:
        if self.assets is not None:
            return self.assets.font(size, bold=True)
        return pygame.font.SysFont("arial", size, bold=True)

    def notify(self, text: str, duration: float = 3.0) -> None:
        self._notices.append([text, duration])

    def update(self, dt: float) -> None:
        for notice in self._notices:
            notice[1] -= dt
        self._notices = [n for n in self._notices if n[1] > 0]

    def draw(self, surface: pygame.Surface, stats: Stats, fps: float,
             cycle: DayNightCycle, prompt: str | None, in_safe_zone: bool) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        self._draw_vitals(surface, stats)
        if in_safe_zone:
            surface.blit(self.small_font.render("SAFE ZONE", True, settings.COLOR_SAFE), (20, 88))
        self._draw_clock(surface, cycle, fps)

        if prompt:
            text = self.font.render(prompt, True, theme.TEXT)
            box = text.get_rect(center=(w // 2, h - 90)).inflate(40, 20)
            pygame.draw.rect(surface, PANEL_FILL, box)
            pygame.draw.rect(surface, theme.AMBER, box, 2)
            surface.blit(text, text.get_rect(center=box.center))

        for i, (message, remaining) in enumerate(self._notices):
            alpha = int(255 * min(1.0, remaining / 0.8))               # fade out at the end
            shadow = render_tracked(message, self.notice_font, (0, 0, 0), 2)
            text = render_tracked(message, self.notice_font, theme.TEXT, 2)
            shadow.set_alpha(int(alpha * 0.7))
            text.set_alpha(alpha)
            center = (w // 2, 130 + i * 56)
            surface.blit(shadow, shadow.get_rect(center=(center[0] + 2, center[1] + 2)))
            surface.blit(text, text.get_rect(center=center))

        hint = self.tiny_font.render(
            "WASD move | SHIFT sprint | E interact | M journal | K skills | TAB inventory | ESC pause",
            True, theme.MUTED)
        surface.blit(hint, (20, h - 28))

        if stats.is_dead:
            msg = self.big_font.render("YOU DIED", True, theme.RED)
            surface.blit(msg, msg.get_rect(center=(w // 2, h // 2)))

    # ---- parts ----
    def _draw_vitals(self, surface: pygame.Surface, stats: Stats) -> None:
        surface.blit(self._vitals_panel, (10, 10))
        low = stats.health / stats.max_health < 0.3
        health_color = theme.RED
        if low:                                                          # pulses when nearly dead
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
            health_color = _mix(theme.RED, (255, 130, 110), pulse)
        self._bar(surface, pygame.Rect(26, 22, 252, 20), stats.health, stats.max_health,
                  health_color, f"HP  {stats.health}/{stats.max_health}", self.font)
        self._bar(surface, pygame.Rect(26, 50, 252, 14), stats.stamina, stats.max_stamina,
                  theme.AMBER, f"STA  {stats.stamina:.0f}", self.tiny_font)

    def _bar(self, surface: pygame.Surface, rect: pygame.Rect, value: float, maximum: float,
             color: tuple[int, int, int], label: str, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, (14, 20, 32), rect)
        fill = int(rect.width * max(0.0, min(1.0, value / maximum)))
        if fill > 0:
            pygame.draw.rect(surface, color, (rect.x, rect.y, fill, rect.height))
            pygame.draw.line(surface, _mix(color, (255, 255, 255), 0.35),
                             (rect.x, rect.y), (rect.x + fill - 1, rect.y))     # a highlight on top
        pygame.draw.rect(surface, theme.BORDER, rect, 1)
        text = font.render(label, True, theme.TEXT)
        surface.blit(text, (rect.x + 8, rect.y + (rect.height - text.get_height()) // 2))

    def _draw_clock(self, surface: pygame.Surface, cycle: DayNightCycle, fps: float) -> None:
        w = settings.SCREEN_WIDTH
        surface.blit(self._clock_panel, (w - 234, 10))
        color = theme.AMBER if cycle.is_day else (150, 180, 235)
        icon = (w - 212, 47)
        if cycle.is_day:                                                  # a sun
            pygame.draw.circle(surface, color, icon, 8)
            for step in range(8):
                ray = pygame.Vector2(1, 0).rotate(step * 45)
                pygame.draw.line(surface, color, icon + ray * 11, icon + ray * 15, 2)
        else:                                                              # a crescent moon
            pygame.draw.circle(surface, theme.MOON, icon, 10)
            pygame.draw.circle(surface, PANEL_FILL, (icon[0] + 5, icon[1] - 3), 9)
        surface.blit(self.label_font.render(cycle.label, True, color), (w - 190, 18))
        surface.blit(self.clock_font.render(cycle.clock_text(), True, theme.TEXT), (w - 190, 40))
        fps_text = self.tiny_font.render(f"{fps:.0f} FPS", True, theme.MUTED)
        surface.blit(fps_text, fps_text.get_rect(topright=(w - 36, 20)))