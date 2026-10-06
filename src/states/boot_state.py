"""Temporary title screen until the real main menu is built (Milestone 9)."""
from __future__ import annotations

import pygame

from src.core import settings
from src.core.game_state import GameState


class BootState(GameState):
    def enter(self) -> None:
        self.title_font = pygame.font.SysFont("arial", 72, bold=True)
        self.small_font = pygame.font.SysFont("arial", 24)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.game.quit()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from src.states.playing_state import PlayingState  # avoid circular import
            self.game.state_manager.change_state(PlayingState(self.game))

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        cx, cy = settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2
        title = self.title_font.render("NIGHTFALL SURVIVAL", True, settings.COLOR_TEXT)
        surface.blit(title, title.get_rect(center=(cx, cy - 40)))
        sub = self.small_font.render("Press ENTER to start  |  ESC to quit",
                                     True, settings.COLOR_ACCENT)
        surface.blit(sub, sub.get_rect(center=(cx, cy + 30)))