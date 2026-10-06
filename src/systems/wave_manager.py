"""Night waves: what spawns, when, and how strong (data-driven, LLD section 12)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

import pygame

from src.core import settings
from src.core.event_bus import EventBus
from src.enemies.enemy import Enemy
from src.enemies.factory import EnemyFactory
from src.services.data_loader import DataLoadError, load_json, require_field

_NUMBER = (int, float)


def _number(data: dict, key: str, where: str, minimum: float = 0.0,
            exclusive: bool = False) -> float:
    value = float(require_field(data, key, _NUMBER, where))
    if value < minimum or (exclusive and value == minimum):
        raise DataLoadError(
            f"{where}: field '{key}' must be {'>' if exclusive else '>='} {minimum:g}")
    return value


@dataclass(frozen=True)
class EnemyChoice:
    enemy_id: str
    weight: float
    min_night: int


@dataclass(frozen=True)
class WaveConfig:
    waves_per_night: int
    base_count: float
    count_growth: float      # extra enemies per night
    wave_growth: float       # extra enemies per later wave within a night
    health_growth: float     # health multiplier added per night
    damage_growth: float
    first_wave_delay: float
    wave_delay: float
    spawn_delay: float
    max_alive: int
    enemies: tuple[EnemyChoice, ...]

    @classmethod
    def from_dict(cls, data: dict, known_enemy_ids: set[str], where: str) -> WaveConfig:
        waves = require_field(data, "waves_per_night", int, where)
        max_alive = require_field(data, "max_alive", int, where)
        if waves < 1 or max_alive < 1:
            raise DataLoadError(f"{where}: waves_per_night and max_alive must be >= 1")

        raw = require_field(data, "enemies", list, where)
        if not raw:
            raise DataLoadError(f"{where}: 'enemies' must not be empty")
        choices: list[EnemyChoice] = []
        for index, item in enumerate(raw):
            item_where = f"{where}: enemies[{index}]"
            if not isinstance(item, dict):
                raise DataLoadError(f"{item_where}: must be an object")
            enemy_id = require_field(item, "id", str, item_where)
            if enemy_id not in known_enemy_ids:
                raise DataLoadError(f"{item_where}: unknown enemy '{enemy_id}'")
            weight = _number(item, "weight", item_where, 0.0, exclusive=True)
            min_night = require_field(item, "min_night", int, item_where)
            if min_night < 1:
                raise DataLoadError(f"{item_where}: field 'min_night' must be >= 1")
            choices.append(EnemyChoice(enemy_id, weight, min_night))
        if not any(choice.min_night <= 1 for choice in choices):
            raise DataLoadError(f"{where}: at least one enemy must be available on night 1")

        return cls(
            waves_per_night=waves,
            base_count=_number(data, "base_count", where, 1.0),
            count_growth=_number(data, "count_growth", where),
            wave_growth=_number(data, "wave_growth", where),
            health_growth=_number(data, "health_growth", where),
            damage_growth=_number(data, "damage_growth", where),
            first_wave_delay=_number(data, "first_wave_delay", where),
            wave_delay=_number(data, "wave_delay", where),
            spawn_delay=_number(data, "spawn_delay", where, 0.0, exclusive=True),
            max_alive=max_alive,
            enemies=tuple(choices),
        )


def load_wave_config(path: str, known_enemy_ids: set[str]) -> WaveConfig:
    return WaveConfig.from_dict(load_json(path), known_enemy_ids, path)


# ---- difficulty formulas (pure functions, easy to test and balance) ----
def enemy_count(config: WaveConfig, night: int, wave: int) -> int:
    count = config.base_count + (night - 1) * config.count_growth + (wave - 1) * config.wave_growth
    return max(1, round(count))


def health_multiplier(config: WaveConfig, night: int) -> float:
    return 1.0 + (night - 1) * config.health_growth


def damage_multiplier(config: WaveConfig, night: int) -> float:
    return 1.0 + (night - 1) * config.damage_growth


class WaveState(Enum):
    IDLE = "IDLE"                    # daytime: nothing happening
    INTERMISSION = "INTERMISSION"    # counting down to the next wave
    SPAWNING = "SPAWNING"            # enemies are trickling in
    ACTIVE = "ACTIVE"                # all spawned; waiting for the player to clear them
    COMPLETE = "COMPLETE"            # every wave of the night cleared


class WaveManager:
    def __init__(self, config: WaveConfig, factory: EnemyFactory,
                 spawn_zones: Sequence[pygame.Rect], event_bus: EventBus | None = None,
                 rng: random.Random | None = None) -> None:
        if not spawn_zones:
            raise ValueError("WaveManager needs at least one spawn zone")
        self.config = config
        self.factory = factory
        self.spawn_zones = list(spawn_zones)
        self.event_bus = event_bus
        self.rng = rng or random.Random()
        self.state = WaveState.IDLE
        self.night = 0
        self.wave = 0
        self.remaining_to_spawn = 0
        self._timer = 0.0

    @property
    def seconds_until_next_wave(self) -> float:
        return max(0.0, self._timer) if self.state is WaveState.INTERMISSION else 0.0

    # ---- lifecycle ----
    def start_night(self, night: int) -> None:
        self.night = night
        self.wave = 0
        self.remaining_to_spawn = 0
        self.state = WaveState.INTERMISSION
        self._timer = self.config.first_wave_delay

    def end_night(self) -> None:
        self.state = WaveState.IDLE
        self.wave = 0
        self.remaining_to_spawn = 0

    def update(self, dt: float, alive_count: int) -> list[Enemy]:
        """Advance the wave logic. Returns enemies that spawned this frame."""
        spawned: list[Enemy] = []

        if self.state is WaveState.INTERMISSION:
            self._timer -= dt
            if self._timer <= 0:
                self._begin_wave()

        elif self.state is WaveState.SPAWNING:
            self._timer -= dt
            while (self._timer <= 0 and self.remaining_to_spawn > 0
                   and alive_count + len(spawned) < self.config.max_alive):
                spawned.append(self._spawn_one())
                self.remaining_to_spawn -= 1
                self._timer += self.config.spawn_delay
            if self.remaining_to_spawn == 0:
                self.state = WaveState.ACTIVE
            elif self._timer < 0:
                self._timer = 0.0          # blocked by the alive cap: don't build up a burst

        elif self.state is WaveState.ACTIVE:
            if alive_count == 0:
                self._finish_wave()

        return spawned

    # ---- internals ----
    def _begin_wave(self) -> None:
        self.wave += 1
        self.remaining_to_spawn = enemy_count(self.config, self.night, self.wave)
        self.state = WaveState.SPAWNING
        self._timer = 0.0
        self._emit("WAVE_STARTED", {"night": self.night, "wave": self.wave,
                                    "total": self.remaining_to_spawn})

    def _finish_wave(self) -> None:
        self._emit("WAVE_COMPLETED", {"night": self.night, "wave": self.wave})
        if self.wave >= self.config.waves_per_night:
            self.state = WaveState.COMPLETE
            self._emit("NIGHT_CLEARED", {"night": self.night})
        else:
            self.state = WaveState.INTERMISSION
            self._timer = self.config.wave_delay

    def _spawn_one(self) -> Enemy:
        eligible = [c for c in self.config.enemies if c.min_night <= self.night]
        choice = self.rng.choices(eligible, weights=[c.weight for c in eligible])[0]
        zone = self.rng.choice(self.spawn_zones)
        position = (self.rng.randint(zone.left, zone.right - 1),
                    self.rng.randint(zone.top, zone.bottom - 1))
        enemy = self.factory.create(
            choice.enemy_id, position,
            health_multiplier(self.config, self.night),
            damage_multiplier(self.config, self.night))
        enemy.relentless = True
        return enemy

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)