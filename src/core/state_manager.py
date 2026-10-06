"""Owns the active GameState and routes the loop calls to it."""
from __future__ import annotations

from typing import Iterable, Optional

import pygame

from src.core.game_state import GameState


class StateManager:
    def __init__(self) -> None:
        self.current_state: Optional[GameState] = None

    def change_state(self, new_state: GameState) -> None:
        if self.current_state is not None:
            self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()

    def handle_events(self, events: Iterable[pygame.event.Event]) -> None:
        if self.current_state is None:
            return
        for event in events:
            self.current_state.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current_state is not None:
            self.current_state.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        if self.current_state is not None:
            self.current_state.render(surface)