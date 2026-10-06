"""HUD: bars, time of day, prompts and notifications (temporary styling)."""
from __future__ import annotations

import pygame

from src.core import settings
from src.player.stats import Stats
from src.world.day_night import DayNightCycle


class HUD:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("arial", 18, bold=True)
        self.clock_font = pygame.font.SysFont("arial", 30, bold=True)
        self.notice_font = pygame.font.SysFont("arial", 44, bold=True)
        self.big_font = pygame.font.SysFont("arial", 64, bold=True)
        self._notices: list[list] = []          # [text, seconds_remaining]

    def notify(self, text: str, duration: float = 3.0) -> None:
        self._notices.append([text, duration])

    def update(self, dt: float) -> None:
        for notice in self._notices:
            notice[1] -= dt
        self._notices = [n for n in self._notices if n[1] > 0]

    def draw(self, surface: pygame.Surface, stats: Stats, fps: float,
             cycle: DayNightCycle, prompt: str | None, in_safe_zone: bool) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

        self._bar(surface, (20, 20), stats.health, stats.max_health,
                  settings.COLOR_ACCENT, f"HP {stats.health}/{stats.max_health}")
        self._bar(surface, (20, 52), stats.stamina, stats.max_stamina,
                  settings.COLOR_AMBER, f"STA {stats.stamina:.0f}/{stats.max_stamina:.0f}")
        if in_safe_zone:
            safe = self.font.render("SAFE ZONE", True, settings.COLOR_SAFE)
            surface.blit(safe, (20, 84))

        # Time of day (top right)
        colour = settings.COLOR_AMBER if cycle.is_day else settings.COLOR_NIGHT
        label = self.clock_font.render(cycle.label, True, colour)
        clock = self.clock_font.render(cycle.clock_text(), True, settings.COLOR_TEXT)
        surface.blit(label, label.get_rect(topright=(w - 20, 16)))
        surface.blit(clock, clock.get_rect(topright=(w - 20, 50)))
        fps_text = self.font.render(f"FPS {fps:.0f}", True, settings.COLOR_MUTED)
        surface.blit(fps_text, fps_text.get_rect(topright=(w - 20, 90)))

        if prompt:
            text = self.font.render(prompt, True, settings.COLOR_TEXT)
            box = text.get_rect(center=(w // 2, h - 90)).inflate(40, 20)
            pygame.draw.rect(surface, (15, 22, 36), box)
            pygame.draw.rect(surface, settings.COLOR_AMBER, box, 2)
            surface.blit(text, text.get_rect(center=box.center))

        for i, (message, remaining) in enumerate(self._notices):
            banner = self.notice_font.render(message, True, settings.COLOR_TEXT)
            banner.set_alpha(int(255 * min(1.0, remaining / 0.8)))   # fade out
            surface.blit(banner, banner.get_rect(center=(w // 2, 130 + i * 56)))

        hint = self.font.render(
            "WASD move | SHIFT sprint | E interact | F3 debug | N skip phase | "
            "H/J damage/heal | ESC menu", True, settings.COLOR_MUTED)
        surface.blit(hint, (20, h - 32))

        if stats.is_dead:
            msg = self.big_font.render("YOU DIED", True, settings.COLOR_ACCENT)
            surface.blit(msg, msg.get_rect(center=(w // 2, h // 2)))

    def _bar(self, surface: pygame.Surface, pos: tuple[int, int], value: float,
             maximum: float, color: tuple[int, int, int], label: str) -> None:
        width, height = 260, 22
        x, y = pos
        pygame.draw.rect(surface, (20, 26, 40), (x, y, width, height))
        fill = int(width * max(0.0, min(1.0, value / maximum)))
        pygame.draw.rect(surface, color, (x, y, fill, height))
        pygame.draw.rect(surface, (70, 88, 120), (x, y, width, height), 2)
        text = self.font.render(label, True, settings.COLOR_TEXT)
        surface.blit(text, (x + 8, y + 1))