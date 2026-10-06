"""The in-game state: world, player, combat, enemies, time of day, HUD."""
from __future__ import annotations

import pygame
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.combat.weapon import Weapon, load_weapon_defs
from src.core import settings
from src.core.game_state import GameState
from src.enemies.enemy import Enemy
from src.enemies.factory import EnemyFactory
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.ui.combat_hud import CombatHUD
from src.ui.hud import HUD
from src.world.camera import Camera
from src.world.day_night import DayNightCycle
from src.world.lighting import Lighting
from src.world.map import GameMap, Interactable

# Temporary: idle Walkers placed in the streets for testing. Waves replace this in M5.
TEST_WALKER_POSITIONS = [(900, 800), (1300, 800), (2000, 800), (1450, 1500)]


class PlayingState(GameState):
    def enter(self) -> None:
        self.map = GameMap.load(settings.DEFAULT_MAP)

        weapon_defs = load_weapon_defs()
        if settings.PLAYER_START_WEAPON not in weapon_defs:
            raise DataLoadError(
                f"{settings.WEAPONS_FILE}: starting weapon "
                f"'{settings.PLAYER_START_WEAPON}' not found")
        weapon = Weapon(weapon_defs[settings.PLAYER_START_WEAPON],
                        reserve=settings.PLAYER_START_RESERVE_AMMO)
        self.player = Player(self.map.player_spawn, weapon)

        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT,
                             self.map.width, self.map.height)
        self.camera.snap_to(self.player.position)
        self.cycle = DayNightCycle(event_bus=self.game.event_bus)
        self.lighting = Lighting(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)
        self.hud = HUD()
        self.combat_hud = CombatHUD()
        self.debug_font = pygame.font.SysFont("arial", 16, bold=True)

        self.combat = CombatSystem(event_bus=self.game.event_bus)
        self.enemy_factory = EnemyFactory()
        self.enemies: list[Enemy] = [
            self.enemy_factory.create("walker", pos) for pos in TEST_WALKER_POSITIONS]

        self.debug = False
        self.interactable: Interactable | None = None
        self.kills = 0
        self.fire_pressed = False
        self._death_announced = False
        self.death_timer = 0.0

        bus = self.game.event_bus
        bus.on("NIGHT_STARTED", self._on_night_started)
        bus.on("DAY_STARTED", self._on_day_started)
        bus.on("ENEMY_DIED", self._on_enemy_died)
        pygame.mouse.set_visible(False)          # we draw our own crosshair
        self.hud.notify("DAY 1 - SCAVENGE WHILE YOU CAN")

    def exit(self) -> None:
        bus = self.game.event_bus
        bus.off("NIGHT_STARTED", self._on_night_started)
        bus.off("DAY_STARTED", self._on_day_started)
        bus.off("ENEMY_DIED", self._on_enemy_died)
        pygame.mouse.set_visible(True)

    # ---- event bus handlers ----
    def _on_night_started(self, data: dict) -> None:
        self.hud.notify(f"NIGHT {data['night']} BEGINS")

    def _on_day_started(self, data: dict) -> None:
        self.hud.notify(f"DAY {data['day']} - YOU SURVIVED")

    def _on_enemy_died(self, data: dict) -> None:
        self.kills += 1

    # ---- loop ----
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.fire_pressed = True
            return
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_ESCAPE:
            from src.states.boot_state import BootState  # avoid circular import
            self.game.state_manager.change_state(BootState(self.game))
        elif event.key == pygame.K_e:
            if self.interactable is not None and self.interactable.kind == "rest":
                self.cycle.skip_to_next_phase()
        elif event.key == pygame.K_r:
            if not self.player.stats.is_dead:
                self.player.weapon.start_reload()
        elif event.key == pygame.K_F3:
            self.debug = not self.debug
        elif event.key == pygame.K_t:      # DEBUG ONLY
            self._debug_spawn_walker()
        elif event.key == pygame.K_n:      # DEBUG ONLY
            self.cycle.skip_to_next_phase()
        elif event.key == pygame.K_h:      # DEBUG ONLY
            self.player.take_damage(10)
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

        self._update_combat(dt)
        self._update_enemies(dt)

        self.interactable = self._find_interactable()
        self.hud.update(dt)
        self._check_player_death(dt)       # keep last: it may switch state

    def _update_combat(self, dt: float) -> None:
        self.combat.update(dt)
        weapon = self.player.weapon
        held = pygame.mouse.get_pressed()[0]
        trigger = self.fire_pressed or (weapon.definition.automatic and held)
        self.fire_pressed = False
        if trigger and not self.player.stats.is_dead:
            if weapon.loaded == 0:
                weapon.start_reload()      # clicking on an empty gun reloads
            else:
                self.combat.fire_weapon(self.player.position, self.player.aim_direction,
                                        weapon, self.enemies, self.map.walls)

    def _update_enemies(self, dt: float) -> None:
        # Enemies ignore a dead player and a player inside the safe zone.
        targetable = (not self.player.stats.is_dead
                      and not self.map.in_safe_zone(self.player.rect))
        for enemy in self.enemies:
            damage = enemy.update(dt, self.player.position, targetable, self.map.walls)
            if damage:
                dealt = self.player.take_damage(damage)
                if dealt:
                    self.game.event_bus.emit("PLAYER_DAMAGED", {"amount": dealt})
        self.enemies = [e for e in self.enemies if not e.is_removable]

    def _check_player_death(self, dt: float) -> None:
        if not self.player.stats.is_dead:
            return
        if not self._death_announced:
            self._death_announced = True
            self.death_timer = settings.GAME_OVER_DELAY
            self.game.event_bus.emit("PLAYER_DIED", {"day": self.cycle.day_number})
            return
        self.death_timer -= dt
        if self.death_timer <= 0:
            from src.states.game_over_state import GameOverState
            self.game.state_manager.change_state(
                GameOverState(self.game, self.cycle.day_number, self.kills))

    def _find_interactable(self) -> Interactable | None:
        item = self.map.interactable_at(self.player.rect)
        if item is not None and item.kind == "rest" and self.cycle.is_day:
            return item          # resting is only offered during the day
        return None

    def _debug_spawn_walker(self) -> None:
        pos = self.camera.screen_to_world(pygame.mouse.get_pos())
        rect = pygame.Rect(0, 0, 32, 32)
        rect.center = (round(pos.x), round(pos.y))
        world = pygame.Rect(0, 0, self.map.width, self.map.height)
        if world.contains(rect) and rect.collidelist(self.map.walls) == -1:
            self.enemies.append(self.enemy_factory.create("walker", (pos.x, pos.y)))

    # ---- drawing ----
    def render(self, surface: pygame.Surface) -> None:
        self.map.draw(surface, self.camera)

        view = self.camera.view_rect().inflate(100, 100)
        for enemy in self.enemies:             # culling: only draw nearby enemies
            if view.collidepoint(enemy.position):
                enemy.draw(surface, self.camera)
        self.player.draw(surface, self.camera)

        self.lighting.render(surface, self.camera, self.cycle.darkness,
                             self.map.street_lights, self.player.position)
        self.combat.draw(surface, self.camera)   # after lighting: flashes glow in the dark

        if self.debug:
            self.map.draw_debug(surface, self.camera)
            for enemy in self.enemies:
                if view.collidepoint(enemy.position):
                    enemy.draw_debug(surface, self.camera, self.debug_font)

        prompt = self.interactable.prompt if self.interactable else None
        self.hud.draw(surface, self.player.stats, self.game.clock.get_fps(),
                      self.cycle, prompt, self.map.in_safe_zone(self.player.rect))
        self.combat_hud.draw(surface, self.player.weapon, pygame.mouse.get_pos(),
                             len(self.enemies))