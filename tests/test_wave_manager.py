import random

import pygame
import pytest

from src.core import settings
from src.core.event_bus import EventBus
from src.enemies.enemy import load_enemy_defs
from src.enemies.factory import EnemyFactory
from src.services.data_loader import DataLoadError
from src.systems.wave_manager import (
    EnemyChoice, WaveConfig, WaveManager, WaveState,
    damage_multiplier, enemy_count, health_multiplier, load_wave_config,
)
from tests.factories import make_enemy_def

ZONES = [pygame.Rect(100, 100, 200, 80), pygame.Rect(1000, 1000, 200, 80)]


def make_config(**overrides) -> WaveConfig:
    values = dict(
        waves_per_night=3, base_count=4, count_growth=2.0, wave_growth=2.0,
        health_growth=0.15, damage_growth=0.1, first_wave_delay=5.0,
        wave_delay=10.0, spawn_delay=1.0, max_alive=20,
        enemies=(EnemyChoice("walker", 100.0, 1), EnemyChoice("stalker", 30.0, 2)),
    )
    values.update(overrides)
    return WaveConfig(**values)


def make_factory() -> EnemyFactory:
    return EnemyFactory({
        "walker": make_enemy_def(id="walker"),
        "stalker": make_enemy_def(id="stalker", type="stalker"),
    })


def make_manager(config=None, bus=None) -> WaveManager:
    return WaveManager(config or make_config(), make_factory(), ZONES,
                       event_bus=bus, rng=random.Random(1))


def valid_data(**overrides) -> dict:
    data = {
        "waves_per_night": 3, "base_count": 4, "count_growth": 2, "wave_growth": 2,
        "health_growth": 0.15, "damage_growth": 0.1, "first_wave_delay": 8,
        "wave_delay": 12, "spawn_delay": 1.2, "max_alive": 20,
        "enemies": [{"id": "walker", "weight": 100, "min_night": 1}],
    }
    data.update(overrides)
    return data


def test_enemy_count_formula():
    config = make_config()
    assert enemy_count(config, 1, 1) == 4
    assert enemy_count(config, 2, 3) == 10        # 4 + 1*2 + 2*2


def test_multipliers_scale_with_the_night():
    config = make_config()
    assert health_multiplier(config, 1) == 1.0 and damage_multiplier(config, 1) == 1.0
    assert abs(health_multiplier(config, 3) - 1.3) < 1e-9


def test_start_night_enters_intermission():
    manager = make_manager()
    assert manager.state is WaveState.IDLE
    manager.start_night(1)
    assert manager.state is WaveState.INTERMISSION
    assert manager.night == 1 and manager.wave == 0


def test_first_wave_starts_after_the_delay_and_emits_an_event():
    bus, events = EventBus(), []
    bus.on("WAVE_STARTED", events.append)
    manager = make_manager(bus=bus)
    manager.start_night(1)
    manager.update(4.9, 0)
    assert manager.state is WaveState.INTERMISSION
    manager.update(0.2, 0)
    assert manager.state is WaveState.SPAWNING
    assert events == [{"night": 1, "wave": 1, "total": 4}]


def test_spawning_is_paced():
    manager = make_manager()
    manager.start_night(1)
    manager.update(5.0, 0)                        # the wave begins
    assert len(manager.update(0.0, 0)) == 1       # first enemy right away
    assert len(manager.update(0.5, 0)) == 0
    assert len(manager.update(0.5, 0)) == 1


def test_a_full_night_spawns_every_wave_and_completes():
    bus, seen = EventBus(), []
    for name in ("WAVE_COMPLETED", "NIGHT_CLEARED"):
        bus.on(name, lambda data, name=name: seen.append(name))
    manager = make_manager(bus=bus)
    manager.start_night(1)
    total = 0
    for _ in range(2000):
        total += len(manager.update(0.5, 0))
        if manager.state is WaveState.COMPLETE:
            break
    assert manager.state is WaveState.COMPLETE
    assert total == 4 + 6 + 8
    assert seen == ["WAVE_COMPLETED"] * 3 + ["NIGHT_CLEARED"]


def test_alive_cap_blocks_spawning():
    manager = make_manager(make_config(max_alive=2))
    manager.start_night(1)
    manager.update(5.0, 0)
    assert manager.update(0.0, 2) == []
    assert len(manager.update(0.0, 1)) == 1


def test_spawned_enemies_hunt_scale_and_appear_in_zones():
    manager = make_manager()
    manager.start_night(3)
    manager.update(5.0, 0)
    enemies = []
    for _ in range(30):
        enemies += manager.update(0.5, 0)
    assert enemies
    for enemy in enemies:
        assert enemy.relentless
        assert any(zone.collidepoint(enemy.position) for zone in ZONES)
        assert enemy.max_health == round(60 * health_multiplier(make_config(), 3))


def test_enemy_types_respect_min_night():
    config = make_config(base_count=30, count_growth=0, max_alive=100)

    def spawn_for_night(night: int) -> list:
        manager = make_manager(config)
        manager.start_night(night)
        manager.update(5.0, 0)
        out = []
        for _ in range(100):
            out += manager.update(1.0, 0)
        return out

    assert all(e.definition.id == "walker" for e in spawn_for_night(1))
    assert any(e.definition.id == "stalker" for e in spawn_for_night(2))


def test_end_night_resets_the_manager():
    manager = make_manager()
    manager.start_night(1)
    manager.update(5.0, 0)
    manager.end_night()
    assert manager.state is WaveState.IDLE
    assert manager.update(1.0, 0) == []


def test_config_rejects_unknown_enemy():
    data = valid_data(enemies=[{"id": "dragon", "weight": 1, "min_night": 1}])
    with pytest.raises(DataLoadError, match="dragon"):
        WaveConfig.from_dict(data, {"walker"}, "test")


def test_config_needs_an_enemy_available_on_night_one():
    data = valid_data(enemies=[{"id": "walker", "weight": 1, "min_night": 2}])
    with pytest.raises(DataLoadError, match="night 1"):
        WaveConfig.from_dict(data, {"walker"}, "test")


def test_shipped_waves_reference_real_enemies():
    config = load_wave_config(settings.WAVES_FILE, set(load_enemy_defs()))
    assert config.enemies and config.waves_per_night >= 1


def test_all_shipped_enemies_can_be_built():
    factory = EnemyFactory()
    for enemy_id in factory.definitions:
        enemy = factory.create(enemy_id, (500, 500))
        assert enemy.health == enemy.definition.max_health