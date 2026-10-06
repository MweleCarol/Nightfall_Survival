"""Minimal HUD: health and stamina bars."""
from __future__ import annotations

import pygame

from src.core import settings
from src.player.stats import Stats


class HUD:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("arial", 18, bold=True)
        self.big_font = pygame.font.SysFont("arial", 64, bold=True)

    def draw(self, surface: pygame.Surface, stats: Stats, fps: float) -> None:
        self._bar(surface, (20, 20), stats.health, stats.max_health,
                  settings.COLOR_ACCENT, f"HP {stats.health}/{stats.max_health}")
        self._bar(surface, (20, 52), stats.stamina, stats.max_stamina,
                  settings.COLOR_AMBER, f"STA {stats.stamina:.0f}/{stats.max_stamina:.0f}")

        fps_text = self.font.render(f"FPS {fps:.0f}", True, settings.COLOR_MUTED)
        surface.blit(fps_text, (settings.SCREEN_WIDTH - 90, 20))

        hint = self.font.render(
            "WASD move | SHIFT sprint | Mouse aim | H/J debug damage/heal | ESC menu",
            True, settings.COLOR_MUTED)
        surface.blit(hint, (20, settings.SCREEN_HEIGHT - 32))

        if stats.is_dead:
            msg = self.big_font.render("YOU DIED", True, settings.COLOR_ACCENT)
            surface.blit(msg, msg.get_rect(center=(settings.SCREEN_WIDTH // 2,
                                                   settings.SCREEN_HEIGHT // 2)))

    def _bar(self, surface: pygame.Surface, pos: tuple[int, int],
             value: float, maximum: float, color: tuple[int, int, int],
             label: str) -> None:
        width, height = 260, 22
        x, y = pos
        pygame.draw.rect(surface, (20, 26, 40), (x, y, width, height))
        fill = int(width * max(0.0, min(1.0, value / maximum)))
        pygame.draw.rect(surface, color, (x, y, fill, height))
        pygame.draw.rect(surface, (70, 88, 120), (x, y, width, height), 2)
        text = self.font.render(label, True, settings.COLOR_TEXT)
        surface.blit(text, (x + 8, y + 1))