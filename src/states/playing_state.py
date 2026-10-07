"""The in-game state: world, player, combat, waves, loot, progression, HUD."""
from __future__ import annotations

import random

import pygame
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.combat.weapon import Weapon, load_weapon_defs
from src.core import settings
from src.core.game_state import GameState
from src.enemies.enemy import Enemy
from src.enemies.factory import EnemyFactory
from src.player.inventory import Inventory, load_item_defs
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.systems.crafting import CraftingSystem, load_crafting_data
from src.systems.loot_system import LootSystem, load_loot_tables
from src.systems.progression import Progression
from src.systems.skills import SkillSet, load_skill_defs
from src.systems.wave_manager import WaveManager, load_wave_config
from src.ui.combat_hud import CombatHUD
from src.ui.hud import HUD
from src.ui.inventory_ui import InventoryUI
from src.ui.progression_hud import ProgressionHUD
from src.ui.skills_ui import SkillsUI
from src.ui.survival_hud import SurvivalHUD
from src.ui.workshop_ui import WorkshopUI
from src.world.camera import Camera
from src.world.day_night import DayNightCycle
from src.world.lighting import Lighting
from src.world.loot_objects import LootContainer, Pickup
from src.world.map import GameMap

# Keys that close each overlay screen.
OVERLAY_CLOSE_KEYS = {
    "inventory": (pygame.K_TAB, pygame.K_ESCAPE),
    "skills": (pygame.K_k, pygame.K_ESCAPE),
    "workshop": (pygame.K_e, pygame.K_ESCAPE),
}


class PlayingState(GameState):
    def enter(self) -> None:
        self.rng = random.Random()
        self.map = GameMap.load(settings.DEFAULT_MAP)

        # Items and inventory
        self.item_defs = load_item_defs()
        self.inventory = Inventory(settings.INVENTORY_CAPACITY, self.item_defs)
        for item_id, quantity in settings.PLAYER_START_ITEMS.items():
            self.inventory.add(item_id, quantity)

        # Player and weapon (the weapon draws its spare ammo from the inventory)
        weapon_defs = load_weapon_defs()
        if settings.PLAYER_START_WEAPON not in weapon_defs:
            raise DataLoadError(
                f"{settings.WEAPONS_FILE}: starting weapon "
                f"'{settings.PLAYER_START_WEAPON}' not found")
        weapon = Weapon(weapon_defs[settings.PLAYER_START_WEAPON], ammo_source=self.inventory)
        self.player = Player(self.map.player_spawn, weapon, self.inventory)

        self.camera = Camera(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT,
                             self.map.width, self.map.height)
        self.camera.snap_to(self.player.position)
        self.cycle = DayNightCycle(event_bus=self.game.event_bus)
        self.lighting = Lighting(settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT)

        # Progression, skills and crafting
        self.progression = Progression(event_bus=self.game.event_bus)
        self.skills = SkillSet(load_skill_defs())
        self.crafting = CraftingSystem(load_crafting_data(self.item_defs), self.inventory, self.rng)

        # UI
        self.hud = HUD()
        self.combat_hud = CombatHUD()
        self.survival_hud = SurvivalHUD()
        self.progression_hud = ProgressionHUD()
        self.inventory_ui = InventoryUI()
        self.skills_ui = SkillsUI(self.skills, self.progression)
        self.workshop_ui = WorkshopUI(self.crafting, self.inventory, weapon, self.skills)
        self.active_overlay: str | None = None
        self.debug_font = pygame.font.SysFont("arial", 16, bold=True)

        # Combat, enemies, waves, loot
        self.combat = CombatSystem(event_bus=self.game.event_bus)
        self.enemy_factory = EnemyFactory()
        self.enemies: list[Enemy] = []
        wave_config = load_wave_config(settings.WAVES_FILE, set(self.enemy_factory.definitions))
        self.wave_manager = WaveManager(
            wave_config, self.enemy_factory, [zone.rect for zone in self.map.spawn_zones],
            self.game.event_bus, self.rng)
        self.loot = LootSystem(load_loot_tables(self.item_defs), self.rng)
        self.containers = [LootContainer(p.id, p.pos, p.category) for p in self.map.loot_points]
        self.pickups: list[Pickup] = []

        self.debug = False
        self.interaction: tuple[str, object, str] | None = None
        self.kills = 0
        self.fire_pressed = False
        self.full_notice_timer = 0.0
        self._death_announced = False
        self.death_timer = 0.0

        self._apply_skill_effects()

        self._subscriptions = [
            ("NIGHT_STARTED", self._on_night_started),
            ("NIGHT_COMPLETED", self._on_night_completed),
            ("DAY_STARTED", self._on_day_started),
            ("ENEMY_DIED", self._on_enemy_died),
            ("WAVE_STARTED", self._on_wave_started),
            ("WAVE_COMPLETED", self._on_wave_completed),
            ("NIGHT_CLEARED", self._on_night_cleared),
            ("LEVEL_UP", self._on_level_up),
        ]
        for event, handler in self._subscriptions:
            self.game.event_bus.on(event, handler)
        pygame.mouse.set_visible(False)          # we draw our own crosshair
        self.hud.notify("DAY 1 - SCAVENGE WHILE YOU CAN")

    def exit(self) -> None:
        for event, handler in self._subscriptions:
            self.game.event_bus.off(event, handler)
        pygame.mouse.set_visible(True)

    # ---- skills: turn ranks and upgrades into real stats ----
    def _apply_skill_effects(self) -> None:
        skills, weapon = self.skills, self.player.weapon
        self.player.apply_bonuses(int(skills.bonus("max_health")),
                                  skills.bonus("max_stamina"),
                                  skills.bonus("move_speed"))
        self.inventory.capacity = settings.INVENTORY_CAPACITY + int(skills.bonus("carry_slots"))
        weapon.modifiers = {
            "damage": skills.bonus("damage") + self.crafting.upgrade_bonus("damage", weapon),
            "reload": (skills.bonus("reload_time_reduction")
                       + self.crafting.upgrade_bonus("reload", weapon)),
            "magazine": self.crafting.upgrade_bonus("magazine", weapon),
        }

    # ---- event bus handlers ----
    def _on_night_started(self, data: dict) -> None:
        self.hud.notify(f"NIGHT {data['night']} BEGINS")
        self.wave_manager.start_night(data["night"])

    def _on_night_completed(self, data: dict) -> None:
        self.wave_manager.end_night()
        self.enemies.clear()                     # whatever survived burns away at dawn

    def _on_day_started(self, data: dict) -> None:
        self.hud.notify(f"DAY {data['day']} - YOU SURVIVED")
        for container in self.containers:
            container.reset()                    # the crates are restocked

    def _on_wave_started(self, data: dict) -> None:
        self.hud.notify(f"WAVE {data['wave']} / {self.wave_manager.config.waves_per_night}")

    def _on_wave_completed(self, data: dict) -> None:
        self.progression.add_xp(settings.XP_PER_WAVE * data["wave"])

    def _on_night_cleared(self, data: dict) -> None:
        self.hud.notify("NIGHT CLEARED - HOLD UNTIL DAWN")
        self.progression.add_xp(settings.XP_NIGHT_CLEARED)

    def _on_enemy_died(self, data: dict) -> None:
        self.kills += 1
        self.progression.add_xp(data["xp"])
        table = self.loot.table_for_enemy(data["enemy_id"])
        for item_id, quantity in self.loot.roll(table, self.skills.bonus("loot_luck")):
            self._drop_pickup(item_id, quantity, Vector2(data["position"]))

    def _on_level_up(self, data: dict) -> None:
        self.hud.notify(f"LEVEL UP!  LEVEL {data['level']}  -  PRESS K")

    # ---- input ----
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.active_overlay is not None:
            self._handle_overlay_event(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.fire_pressed = True
            return
        if event.type != pygame.KEYDOWN:
            return

        key = event.key
        if key == pygame.K_ESCAPE:
            from src.states.boot_state import BootState  # avoid circular import
            self.game.state_manager.change_state(BootState(self.game))
        elif key == pygame.K_TAB:
            self._open_overlay("inventory")
        elif key == pygame.K_k:
            self._open_overlay("skills")
        elif key == pygame.K_e:
            self._interact()
        elif key == pygame.K_q:
            self._quick_heal()
        elif key == pygame.K_r:
            if not self.player.stats.is_dead:
                self.player.weapon.start_reload()
        elif key == pygame.K_F3:
            self.debug = not self.debug
        elif key == pygame.K_t:      # DEBUG ONLY: spawn a Walker at the cursor
            self._debug_spawn_walker()
        elif key == pygame.K_n:      # DEBUG ONLY: skip day/night
            self.cycle.skip_to_next_phase()
        elif key == pygame.K_x:      # DEBUG ONLY: +100 XP
            self.progression.add_xp(100)
        elif key == pygame.K_g:      # DEBUG ONLY: free crafting materials
            for item_id, quantity in (("scrap", 20), ("chemicals", 10), ("medical_supplies", 10),
                                      ("weapon_parts", 6), ("batteries", 4)):
                self.inventory.add(item_id, quantity)
            self.hud.notify("DEBUG: materials added", 1.5)
        elif key == pygame.K_h:      # DEBUG ONLY
            self.player.take_damage(10)
        elif key == pygame.K_j:      # DEBUG ONLY
            self.player.stats.heal(10)

    def _open_overlay(self, name: str) -> None:
        if self.player.stats.is_dead:
            return
        self.active_overlay = name
        if name == "inventory":
            self.inventory_ui.selected = 0
        elif name == "skills":
            self.skills_ui.reset()

    def _handle_overlay_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        name = self.active_overlay
        if event.key in OVERLAY_CLOSE_KEYS[name]:
            self.active_overlay = None
            return
        if name == "inventory":
            message = self.inventory_ui.handle_event(event, self.player)
        elif name == "skills":
            message = self.skills_ui.handle_event(event)
        else:
            message = self.workshop_ui.handle_event(event)
        if name != "inventory":
            self._apply_skill_effects()          # ranks or weapon upgrades may have changed
        if message:
            self.hud.notify(message, 2.0)

    # ---- update ----
    def update(self, dt: float) -> None:
        self.hud.update(dt)
        if self.active_overlay is not None:
            self.fire_pressed = False
            return                                # menus pause the game

        self.full_notice_timer = max(0.0, self.full_notice_timer - dt)
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
        self._update_waves(dt)
        self._update_enemies(dt)
        self._update_pickups(dt)

        self.interaction = self._find_interaction()
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
                                        weapon, self.enemies, self.map.walls,
                                        crit_chance=self.skills.bonus("crit_chance"))

    def _update_waves(self, dt: float) -> None:
        alive = sum(1 for enemy in self.enemies if not enemy.is_dead)
        self.enemies.extend(self.wave_manager.update(dt, alive))

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

    def _update_pickups(self, dt: float) -> None:
        remaining: list[Pickup] = []
        for pickup in self.pickups:
            pickup.update(dt)
            if pickup.expired:
                continue
            near = self.player.position.distance_to(pickup.position) <= settings.PICKUP_RADIUS
            if near and not self.player.stats.is_dead:
                added = self.inventory.add(pickup.item_id, pickup.quantity)
                if added:
                    pickup.quantity -= added
                    self.hud.notify(f"+{added} {pickup.label}", 1.6)
                elif self.full_notice_timer <= 0:
                    self.hud.notify("INVENTORY FULL", 1.6)
                    self.full_notice_timer = settings.FULL_NOTICE_COOLDOWN
            if pickup.quantity > 0:
                remaining.append(pickup)
        self.pickups = remaining

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

    # ---- interaction, looting, healing ----
    def _find_interaction(self) -> tuple[str, object, str] | None:
        if self.player.stats.is_dead:
            return None
        best, best_distance = None, settings.CONTAINER_INTERACT_RANGE
        for container in self.containers:
            if container.opened:
                continue
            distance = self.player.position.distance_to(container.position)
            if distance <= best_distance:
                best, best_distance = container, distance
        if best is not None:
            return ("container", best, "Press E to search")

        zone = self.map.interactable_at(self.player.rect)
        if zone is not None:
            if zone.kind == "rest":
                if self.cycle.is_day:            # resting is only offered during the day
                    return ("rest", zone, zone.prompt)
            else:
                return ("station", zone, zone.prompt)
        return None

    def _interact(self) -> None:
        if self.interaction is None:
            return
        kind, target, _prompt = self.interaction
        if kind == "container":
            self._search_container(target)
        elif kind == "rest":
            self.cycle.skip_to_next_phase()
        elif kind == "station":
            self.workshop_ui.open_tab("craft" if target.kind == "workbench" else "weapon")
            self.active_overlay = "workshop"

    def _search_container(self, container: LootContainer) -> None:
        container.opened = True
        self.progression.add_xp(settings.XP_CONTAINER_SEARCH)
        drops = self.loot.roll(container.category, self.skills.bonus("loot_luck"))
        if not drops:
            self.hud.notify("Nothing useful here", 2.0)
            return
        for item_id, quantity in drops:
            name = self.item_defs[item_id].name
            added = self.inventory.add(item_id, quantity)
            if added:
                self.hud.notify(f"+{added} {name}", 2.0)
            if added < quantity:                 # what doesn't fit lands on the ground
                self._drop_pickup(item_id, quantity - added, container.position)
                self.hud.notify("INVENTORY FULL - ITEMS DROPPED", 2.0)

    def _drop_pickup(self, item_id: str, quantity: int, origin: Vector2) -> None:
        definition = self.item_defs[item_id]
        scatter = settings.DROP_SCATTER
        position = origin + Vector2(self.rng.uniform(-scatter, scatter),
                                    self.rng.uniform(-scatter, scatter))
        if any(wall.collidepoint(position) for wall in self.map.walls):
            position = Vector2(origin)           # never drop an item inside a wall
        self.pickups.append(Pickup(item_id, quantity, position,
                                   settings.RARITY_COLORS[definition.rarity], definition.name))

    def _quick_heal(self) -> None:
        if self.player.stats.is_dead:
            return
        if self.player.stats.health >= self.player.stats.max_health:
            self.hud.notify("Health is full", 1.2)
            return
        name = self.player.quick_heal()
        self.hud.notify(f"Used {name}" if name else "No healing items", 1.5)

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
        for container in self.containers:        # culling: only draw what is near the screen
            if view.collidepoint(container.position):
                container.draw(surface, self.camera)
        for pickup in self.pickups:
            if view.collidepoint(pickup.position):
                close = self.player.position.distance_to(pickup.position) < 90
                pickup.draw(surface, self.camera, self.debug_font, close)
        for enemy in self.enemies:
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

        prompt = self.interaction[2] if self.interaction else None
        self.hud.draw(surface, self.player.stats, self.game.clock.get_fps(),
                      self.cycle, prompt, self.map.in_safe_zone(self.player.rect))
        alive = sum(1 for enemy in self.enemies if not enemy.is_dead)
        self.combat_hud.draw(surface, self.player.weapon, pygame.mouse.get_pos(), alive)
        self.survival_hud.draw(surface, self.wave_manager, alive, self.inventory,
                               self.cycle.is_night)
        self.progression_hud.draw(surface, self.progression)

        if self.active_overlay == "inventory":
            self.inventory_ui.draw(surface, self.player)
        elif self.active_overlay == "skills":
            self.skills_ui.draw(surface)
        elif self.active_overlay == "workshop":
            self.workshop_ui.draw(surface)