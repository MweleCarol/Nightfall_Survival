"""Abstract base class that every game screen (state) inherits from."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.core.game import Game


class GameState(ABC):
    """One screen/mode of the game: menu, playing, paused, etc."""

    def __init__(self, game: Game) -> None:
        self.game = game

    def enter(self) -> None:
        """Called once when this state becomes active."""

    def exit(self) -> None:
        """Called once when this state stops being active."""

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """React to a single input event."""

    @abstractmethod
    def update(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None:
        """Draw this state onto the surface."""