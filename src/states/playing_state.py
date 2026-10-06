"""The in-game state: world, player, camera, time of day, lighting, HUD."""
from __future__ import annotations

import pygame
from pygame import Vector2

from src.core import settings
from src.core.game_state import GameState
from src.player.player import Player
from src.ui.hud import HUD
from src.world.camera import Camera
from src.world.day_night import DayNightCycle
from src.world.lighting import Lighting
from src.world.map import GameMap, Interactable


class PlayingState(GameState):
    def enter(self) -> None:
        self.map = GameMap.load(settings.DEFAULT_MAP)
        self.player = Player(self.map.player_spawn)
        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT,
                             self.map.width, self.map.height)
        self.camera.snap_to(self.player.position)
        self.cycle = DayNightCycle(event_bus=self.game.event_bus)
        self.lighting = Lighting(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.hud = HUD()
        self.debug = False
        self.interactable: Interactable | None = None

        self.game.event_bus.on("NIGHT_STARTED", self._on_night_started)
        self.game.event_bus.on("DAY_STARTED", self._on_day_started)
        self.hud.notify("DAY 1 - SCAVENGE WHILE YOU CAN")

    def exit(self) -> None:
        self.game.event_bus.off("NIGHT_STARTED", self._on_night_started)
        self.game.event_bus.off("DAY_STARTED", self._on_day_started)

    # ---- event bus handlers ----
    def _on_night_started(self, data: dict) -> None:
        self.hud.notify(f"NIGHT {data['night']} BEGINS")

    def _on_day_started(self, data: dict) -> None:
        self.hud.notify(f"DAY {data['day']} - YOU SURVIVED")

    # ---- loop ----
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            from src.states.boot_state import BootState  # avoid circular import
            self.game.state_manager.change_state(BootState(self.game))
        elif event.key == pygame.K_e:
            if self.interactable is not None and self.interactable.kind == "rest":
                self.cycle.skip_to_next_phase()
        elif event.key == pygame.K_F3:
            self.debug = not self.debug
        elif event.key == pygame.K_n:      # DEBUG ONLY
            self.cycle.skip_to_next_phase()
        elif event.key == pygame.K_h:      # DEBUG ONLY
            self.player.stats.take_damage(10)
        elif event.key == pygame.K_j:      # DEBUG ONLY
            self.player.stats.heal(10)

    def update(self, dt: float) -> None:
        self.cycle.update(dt)

        keys = pygame.key.get_pressed()
        direction = Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        self.player.update(dt, direction, bool(sprint), self.map.walls)
        self.camera.update(self.player.position, dt)
        self.player.aim_at(self.camera.screen_to_world(pygame.mouse.get_pos()))

        self.interactable = self._find_interactable()
        self.hud.update(dt)

    def _find_interactable(self) -> Interactable | None:
        item = self.map.interactable_at(self.player.rect)
        if item is not None and item.kind == "rest" and self.cycle.is_day:
            return item          # resting is only offered during the day
        return None

    def render(self, surface: pygame.Surface) -> None:
        self.map.draw(surface, self.camera)
        self.player.draw(surface, self.camera)
        self.lighting.render(surface, self.camera, self.cycle.darkness,
                             self.map.street_lights, self.player.position)
        if self.debug:
            self.map.draw_debug(surface, self.camera)
        prompt = self.interactable.prompt if self.interactable else None
        self.hud.draw(surface, self.player.stats, self.game.clock.get_fps(),
                      self.cycle, prompt, self.map.in_safe_zone(self.player.rect))