import random

import pygame
import pytest
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.core import settings
from src.core.event_bus import EventBus
from tests.factories import make_enemy, make_weapon

ORIGIN, RIGHT = Vector2(0, 0), Vector2(1, 0)


def setup(*names):
    bus = EventBus()
    logs = {name: [] for name in names}
    for name in names:
        bus.on(name, logs[name].append)
    return CombatSystem(event_bus=bus, rng=random.Random(1)), logs


def test_shot_event_reports_the_muzzle_and_direction():
    combat, logs = setup("SHOT_FIRED")
    combat.fire_weapon(ORIGIN, RIGHT, make_weapon(spread=0), [], [])
    event = logs["SHOT_FIRED"][0]
    assert event["origin"] == pytest.approx((settings.MUZZLE_OFFSET, 0))
    assert event["direction"] == pytest.approx((1, 0))


def test_hitting_an_enemy_reports_where_and_how_hard():
    combat, logs = setup("ENEMY_HIT", "SHOT_IMPACT")
    combat.fire_weapon(ORIGIN, RIGHT, make_weapon(spread=0), [make_enemy((200, 0))], [])
    hit = logs["ENEMY_HIT"][0]
    assert hit["damage"] == 25 and hit["critical"] is False
    assert hit["position"][0] == pytest.approx(184)
    assert logs["SHOT_IMPACT"] == []


def test_hitting_a_wall_reports_an_impact_there():
    combat, logs = setup("ENEMY_HIT", "SHOT_IMPACT")
    wall = pygame.Rect(100, -50, 20, 100)
    combat.fire_weapon(ORIGIN, RIGHT, make_weapon(spread=0), [], [wall])
    assert logs["SHOT_IMPACT"][0]["position"][0] == pytest.approx(100)
    assert logs["ENEMY_HIT"] == []


def test_a_shot_into_open_air_reports_no_impact():
    combat, logs = setup("ENEMY_HIT", "SHOT_IMPACT")
    combat.fire_weapon(ORIGIN, RIGHT, make_weapon(spread=0), [], [])
    assert logs["ENEMY_HIT"] == [] and logs["SHOT_IMPACT"] == []