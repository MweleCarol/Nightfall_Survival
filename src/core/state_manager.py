"""Owns a stack of GameStates. Only the top one receives input and updates."""
from __future__ import annotations

from typing import Iterable, Optional

import pygame

from src.core.game_state import GameState


class StateManager:
    def __init__(self) -> None:
        self._stack: list[GameState] = []

    @property
    def current_state(self) -> Optional[GameState]:
        return self._stack[-1] if self._stack else None

    @property
    def depth(self) -> int:
        return len(self._stack)

    def change_state(self, new_state: GameState) -> None:
        """Replace everything: leave every state (top first), then enter the new one."""
        while self._stack:
            self._stack.pop().exit()
        self._stack.append(new_state)
        new_state.enter()

    def push_state(self, new_state: GameState) -> None:
        """Put a state on top. The one below stays alive but stops receiving input."""
        self._stack.append(new_state)
        new_state.enter()

    def pop_state(self) -> Optional[GameState]:
        """Remove the top state; the one below becomes active again."""
        if not self._stack:
            return None
        state = self._stack.pop()
        state.exit()
        return state

    def handle_events(self, events: Iterable[pygame.event.Event]) -> None:
        state = self.current_state
        if state is None:
            return
        for event in events:
            if self.current_state is not state:      # the state changed mid-way: stop
                break
            state.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current_state is not None:
            self.current_state.update(dt)

    def render(self, surface: pygame.Surface) -> None:
        if not self._stack:
            return
        first = len(self._stack) - 1
        while first > 0 and self._stack[first].transparent:   # draw what is visible underneath
            first -= 1
        for state in self._stack[first:]:
            state.render(surface)