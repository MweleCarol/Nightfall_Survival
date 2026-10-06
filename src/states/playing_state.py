"""The in-game state: world, player, camera, HUD."""
from __future__ import annotations

import pygame
from pygame import Vector2

from src.core import settings
from src.core.game_state import GameState
from src.player.player import Player
from src.ui.hud import HUD
from src.world.camera import Camera
from src.world.map import SPAWN_POINT, GameMap


class PlayingState(GameState):
    def enter(self) -> None:
        self.map = GameMap()
        self.player = Player(SPAWN_POINT)
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT,
                             self.map.width, self.map.height)
        self.camera.snap_to(self.player.position)
        self.hud = HUD()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            from src.states.boot_state import BootState  # avoid circular import
            self.game.state_manager.change_state(BootState(self.game))
        elif event.key == pygame.K_h:      # DEBUG ONLY
            self.player.stats.take_damage(10)
        elif event.key == pygame.K_j:      # DEBUG ONLY
            self.player.stats.heal(10)

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        direction = Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        self.player.update(dt, direction, bool(sprint), self.map.walls)
        self.camera.update(self.player.position, dt)

        mouse_world = self.camera.screen_to_world(pygame.mouse.get_pos())
        self.player.aim_at(mouse_world)

    def render(self, surface: pygame.Surface) -> None:
        self.map.draw(surface, self.camera)
        self.player.draw(surface, self.camera)
        self.hud.draw(surface, self.player.stats, self.game.clock.get_fps())