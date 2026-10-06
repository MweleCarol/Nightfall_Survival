import random

import pygame
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.core.event_bus import EventBus
from tests.factories import make_enemy, make_weapon

ORIGIN, RIGHT = Vector2(0, 0), Vector2(1, 0)


def test_shot_damages_enemy_in_line():
    enemy, weapon = make_enemy((200, 0)), make_weapon(spread=0)
    cs = CombatSystem(rng=random.Random(1))
    assert cs.fire_weapon(ORIGIN, RIGHT, weapon, [enemy], []) is True
    assert enemy.health == enemy.max_health - 25


def test_shot_misses_enemy_off_line_but_spends_ammo():
    enemy, weapon = make_enemy((200, 100)), make_weapon(spread=0)
    cs = CombatSystem(rng=random.Random(1))
    assert cs.fire_weapon(ORIGIN, RIGHT, weapon, [enemy], []) is True
    assert enemy.health == enemy.max_health and weapon.loaded == 11


def test_empty_weapon_does_not_fire():
    weapon = make_weapon(loaded=0)
    cs = CombatSystem(rng=random.Random(1))
    assert cs.fire_weapon(ORIGIN, RIGHT, weapon, [], []) is False
    assert cs.tracers == []


def test_wall_blocks_damage():
    enemy, weapon = make_enemy((200, 0)), make_weapon(spread=0)
    wall = pygame.Rect(100, -50, 20, 100)
    CombatSystem(rng=random.Random(1)).fire_weapon(ORIGIN, RIGHT, weapon, [enemy], [wall])
    assert enemy.health == enemy.max_health


def test_kill_emits_enemy_died_once():
    bus, died = EventBus(), []
    bus.on("ENEMY_DIED", died.append)
    enemy, weapon = make_enemy((200, 0), max_health=25), make_weapon(spread=0)
    cs = CombatSystem(event_bus=bus, rng=random.Random(1))
    cs.fire_weapon(ORIGIN, RIGHT, weapon, [enemy], [])
    weapon.update(0.25)
    cs.fire_weapon(ORIGIN, RIGHT, weapon, [enemy], [])   # shooting a corpse does nothing
    assert len(died) == 1 and died[0]["xp"] == enemy.xp_reward


def test_tracer_created_then_expires():
    weapon = make_weapon(spread=0)
    cs = CombatSystem(rng=random.Random(1))
    cs.fire_weapon(ORIGIN, RIGHT, weapon, [], [])
    assert len(cs.tracers) == 1
    cs.update(1.0)
    assert cs.tracers == []