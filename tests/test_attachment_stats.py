import random

import pytest
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.core.event_bus import EventBus
from src.world.effects_manager import EffectsManager
from tests.factories import make_enemy, make_weapon


def test_modifiers_scale_the_stats_and_respect_their_floors():
    weapon = make_weapon(spread=2.0, range=500.0, fire_rate=4.0)
    weapon.modifiers = {"range": 0.2, "spread": -0.5, "fire_rate": 0.25, "recoil": -0.4}
    assert weapon.range == pytest.approx(600) and weapon.spread == pytest.approx(1.0)
    assert weapon.fire_rate == pytest.approx(5.0) and weapon.recoil == pytest.approx(0.6)
    weapon.modifiers = {"range": -5.0, "spread": -5.0, "fire_rate": -5.0, "recoil": -5.0}
    assert weapon.range == pytest.approx(125) and weapon.spread == 0.0
    assert weapon.fire_rate == pytest.approx(1.0) and weapon.recoil == 0.0


def test_a_faster_fire_rate_shortens_the_cooldown():
    weapon = make_weapon(fire_rate=4.0)
    weapon.modifiers = {"fire_rate": 1.0}
    weapon.fire()
    assert weapon.cooldown == pytest.approx(1 / 8)


def test_the_modified_range_decides_what_a_shot_can_hit():
    def hits(range_modifier: float, distance: float) -> bool:
        enemy = make_enemy((distance, 0), max_health=200)
        weapon = make_weapon(spread=0, range=500.0)
        weapon.modifiers = {"range": range_modifier}
        CombatSystem(rng=random.Random(1)).fire_weapon(
            Vector2(0, 0), Vector2(1, 0), weapon, [enemy], [])
        return enemy.health < 200

    assert hits(0.0, 400) is True
    assert hits(-0.5, 400) is False
    assert hits(1.0, 800) is True


def test_shots_report_their_recoil():
    bus, shots = EventBus(), []
    bus.on("SHOT_FIRED", shots.append)
    weapon = make_weapon(spread=0)
    weapon.modifiers = {"recoil": -0.4}
    CombatSystem(bus, random.Random(1)).fire_weapon(Vector2(0, 0), Vector2(1, 0), weapon, [], [])
    assert shots[0]["recoil"] == pytest.approx(0.6)


def test_recoil_scales_the_screen_shake():
    bus = EventBus()
    effects = EffectsManager(bus, 320, 180, rng=random.Random(1))
    bus.emit("SHOT_FIRED", {"weapon": "x", "origin": (0, 0), "direction": (1, 0), "recoil": 0.0})
    assert effects.shake.trauma == 0.0
    bus.emit("SHOT_FIRED", {"weapon": "x", "origin": (0, 0), "direction": (1, 0), "recoil": 1.0})
    assert effects.shake.trauma == pytest.approx(0.10)