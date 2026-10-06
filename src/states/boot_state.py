"""Temporary title screen used to verify the foundation works."""
from __future__ import annotations

import pygame

from src.core import settings
from src.core.game_state import GameState


class BootState(GameState):
    def enter(self) -> None:
        self.title_font = pygame.font.SysFont("arial", 72, bold=True)
        self.small_font = pygame.font.SysFont("arial", 24)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.game.quit()

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        cx = settings.SCREEN_WIDTH // 2
        cy = settings.SCREEN_HEIGHT // 2

        title = self.title_font.render("NIGHTFALL SURVIVAL", True, settings.COLOR_TEXT)
        surface.blit(title, title.get_rect(center=(cx, cy - 40)))

        sub = self.small_font.render("Milestone 1: Foundation", True, settings.COLOR_ACCENT)
        surface.blit(sub, sub.get_rect(center=(cx, cy + 30)))

        fps = self.small_font.render(
            f"FPS: {self.game.clock.get_fps():.0f}   |   ESC to quit",
            True, settings.COLOR_MUTED,
        )
        surface.blit(fps, (16, 16))