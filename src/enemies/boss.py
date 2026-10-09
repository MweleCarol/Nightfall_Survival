"""Bosses: data definitions plus the Boss class with phases and telegraphed attacks."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

import pygame
from pygame import Vector2

from src.core import settings
from src.enemies.enemy import AIState, Enemy, EnemyDef
from src.player.inventory import ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field
from src.world.camera import Camera
from src.world.collision import collide_axis

_NUMBER = (int, float)
ATTACK_NAMES = ("cleave", "charge", "slam")
PLAYER_HALF = settings.PLAYER_SIZE / 2      # the player counts as a circle of this radius
CLEAVE_PAUSE = 0.5                          # breathing room after a cleave


def _number(data: dict, key: str, where: str, minimum: float = 0.0,
            exclusive: bool = False) -> float:
    value = float(require_field(data, key, _NUMBER, where))
    if value < minimum or (exclusive and value == minimum):
        raise DataLoadError(
            f"{where}: field '{key}' must be {'>' if exclusive else '>='} {minimum:g}")
    return value


def _whole(data: dict, key: str, where: str, default: int | None = None) -> int:
    if key not in data and default is not None:
        return default
    value = require_field(data, key, int, where)
    if value < 0:
        raise DataLoadError(f"{where}: field '{key}' must be >= 0")
    return value


# ---------------------------------------------------------------- definitions
@dataclass(frozen=True)
class CleaveDef:
    damage: int
    windup: float
    cooldown: float
    radius: float           # size of the swing area
    reach: float            # how far in front of the boss the swing area is centred
    trigger_range: float    # the boss swings when the player is this close

    @classmethod
    def from_dict(cls, data: dict, where: str) -> CleaveDef:
        return cls(_whole(data, "damage", where), _number(data, "windup", where, 0.0, True),
                   _number(data, "cooldown", where), _number(data, "radius", where, 0.0, True),
                   _number(data, "reach", where), _number(data, "trigger_range", where, 0.0, True))


@dataclass(frozen=True)
class ChargeDef:
    damage: int
    windup: float
    cooldown: float
    speed: float
    max_duration: float
    min_distance: float     # only charges when the player is at least this far away
    recover: float          # exposed time after a charge that missed
    wall_recover: float     # exposed time after crashing into a wall

    @classmethod
    def from_dict(cls, data: dict, where: str) -> ChargeDef:
        return cls(_whole(data, "damage", where), _number(data, "windup", where, 0.0, True),
                   _number(data, "cooldown", where), _number(data, "speed", where, 0.0, True),
                   _number(data, "max_duration", where, 0.0, True),
                   _number(data, "min_distance", where), _number(data, "recover", where),
                   _number(data, "wall_recover", where))


@dataclass(frozen=True)
class SlamDef:
    damage: int
    windup: float
    cooldown: float
    radius: float
    trigger_range: float
    recover: float

    @classmethod
    def from_dict(cls, data: dict, where: str) -> SlamDef:
        return cls(_whole(data, "damage", where), _number(data, "windup", where, 0.0, True),
                   _number(data, "cooldown", where), _number(data, "radius", where, 0.0, True),
                   _number(data, "trigger_range", where, 0.0, True),
                   _number(data, "recover", where))


@dataclass(frozen=True)
class PhaseDef:
    name: str
    starts_at: float                        # the phase begins when health falls to this fraction
    speed_multiplier: float
    color: tuple[int, int, int]
    attacks: tuple[str, ...]


@dataclass(frozen=True)
class BossRewards:
    xp: int
    skill_points: int
    items: dict[str, int]

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> BossRewards:
        raw_items = require_field(data, "items", dict, where) if "items" in data else {}
        items: dict[str, int] = {}
        for item_id, quantity in raw_items.items():
            if item_id not in item_defs:
                raise DataLoadError(f"{where}: unknown reward item '{item_id}'")
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
                raise DataLoadError(f"{where}: reward '{item_id}' must be an integer >= 1")
            items[item_id] = quantity
        return cls(_whole(data, "xp", where, 0), _whole(data, "skill_points", where, 0), items)


@dataclass(frozen=True)
class BossDef:
    id: str
    name: str
    max_health: int
    speed: float
    radius: int
    intro_time: float
    transition_time: float
    vulnerable_multiplier: float
    rewards: BossRewards
    cleave: CleaveDef
    charge: ChargeDef
    slam: SlamDef
    phases: tuple[PhaseDef, ...]

    def attack_def(self, name: str):
        return {"cleave": self.cleave, "charge": self.charge, "slam": self.slam}[name]

    def to_enemy_def(self) -> EnemyDef:
        """The plain-enemy view of this boss, so shooting/XP/events work unchanged."""
        return EnemyDef(
            id=self.id, name=self.name, type="boss", max_health=self.max_health,
            speed=self.speed, detection_range=800.0, attack_range=self.cleave.trigger_range,
            attack_damage=self.cleave.damage, attack_cooldown=self.cleave.cooldown,
            attack_windup=self.cleave.windup, search_time=0.0, xp_reward=self.rewards.xp,
            radius=self.radius, color=self.phases[0].color)

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> BossDef:
        max_health = require_field(data, "max_health", int, where)
        radius = require_field(data, "radius", int, where)
        if max_health <= 0 or radius <= 0:
            raise DataLoadError(f"{where}: max_health and radius must be > 0")

        attacks = require_field(data, "attacks", dict, where)
        for name in ATTACK_NAMES:
            if name not in attacks:
                raise DataLoadError(f"{where}: attacks.{name} is missing")
        cleave = CleaveDef.from_dict(require_field(attacks, "cleave", dict, where), where + ".attacks.cleave")
        charge = ChargeDef.from_dict(require_field(attacks, "charge", dict, where), where + ".attacks.charge")
        slam = SlamDef.from_dict(require_field(attacks, "slam", dict, where), where + ".attacks.slam")

        raw_phases = require_field(data, "phases", list, where)
        if not raw_phases:
            raise DataLoadError(f"{where}: 'phases' must not be empty")
        phases: list[PhaseDef] = []
        previous: float | None = None
        for index, raw in enumerate(raw_phases):
            phase_where = f"{where}.phases[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{phase_where}: must be an object")
            starts_at = float(require_field(raw, "starts_at", _NUMBER, phase_where))
            if index == 0 and starts_at != 1.0:
                raise DataLoadError(f"{phase_where}: the first phase must have starts_at 1.0")
            if not 0.0 < starts_at <= 1.0:
                raise DataLoadError(f"{phase_where}: starts_at must be between 0 and 1")
            if previous is not None and starts_at >= previous:
                raise DataLoadError(f"{phase_where}: phases need strictly descending starts_at values")
            previous = starts_at
            phase_attacks = require_field(raw, "attacks", list, phase_where)
            for name in phase_attacks:
                if name not in ATTACK_NAMES:
                    raise DataLoadError(f"{phase_where}: unknown attack '{name}'")
            color = require_field(raw, "color", list, phase_where)
            if len(color) != 3 or not all(isinstance(c, int) and not isinstance(c, bool)
                                          and 0 <= c <= 255 for c in color):
                raise DataLoadError(f"{phase_where}: field 'color' must be [r, g, b] integers 0-255")
            phases.append(PhaseDef(
                name=require_field(raw, "name", str, phase_where), starts_at=starts_at,
                speed_multiplier=_number(raw, "speed_multiplier", phase_where, 0.0, True),
                color=(color[0], color[1], color[2]), attacks=tuple(phase_attacks)))

        return cls(
            id=require_field(data, "id", str, where), name=require_field(data, "name", str, where),
            max_health=max_health, speed=_number(data, "speed", where, 0.0, True), radius=radius,
            intro_time=_number(data, "intro_time", where), transition_time=_number(data, "transition_time", where),
            vulnerable_multiplier=_number(data, "vulnerable_multiplier", where, 1.0),
            rewards=BossRewards.from_dict(require_field(data, "rewards", dict, where), item_defs,
                                          where + ".rewards"),
            cleave=cleave, charge=charge, slam=slam, phases=tuple(phases))


def load_boss_defs(item_defs: dict[str, ItemDef],
                   path: str = settings.BOSSES_FILE) -> dict[str, BossDef]:
    data = load_json(path)
    items = require_field(data, "bosses", list, path)
    bosses: dict[str, BossDef] = {}
    for index, raw in enumerate(items):
        where = f"{path}: bosses[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{where}: must be an object")
        boss = BossDef.from_dict(raw, item_defs, where)
        if boss.id in bosses:
            raise DataLoadError(f"{where}: duplicate id '{boss.id}'")
        bosses[boss.id] = boss
    return bosses


# ---------------------------------------------------------------- the boss itself
class BossMode(Enum):
    INTRO = "INTRO"              # introduction: invulnerable, standing still
    CHASE = "CHASE"              # walking at the player, deciding on an attack
    TELEGRAPH = "TELEGRAPH"      # wind-up: the danger zone is shown, then the attack lands
    CHARGE = "CHARGE"            # dashing in a straight line
    RECOVER = "RECOVER"          # worn out after a charge or slam: takes extra damage
    TRANSITION = "TRANSITION"    # roaring into the next phase: invulnerable


_ALPHA_SPRITES: dict[tuple, pygame.Surface] = {}


def _draw_alpha_circle(surface: pygame.Surface, color: tuple[int, int, int, int],
                       center: Vector2, radius: float) -> None:
    """A translucent filled circle. Sprites are cached by size so nothing is allocated per frame."""
    size = max(1, int(radius))
    key = (color, size)
    sprite = _ALPHA_SPRITES.get(key)
    if sprite is None:
        sprite = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        pygame.draw.circle(sprite, color, (size, size), size)
        _ALPHA_SPRITES[key] = sprite
    surface.blit(sprite, (center.x - size, center.y - size))


class Boss(Enemy):
    """A boss. It reuses Enemy for health, position and drawing helpers but has its own AI."""

    def __init__(self, boss_def: BossDef, position: tuple[float, float],
                 rng: random.Random | None = None) -> None:
        super().__init__(boss_def.to_enemy_def(), position)
        self.boss_def = boss_def
        self.rng = rng or random.Random()
        self.state = AIState.CHASE               # Enemy.state is only used for alive/dead here
        self.mode = BossMode.INTRO
        self.mode_timer = boss_def.intro_time
        self.phase_index = 0
        self.current_attack: str | None = None
        self.attack_direction = Vector2(1, 0)
        self.cooldowns = {name: 0.0 for name in ATTACK_NAMES}
        self.decision_timer = 0.0
        self.vulnerable = False
        self.charge_hit = False
        self.events: list[tuple[str, dict[str, Any]]] = []

    # ---- queries ----
    @property
    def phase(self) -> PhaseDef:
        return self.boss_def.phases[self.phase_index]

    @property
    def speed(self) -> float:
        return self.definition.speed * self.phase.speed_multiplier

    @property
    def health_fraction(self) -> float:
        return self.health / self.max_health

    @property
    def intro_progress(self) -> float:
        """0.0 -> 1.0 during the introduction, 1.0 afterwards."""
        if self.mode is not BossMode.INTRO or self.boss_def.intro_time <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self.mode_timer / self.boss_def.intro_time))

    def pop_events(self) -> list[tuple[str, dict[str, Any]]]:
        """Events (phase changes, stun, death) for the game to forward to the event bus."""
        events, self.events = self.events, []
        return events

    # ---- damage ----
    def take_damage(self, amount: int) -> bool:
        if self.is_dead or amount <= 0:
            return False
        if self.mode in (BossMode.INTRO, BossMode.TRANSITION):
            return False                         # shrugs off hits while introducing or roaring
        if self.vulnerable:
            amount = round(amount * self.boss_def.vulnerable_multiplier)
        if super().take_damage(amount):
            self.events.append(("BOSS_DEFEATED", {"id": self.boss_def.id, "name": self.boss_def.name}))
            return True
        new_phase = self._phase_for_health()
        if new_phase > self.phase_index:
            self.phase_index = new_phase
            self.current_attack = None
            self._enter(BossMode.TRANSITION, self.boss_def.transition_time)
            self.events.append(("BOSS_PHASE_CHANGED", {
                "id": self.boss_def.id, "name": self.boss_def.name,
                "phase": new_phase + 1, "phase_name": self.phase.name}))
        return False

    def _phase_for_health(self) -> int:
        fraction = self.health_fraction
        index = 0
        for i, phase in enumerate(self.boss_def.phases):
            if fraction <= phase.starts_at + 1e-9:
                index = i
        return index

    # ---- AI ----
    def update(self, dt: float, target: Vector2, target_valid: bool,
               walls: Sequence[pygame.Rect]) -> int:
        """Advance the fight. Returns damage dealt to the target this frame."""
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.is_dead:
            self.death_timer -= dt
            return 0
        for name in self.cooldowns:
            self.cooldowns[name] = max(0.0, self.cooldowns[name] - dt)
        self.decision_timer = max(0.0, self.decision_timer - dt)
        if not target_valid:
            return 0                              # nobody to fight (the player is dead)
        self.mode_timer -= dt

        if self.mode is BossMode.INTRO:
            self._face(target)
            if self.mode_timer <= 0:
                self._enter(BossMode.CHASE)
        elif self.mode is BossMode.TRANSITION:
            if self.mode_timer <= 0:
                self._enter(BossMode.CHASE)
        elif self.mode is BossMode.RECOVER:
            if self.mode_timer <= 0:
                self._enter(BossMode.CHASE)
        elif self.mode is BossMode.TELEGRAPH:
            if self.mode_timer <= 0:
                return self._execute_attack(target)
        elif self.mode is BossMode.CHARGE:
            return self._update_charge(dt, target, walls)
        else:
            self._update_chase(dt, target, walls)
        return 0

    def _enter(self, mode: BossMode, seconds: float = 0.0) -> None:
        self.mode = mode
        self.mode_timer = seconds
        self.vulnerable = False

    def _update_chase(self, dt: float, target: Vector2, walls: Sequence[pygame.Rect]) -> None:
        self._face(target)
        distance = self.position.distance_to(target)
        if self.decision_timer <= 0:
            attack = self._choose_attack(distance)
            if attack is not None:
                self._begin_attack(attack, target)
                return
        if distance > self.radius + PLAYER_HALF + 4:
            self._step(self.facing, self.speed, dt, walls)

    def _choose_attack(self, distance: float) -> str | None:
        allowed = self.phase.attacks
        options: list[str] = []
        if "cleave" in allowed and self.cooldowns["cleave"] <= 0 \
                and distance <= self.boss_def.cleave.trigger_range:
            options.append("cleave")
        if "charge" in allowed and self.cooldowns["charge"] <= 0 \
                and distance >= self.boss_def.charge.min_distance:
            options.append("charge")
        if "slam" in allowed and self.cooldowns["slam"] <= 0 \
                and distance <= self.boss_def.slam.trigger_range:
            options.append("slam")
        return self.rng.choice(options) if options else None

    def _begin_attack(self, name: str, target: Vector2) -> None:
        offset = target - self.position
        if offset.length_squared() > 0:
            self.attack_direction = offset.normalize()
        self.facing = Vector2(self.attack_direction)       # aim is locked: the player can dodge
        attack = self.boss_def.attack_def(name)
        self.cooldowns[name] = attack.cooldown
        self.current_attack = name
        self.charge_hit = False
        self._enter(BossMode.TELEGRAPH, attack.windup)

    def _execute_attack(self, target: Vector2) -> int:
        name = self.current_attack
        damage = 0
        if name == "cleave":
            cleave = self.boss_def.cleave
            spot = self.position + self.attack_direction * cleave.reach
            if target.distance_to(spot) <= cleave.radius + PLAYER_HALF:
                damage = cleave.damage
            self.current_attack = None
            self._enter(BossMode.CHASE)
            self.decision_timer = CLEAVE_PAUSE
        elif name == "slam":
            slam = self.boss_def.slam
            if target.distance_to(self.position) <= slam.radius + PLAYER_HALF:
                damage = slam.damage
            self.current_attack = None
            self._enter(BossMode.RECOVER, slam.recover)
            self.vulnerable = True                           # a slam leaves him exposed
        elif name == "charge":
            self._enter(BossMode.CHARGE, self.boss_def.charge.max_duration)
        return damage

    def _update_charge(self, dt: float, target: Vector2, walls: Sequence[pygame.Rect]) -> int:
        charge = self.boss_def.charge
        blocked = self._step(self.attack_direction, charge.speed, dt, walls)
        damage = 0
        if not self.charge_hit and self.position.distance_to(target) <= self.radius + PLAYER_HALF:
            self.charge_hit = True
            damage = charge.damage
        if blocked:
            self._end_charge(charge.wall_recover, crashed=True)
        elif self.mode_timer <= 0:
            self._end_charge(charge.recover, crashed=False)
        return damage

    def _end_charge(self, recover_time: float, crashed: bool) -> None:
        self.current_attack = None
        self._enter(BossMode.RECOVER, recover_time)
        self.vulnerable = True                               # the weak point: a spent charge
        if crashed:
            self.events.append(("BOSS_STUNNED", {"id": self.boss_def.id, "name": self.boss_def.name}))

    def _step(self, direction: Vector2, speed: float, dt: float,
              walls: Sequence[pygame.Rect]) -> bool:
        """Move with wall collision. Returns True if a wall stopped the movement."""
        step = direction * speed * dt
        blocked = False
        if step.x != 0:
            self.position.x += step.x
            self._sync_rect()
            if collide_axis(self.rect, walls, "x", step.x):
                self.position.x = self.rect.centerx
                blocked = True
        if step.y != 0:
            self.position.y += step.y
            self._sync_rect()
            if collide_axis(self.rect, walls, "y", step.y):
                self.position.y = self.rect.centery
                blocked = True
        self._clamp_to_world()
        return blocked

    # ---- drawing ----
    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        center = camera.world_to_screen(self.position)
        r = self.radius
        if self.is_dead:                                     # shrinking dark corpse
            fade = max(0.0, self.death_timer / settings.ENEMY_CORPSE_TIME)
            pygame.draw.circle(surface, (36, 40, 46), center, max(2, int(r * (0.4 + 0.6 * fade))))
            return

        self._draw_telegraph(surface, center)
        body = (255, 255, 255) if self.hit_flash > 0 else self.phase.color
        pygame.draw.circle(surface, body, center, r)
        outline = (255, 230, 90) if self.vulnerable else (20, 24, 32)
        pygame.draw.circle(surface, outline, center, r, 4)
        pygame.draw.line(surface, (205, 205, 215), center + self.facing * (r * 0.6),
                         center + self.facing * (r + 22), 7)          # the cleaver
        pygame.draw.circle(surface, settings.COLOR_ACCENT, center + self.facing * (r * 0.35), 5)
        if self.mode is BossMode.TRANSITION:
            pulse = int(r + 10 + (self.mode_timer * 40) % 14)
            pygame.draw.circle(surface, settings.COLOR_ACCENT, center, pulse, 3)

    def _draw_telegraph(self, surface: pygame.Surface, center: Vector2) -> None:
        """Show where the next attack will land, so the player can dodge it."""
        if self.mode is not BossMode.TELEGRAPH or self.current_attack is None:
            return
        attack = self.boss_def.attack_def(self.current_attack)
        progress = 1.0 - max(0.0, self.mode_timer) / attack.windup
        danger = (255, 90, 60)
        if self.current_attack == "cleave":
            spot = center + self.attack_direction * attack.reach
            _draw_alpha_circle(surface, (255, 60, 40, 80), spot, attack.radius)
            pygame.draw.circle(surface, danger, spot, max(1, int(attack.radius * progress)), 3)
        elif self.current_attack == "slam":
            _draw_alpha_circle(surface, (255, 60, 40, 60), center, attack.radius)
            pygame.draw.circle(surface, danger, center, max(1, int(attack.radius * progress)), 3)
        else:                                                # charge: show the whole lane
            end = center + self.attack_direction * (attack.speed * attack.max_duration)
            pygame.draw.line(surface, danger, center, end, 2 + int(progress * 6))

    def draw_debug(self, surface: pygame.Surface, camera: Camera, font: pygame.font.Font) -> None:
        center = camera.world_to_screen(self.position)
        label = font.render(f"{self.mode.value}  PHASE {self.phase_index + 1}", True, (255, 255, 255))
        surface.blit(label, (center.x - label.get_width() / 2, center.y - self.radius - 22))