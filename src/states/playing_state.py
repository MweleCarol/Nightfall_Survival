"""The in-game state: world, player, combat, waves, loot, progression, story, bosses, HUD."""
from __future__ import annotations

import random

import pygame
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.combat.weapon import Weapon, load_weapon_defs
from src.core import settings
from src.core.game_state import GameState
from src.enemies.boss import Boss, load_boss_defs
from src.enemies.enemy import Enemy
from src.enemies.factory import EnemyFactory
from src.player.inventory import Inventory, load_item_defs
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.systems.crafting import CraftingSystem, load_crafting_data
from src.systems.loot_system import LootSystem, load_loot_tables
from src.systems.mission_system import (
    MissionManager, MissionStatus, load_missions, validate_references,
)
from src.systems.progression import Progression
from src.systems.safehouse_rules import NightResult, SafeZoneRules
from src.systems.skills import SkillSet, load_skill_defs
from src.systems.story import StoryState, load_story_data
from src.systems.wave_manager import WaveManager, load_wave_config
from src.ui.boss_hud import BossHUD
from src.ui.combat_hud import CombatHUD
from src.ui.hud import HUD
from src.ui.inventory_ui import InventoryUI
from src.ui.mission_hud import MissionHUD
from src.ui.mission_ui import MissionUI
from src.ui.progression_hud import ProgressionHUD
from src.ui.radio_ui import RadioUI
from src.ui.reader_ui import ReaderUI
from src.ui.skills_ui import SkillsUI
from src.ui.survival_hud import SurvivalHUD
from src.ui.workshop_ui import WorkshopUI
from src.world.arena import Arena, ArenaState, load_arenas
from src.world.camera import Camera
from src.world.day_night import DayNightCycle
from src.world.lighting import Lighting
from src.world.loot_objects import LootContainer, Pickup
from src.world.map import GameMap
from src.world.story_world import StoryObject, load_story_world

# Keys that close each overlay screen.
OVERLAY_CLOSE_KEYS = {
    "inventory": (pygame.K_TAB, pygame.K_ESCAPE),
    "skills": (pygame.K_k, pygame.K_ESCAPE),
    "workshop": (pygame.K_e, pygame.K_ESCAPE),
    "journal": (pygame.K_m, pygame.K_ESCAPE),
    "board": (pygame.K_e, pygame.K_ESCAPE),
    "radio": (pygame.K_e, pygame.K_ESCAPE),
    "reader": (pygame.K_e, pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE),
}

# Game events that missions and the story react to (forwarded by _route).
ROUTED_EVENTS = (
    "GAME_STARTED", "LOCATION_REACHED", "ITEM_COLLECTED", "ENEMY_DIED", "WAVE_COMPLETED",
    "NIGHT_STARTED", "NIGHT_COMPLETED", "DAY_STARTED", "OBJECT_INTERACTED",
    "CONTAINER_SEARCHED", "MISSION_STARTED", "MISSION_COMPLETED",
)


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

        # Bosses and arenas
        self.boss_defs = load_boss_defs(self.item_defs)
        self.arenas = [Arena(d) for d in load_arenas(set(self.boss_defs)).values()]
        self.boss: Boss | None = None
        self.current_walls: list[pygame.Rect] = list(self.map.walls)

        # Safehouse rules: A (shooting breaks the truce) and B (a night counts only if cleared)
        self.safe_rules = SafeZoneRules()
        self.night_result = NightResult()

        # Story world, missions and story state
        self.story_world = load_story_world(self.item_defs)
        missions = load_missions(self.item_defs)
        problems = validate_references(
            missions,
            {location.id for location in self.story_world.locations},
            {obj.id for obj in self.story_world.objects} | {i.id for i in self.map.interactables},
            set(self.enemy_factory.definitions) | set(self.boss_defs))
        for arena in self.arenas:
            mission_id = arena.definition.mission
            if mission_id is not None and mission_id not in missions:
                problems.append(f"arena '{arena.definition.id}': unknown mission '{mission_id}'")
        if problems:
            raise DataLoadError("Mission data problems:\n  " + "\n  ".join(problems))
        self.mission_manager = MissionManager(missions, self.game.event_bus)
        self.story = StoryState(load_story_data(), self.game.event_bus)
        self.inside_locations: set[str] = set()
        self.discovered_locations: set[str] = set()
        self._known_available = {m.id for m in self.mission_manager.available()}

        # UI
        self.hud = HUD()
        self.combat_hud = CombatHUD()
        self.survival_hud = SurvivalHUD()
        self.progression_hud = ProgressionHUD()
        self.mission_hud = MissionHUD()
        self.boss_hud = BossHUD()
        self.inventory_ui = InventoryUI()
        self.skills_ui = SkillsUI(self.skills, self.progression)
        self.workshop_ui = WorkshopUI(self.crafting, self.inventory, weapon, self.skills)
        self.mission_ui = MissionUI(self.mission_manager, self.story, self.item_defs)
        self.radio_ui = RadioUI(self.story)
        self.reader_ui = ReaderUI()
        self.active_overlay: str | None = None
        self.debug_font = pygame.font.SysFont("arial", 16, bold=True)

        self.debug = False
        self.interaction: tuple[str, object, str] | None = None
        self.kills = 0
        self.fire_pressed = False
        self.full_notice_timer = 0.0
        self._death_announced = False
        self.death_timer = 0.0

        self._apply_skill_effects()
        self._refresh_walls()

        self._subscriptions = [
            ("NIGHT_STARTED", self._on_night_started),
            ("NIGHT_COMPLETED", self._on_night_completed),
            ("DAY_STARTED", self._on_day_started),
            ("ENEMY_DIED", self._on_enemy_died),
            ("WAVE_STARTED", self._on_wave_started),
            ("WAVE_COMPLETED", self._on_wave_completed),
            ("NIGHT_CLEARED", self._on_night_cleared),
            ("LEVEL_UP", self._on_level_up),
            ("MISSION_STARTED", self._on_mission_started),
            ("MISSION_COMPLETED", self._on_mission_completed),
            ("MISSION_FAILED", self._on_mission_failed),
            ("RADIO_MESSAGE", self._on_radio_message),
            ("CHAPTER_UNLOCKED", self._on_chapter_unlocked),
            ("BOSS_PHASE_CHANGED", self._on_boss_phase_changed),
            ("BOSS_STUNNED", self._on_boss_stunned),
            ("BOSS_DEFEATED", self._on_boss_defeated),
        ]
        for event_name in ROUTED_EVENTS:
            self._subscriptions.append((event_name, self._make_router(event_name)))
        for event_name, handler in self._subscriptions:
            self.game.event_bus.on(event_name, handler)

        pygame.mouse.set_visible(False)          # we draw our own crosshair
        self.hud.notify("DAY 1 - SCAVENGE WHILE YOU CAN")
        self.game.event_bus.emit("GAME_STARTED", {})

    def exit(self) -> None:
        for event_name, handler in self._subscriptions:
            self.game.event_bus.off(event_name, handler)
        pygame.mouse.set_visible(True)

    # ---- walls: the map plus any closed boss gates ----
    def _refresh_walls(self) -> None:
        self.current_walls = list(self.map.walls)
        for arena in self.arenas:
            self.current_walls.extend(arena.barriers)

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

    # ---- event routing: missions and story listen to everything through here ----
    def _make_router(self, event_name: str):
        return lambda data, name=event_name: self._route(name, data)

    def _route(self, event_name: str, data: dict) -> None:
        self.story.notify(event_name, data)
        if event_name == "NIGHT_COMPLETED" and not self.night_result.counts_as_survived:
            return            # rule B: a night that wasn't cleared does not count for missions
        self.mission_manager.notify(event_name, data)

    # ---- event bus handlers ----
    def _on_night_started(self, data: dict) -> None:
        self.night_result.start_night()
        self.hud.notify(f"NIGHT {data['night']} BEGINS")
        self.wave_manager.start_night(data["night"])

    def _on_night_completed(self, data: dict) -> None:
        self.wave_manager.end_night()
        self.enemies.clear()                     # whatever survived burns away at dawn

    def _on_day_started(self, data: dict) -> None:
        if self.night_result.counts_as_survived:
            self.hud.notify(f"DAY {data['day']} - YOU SURVIVED")
        else:
            self.hud.notify(f"DAY {data['day']} - THE NIGHT WAS NOT CLEARED", 3.5)
        for container in self.containers:
            container.reset()                    # the crates are restocked

    def _on_wave_started(self, data: dict) -> None:
        self.hud.notify(f"WAVE {data['wave']} / {self.wave_manager.config.waves_per_night}")

    def _on_wave_completed(self, data: dict) -> None:
        self.progression.add_xp(settings.XP_PER_WAVE * data["wave"])

    def _on_night_cleared(self, data: dict) -> None:
        self.night_result.mark_cleared()
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

    def _on_mission_started(self, data: dict) -> None:
        title = self.mission_manager.missions[data["id"]].title.upper()
        self.hud.notify(f"MISSION STARTED: {title}", 3.0)

    def _on_mission_failed(self, data: dict) -> None:
        title = self.mission_manager.missions[data["id"]].title.upper()
        self.hud.notify(f"MISSION FAILED: {title}", 3.0)

    def _on_mission_completed(self, data: dict) -> None:
        mission = self.mission_manager.missions[data["id"]]
        self.hud.notify(f"MISSION COMPLETE: {mission.title.upper()}", 3.5)
        rewards = mission.rewards
        parts: list[str] = []
        if rewards.xp:
            parts.append(f"{rewards.xp} XP")
            self.progression.add_xp(rewards.xp)
        for item_id, quantity in rewards.items.items():
            self._grant_item(item_id, quantity, self.player.position, announce=False, collected=False)
            parts.append(f"{quantity} {self.item_defs[item_id].name}")
        if parts:
            self.hud.notify("REWARDS: " + ", ".join(parts), 3.5)
        if rewards.unlock_chapter is not None:
            self.story.unlock_chapter(rewards.unlock_chapter)

        available = {m.id for m in self.mission_manager.available()}
        if available - self._known_available:
            self.hud.notify("NEW MISSIONS AT THE MISSION BOARD", 3.0)
        self._known_available |= available

    def _on_radio_message(self, data: dict) -> None:
        self.hud.notify("INCOMING TRANSMISSION - USE THE SAFEHOUSE RADIO", 3.0)

    def _on_chapter_unlocked(self, data: dict) -> None:
        self.hud.notify(f"CHAPTER {data['chapter']} - {data['title'].upper()}", 4.0)

    def _on_boss_phase_changed(self, data: dict) -> None:
        self.hud.notify(f"{data['phase_name'].upper()}!", 2.5)

    def _on_boss_stunned(self, data: dict) -> None:
        self.hud.notify(f"{data['name'].upper()} IS STUNNED!", 1.5)

    def _on_boss_defeated(self, data: dict) -> None:
        definition = self.boss_defs[data["id"]]
        rewards = definition.rewards
        self.hud.notify(f"{definition.name.upper()} IS DEAD", 4.0)
        parts: list[str] = []
        if rewards.skill_points:
            self.progression.skill_points += rewards.skill_points
            parts.append(f"{rewards.skill_points} SKILL POINTS")
        for item_id, quantity in rewards.items.items():
            self._grant_item(item_id, quantity, self.player.position, announce=False, collected=False)
            parts.append(f"{quantity} {self.item_defs[item_id].name}")
        if parts:
            self.hud.notify("BOSS REWARDS: " + ", ".join(parts), 4.0)
        for arena in self.arenas:
            if arena.state is ArenaState.ACTIVE and arena.definition.boss_id == data["id"]:
                arena.clear()                    # the gates open again
        self._refresh_walls()
        self.boss = None

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
        elif key == pygame.K_m:
            self._open_overlay("journal")
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
        elif key == pygame.K_b:      # DEBUG ONLY: jump into the boss fight
            self._debug_start_boss()
        elif key == pygame.K_y:      # DEBUG ONLY: complete the first active mission
            active = self.mission_manager.active()
            if active:
                self.mission_manager.force_complete(active[0].id)
            else:
                self.hud.notify("DEBUG: no active mission", 1.5)
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
        elif name == "journal":
            self.mission_ui.open(board_mode=False)

    def _handle_overlay_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        name = self.active_overlay
        if event.key in OVERLAY_CLOSE_KEYS[name]:
            self.active_overlay = None
            return
        message = None
        if name == "inventory":
            message = self.inventory_ui.handle_event(event, self.player)
        elif name == "skills":
            message = self.skills_ui.handle_event(event)
        elif name == "workshop":
            message = self.workshop_ui.handle_event(event)
        elif name in ("journal", "board"):
            message = self.mission_ui.handle_event(event)
        elif name == "radio":
            message = self.radio_ui.handle_event(event)
        if name in ("skills", "workshop"):
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
        if self.boss is None:
            self.cycle.update(dt)                 # time stands still during a boss fight
        self.safe_rules.update(dt)

        keys = pygame.key.get_pressed()
        direction = Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        sprint = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        self.player.update(dt, direction, bool(sprint), self.current_walls)
        self.camera.update(self.player.position, dt)
        self.player.aim_at(self.camera.screen_to_world(pygame.mouse.get_pos()))

        self._update_combat(dt)
        if self.boss is None:
            self._update_waves(dt)
        self._update_enemies(dt)
        self._update_boss()
        self._update_pickups(dt)
        self._update_locations()
        self._update_arenas()

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
                return
            fired = self.combat.fire_weapon(
                self.player.position, self.player.aim_direction, weapon, self.enemies,
                self.current_walls, crit_chance=self.skills.bonus("crit_chance"))
            # Rule A: shooting out of the safe zone breaks the truce.
            if fired and self.safe_rules.on_shot_fired(self.map.in_safe_zone(self.player.rect)):
                self.hud.notify("TRUCE BROKEN - THEY KNOW WHERE YOU ARE", 2.5)
                self.game.event_bus.emit("TRUCE_BROKEN", {})

    def _update_waves(self, dt: float) -> None:
        alive = sum(1 for enemy in self.enemies if not enemy.is_dead)
        self.enemies.extend(self.wave_manager.update(dt, alive))

    def _update_enemies(self, dt: float) -> None:
        # Enemies leave you alone only while the safe zone really protects you (rule A).
        in_zone = self.map.in_safe_zone(self.player.rect)
        targetable = (not self.player.stats.is_dead
                      and not self.safe_rules.protects(in_zone))
        for enemy in self.enemies:
            damage = enemy.update(dt, self.player.position, targetable, self.current_walls)
            if damage:
                dealt = self.player.take_damage(damage)
                if dealt:
                    self.game.event_bus.emit("PLAYER_DAMAGED", {"amount": dealt})
        self.enemies = [e for e in self.enemies if not e.is_removable]

    def _update_boss(self) -> None:
        boss = self.boss
        if boss is None:
            return
        for name, data in boss.pop_events():      # phase changes, stuns and death
            self.game.event_bus.emit(name, data)

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
                    self.game.event_bus.emit("ITEM_COLLECTED",
                                             {"item": pickup.item_id, "quantity": added})
                elif self.full_notice_timer <= 0:
                    self.hud.notify("INVENTORY FULL", 1.6)
                    self.full_notice_timer = settings.FULL_NOTICE_COOLDOWN
            if pickup.quantity > 0:
                remaining.append(pickup)
        self.pickups = remaining

    def _update_locations(self) -> None:
        for location in self.story_world.locations:
            inside = location.rect.colliderect(self.player.rect)
            if inside and location.id not in self.inside_locations:
                self.inside_locations.add(location.id)
                if location.id not in self.discovered_locations:
                    self.discovered_locations.add(location.id)
                    self.hud.notify(f"DISCOVERED: {location.name.upper()}", 2.5)
                    self.progression.add_xp(settings.XP_LOCATION_DISCOVERY)
                self.game.event_bus.emit("LOCATION_REACHED", {"location": location.id})
            elif not inside:
                self.inside_locations.discard(location.id)

    def _mission_active(self, mission_id: str | None) -> bool:
        return (mission_id is None
                or self.mission_manager.status.get(mission_id) is MissionStatus.ACTIVE)

    def _update_arenas(self) -> None:
        if self.boss is not None or self.player.stats.is_dead:
            return
        for arena in self.arenas:
            mission_active = self._mission_active(arena.definition.mission)
            if arena.can_trigger(self.player.rect, mission_active, self.cycle.is_day):
                self._start_boss_fight(arena)
                return
            if arena.state is ArenaState.WAITING and mission_active \
                    and arena.is_near(self.player.rect):
                if self.cycle.is_day and not arena.warned:
                    arena.warned = True
                    self.hud.notify(f"{arena.definition.name.upper()} AHEAD - GATES WILL CLOSE", 3.5)
                elif not self.cycle.is_day and not arena.hinted:
                    arena.hinted = True
                    self.hud.notify("TOO DANGEROUS AFTER DARK - COME BACK AT DAWN", 3.0)

    def _start_boss_fight(self, arena: Arena) -> None:
        definition = self.boss_defs[arena.definition.boss_id]
        arena.start()
        self._refresh_walls()                    # the gates close
        self.boss = Boss(definition, arena.definition.boss_spawn, self.rng)
        self.enemies.append(self.boss)
        self.hud.notify("THE GATES CLOSE BEHIND YOU", 3.0)
        self.game.event_bus.emit("BOSS_STARTED", {"id": definition.id, "name": definition.name})

    def _debug_start_boss(self) -> None:
        if self.boss is not None:
            return
        arena = next((a for a in self.arenas if a.state is ArenaState.WAITING), None)
        if arena is None:
            self.hud.notify("DEBUG: no arena waiting", 1.5)
            return
        self.enemies.clear()
        self.wave_manager.end_night()
        center = Vector2(arena.definition.rect.center)
        self.player.position = center
        self.player.rect.center = (round(center.x), round(center.y))
        self.camera.snap_to(self.player.position)
        self._start_boss_fight(arena)

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

    # ---- interaction, looting, story objects, healing ----
    def _object_available(self, obj: StoryObject) -> bool:
        if obj.used:
            return False
        definition = obj.definition
        if definition.mission is not None:
            if self.mission_manager.status.get(definition.mission) is not MissionStatus.ACTIVE:
                return False
        if definition.after is not None:
            required = self.story_world.object_by_id(definition.after)
            if required is None or not required.used:
                return False
        return True

    def _find_interaction(self) -> tuple[str, object, str] | None:
        if self.player.stats.is_dead:
            return None
        position = self.player.position

        best_container, best_distance = None, settings.CONTAINER_INTERACT_RANGE
        for container in self.containers:
            if container.opened:
                continue
            distance = position.distance_to(container.position)
            if distance <= best_distance:
                best_container, best_distance = container, distance
        if best_container is not None:
            return ("container", best_container, "Press E to search")

        best_object, best_distance = None, settings.STORY_OBJECT_RANGE
        for obj in self.story_world.objects:
            if not self._object_available(obj):
                continue
            distance = position.distance_to(obj.position)
            if distance <= best_distance:
                best_object, best_distance = obj, distance
        if best_object is not None:
            return ("object", best_object, best_object.definition.prompt)

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
        elif kind == "object":
            self._use_story_object(target)
        elif kind == "rest":
            self.cycle.skip_to_next_phase()
        elif kind == "station":
            self._open_station(target.kind)

    def _open_station(self, station_kind: str) -> None:
        if station_kind in ("workbench", "weapon_station"):
            self.workshop_ui.open_tab("craft" if station_kind == "workbench" else "weapon")
            self.active_overlay = "workshop"
        elif station_kind == "missions":
            self.mission_ui.open(board_mode=True)
            self.active_overlay = "board"
        elif station_kind == "radio":
            self.radio_ui.open()
            self.active_overlay = "radio"
            self.game.event_bus.emit("OBJECT_INTERACTED", {"id": "safehouse_radio"})

    def _use_story_object(self, obj: StoryObject) -> None:
        definition = obj.definition
        if definition.kind == "item":
            if self.inventory.can_add(definition.give_item, definition.quantity) < definition.quantity:
                self.hud.notify("INVENTORY FULL - MAKE ROOM FIRST", 2.5)
                return                           # nothing is used up, so try again later
            self._grant_item(definition.give_item, definition.quantity, obj.position)
        obj.used = True
        if definition.kind == "note":
            note = self.story.data.notes[definition.id]
            if self.story.add_note(definition.id):
                self.hud.notify("NOTE ADDED TO JOURNAL", 2.0)
            self.reader_ui.show(note.title, note.text)
            self.active_overlay = "reader"
        elif definition.kind == "device":
            self.hud.notify(definition.message or definition.name, 2.5)
        self.game.event_bus.emit("OBJECT_INTERACTED", {"id": definition.id})

    def _search_container(self, container: LootContainer) -> None:
        container.opened = True
        self.progression.add_xp(settings.XP_CONTAINER_SEARCH)
        self.game.event_bus.emit("CONTAINER_SEARCHED",
                                 {"id": container.id, "category": container.category})
        drops = self.loot.roll(container.category, self.skills.bonus("loot_luck"))
        if not drops:
            self.hud.notify("Nothing useful here", 2.0)
            return
        for item_id, quantity in drops:
            self._grant_item(item_id, quantity, container.position)

    def _grant_item(self, item_id: str, quantity: int, origin: Vector2,
                    announce: bool = True, collected: bool = True) -> int:
        """Put items in the pack. What doesn't fit lands on the ground. Returns amount added."""
        definition = self.item_defs[item_id]
        added = self.inventory.add(item_id, quantity)
        if added:
            if announce:
                self.hud.notify(f"+{added} {definition.name}", 2.0)
            if collected:
                self.game.event_bus.emit("ITEM_COLLECTED", {"item": item_id, "quantity": added})
        if added < quantity:
            self._drop_pickup(item_id, quantity - added, Vector2(origin))
            self.hud.notify("INVENTORY FULL - ITEMS DROPPED", 2.0)
        return added

    def _drop_pickup(self, item_id: str, quantity: int, origin: Vector2) -> None:
        definition = self.item_defs[item_id]
        scatter = settings.DROP_SCATTER
        position = origin + Vector2(self.rng.uniform(-scatter, scatter),
                                    self.rng.uniform(-scatter, scatter))
        if any(wall.collidepoint(position) for wall in self.current_walls):
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
        if world.contains(rect) and rect.collidelist(self.current_walls) == -1:
            self.enemies.append(self.enemy_factory.create("walker", (pos.x, pos.y)))

    # ---- drawing ----
    def render(self, surface: pygame.Surface) -> None:
        self.map.draw(surface, self.camera)

        view = self.camera.view_rect().inflate(100, 100)
        for arena in self.arenas:                # the gates and the "boss is here" outline
            hint = self._mission_active(arena.definition.mission) and self.cycle.is_day
            arena.draw(surface, self.camera, hint)
        for container in self.containers:        # culling: only draw what is near the screen
            if view.collidepoint(container.position):
                container.draw(surface, self.camera)
        for obj in self.story_world.objects:
            visible = self._object_available(obj) or (obj.used and obj.definition.kind == "note")
            if visible and view.collidepoint(obj.position):
                close = self.player.position.distance_to(obj.position) < 120
                obj.draw(surface, self.camera, self.debug_font, close)
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
            for location in self.story_world.locations:
                pygame.draw.rect(surface, (180, 120, 255), self.camera.apply(location.rect), 2)
            for enemy in self.enemies:
                if view.collidepoint(enemy.position):
                    enemy.draw_debug(surface, self.camera, self.debug_font)

        in_zone = self.map.in_safe_zone(self.player.rect)
        protected = self.safe_rules.protects(in_zone)
        prompt = self.interaction[2] if self.interaction else None
        self.hud.draw(surface, self.player.stats, self.game.clock.get_fps(),
                      self.cycle, prompt, protected)
        if in_zone and self.safe_rules.truce_broken:
            warning = self.debug_font.render("TRUCE BROKEN", True, settings.COLOR_ACCENT)
            surface.blit(warning, (20, 84))
        alive = sum(1 for enemy in self.enemies if not enemy.is_dead)
        self.combat_hud.draw(surface, self.player.weapon, pygame.mouse.get_pos(), alive)
        self.survival_hud.draw(surface, self.wave_manager, alive, self.inventory,
                               self.cycle.is_night)
        self.progression_hud.draw(surface, self.progression)
        self.mission_hud.draw(surface, self.mission_manager, self.story)
        if self.boss is not None:
            self.boss_hud.draw(surface, self.boss)

        overlay = self.active_overlay
        if overlay == "inventory":
            self.inventory_ui.draw(surface, self.player)
        elif overlay == "skills":
            self.skills_ui.draw(surface)
        elif overlay == "workshop":
            self.workshop_ui.draw(surface)
        elif overlay in ("journal", "board"):
            self.mission_ui.draw(surface)
        elif overlay == "radio":
            self.radio_ui.draw(surface)
        elif overlay == "reader":
            self.reader_ui.draw(surface)