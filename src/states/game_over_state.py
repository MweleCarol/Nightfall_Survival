"""Shown after the player dies."""
from __future__ import annotations

import pygame

from src.core import settings
from src.core.game_state import GameState


class GameOverState(GameState):
    def __init__(self, game, day_reached: int, kills: int) -> None:
        super().__init__(game)
        self.day_reached = day_reached
        self.kills = kills

    def enter(self) -> None:
        self.title_font = pygame.font.SysFont("arial", 84, bold=True)
        self.font = pygame.font.SysFont("arial", 28, bold=True)
        self.small_font = pygame.font.SysFont("arial", 22)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            from src.states.playing_state import PlayingState  # avoid circular import
            self.game.state_manager.change_state(PlayingState(self.game))
        elif event.key == pygame.K_ESCAPE:
            from src.states.boot_state import BootState
            self.game.state_manager.change_state(BootState(self.game))

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        cx, cy = settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2
        title = self.title_font.render("YOU DIED", True, settings.COLOR_ACCENT)
        surface.blit(title, title.get_rect(center=(cx, cy - 90)))
        for i, line in enumerate((f"Reached day {self.day_reached}",
                                  f"Enemies killed: {self.kills}")):
            text = self.font.render(line, True, settings.COLOR_TEXT)
            surface.blit(text, text.get_rect(center=(cx, cy - 10 + i * 40)))
        hint = self.small_font.render("ENTER - try again     |     ESC - title screen",
                                      True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(center=(cx, cy + 120)))