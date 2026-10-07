import random

from pygame import Vector2

from src.combat.combat_system import CombatSystem
from tests.factories import make_enemy, make_weapon


def test_damage_modifier_increases_damage():
    weapon = make_weapon(damage=25)
    weapon.modifiers = {"damage": 0.2}
    assert weapon.damage == 30


def test_magazine_modifier_increases_the_reload_fill():
    weapon = make_weapon(loaded=0, reserve=30, magazine_size=12)
    weapon.modifiers = {"magazine": 3}
    weapon.start_reload()
    weapon.update(1.5)
    assert weapon.magazine_size == 15 and weapon.loaded == 15


def test_reload_modifier_shortens_the_reload():
    weapon = make_weapon(reload_time=1.5)
    weapon.modifiers = {"reload": 0.2}
    assert abs(weapon.reload_time - 1.2) < 1e-9


def test_reload_time_has_a_floor():
    weapon = make_weapon(reload_time=2.0)
    weapon.modifiers = {"reload": 5.0}
    assert abs(weapon.reload_time - 0.5) < 1e-9


def test_modified_damage_reaches_the_enemy():
    enemy = make_enemy((200, 0), max_health=100)
    weapon = make_weapon(damage=25, spread=0)
    weapon.modifiers = {"damage": 0.2}
    CombatSystem(rng=random.Random(1)).fire_weapon(Vector2(0, 0), Vector2(1, 0), weapon, [enemy], [])
    assert enemy.health == 70


def test_critical_hit_doubles_damage():
    enemy = make_enemy((200, 0), max_health=100)
    weapon = make_weapon(damage=25, spread=0)
    CombatSystem(rng=random.Random(1)).fire_weapon(
        Vector2(0, 0), Vector2(1, 0), weapon, [enemy], [], crit_chance=1.0)
    assert enemy.health == 50