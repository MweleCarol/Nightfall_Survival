"""The Game object: owns the window, clock, event bus and main loop."""
from __future__ import annotations

import logging

import pygame

from src.core import settings
from src.core.event_bus import EventBus
from src.core.state_manager import StateManager

log = logging.getLogger(__name__)


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(settings.TITLE)
        self.screen = pygame.display.set_mode(
            (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        )
        self.clock = pygame.time.Clock()
        self.running = False
        self.event_bus = EventBus()
        self.state_manager = StateManager()

    def run(self) -> None:
        """Main loop: time -> input -> update -> render."""
        self.running = True
        try:
            while self.running:
                dt = min(self.clock.tick(settings.FPS) / 1000.0, settings.MAX_DT)

                events = pygame.event.get()
                for event in events:
                    if event.type == pygame.QUIT:
                        self.running = False
                self.state_manager.handle_events(events)

                self.state_manager.update(dt)

                self.screen.fill(settings.COLOR_BACKGROUND)
                self.state_manager.render(self.screen)
                pygame.display.flip()
        finally:
            self.shutdown()

    def quit(self) -> None:
        """Ask the loop to stop at the end of this frame."""
        self.running = False

    def shutdown(self) -> None:
        log.info("Shutting down")
        pygame.quit()