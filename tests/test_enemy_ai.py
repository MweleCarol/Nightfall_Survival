import pygame
from pygame import Vector2

from src.enemies.enemy import AIState
from tests.factories import make_enemy


def run(enemy, target, steps, dt=0.1, valid=True, walls=()):
    """Update the enemy repeatedly; return total damage dealt."""
    total = 0
    for _ in range(steps):
        total += enemy.update(dt, target, valid, list(walls))
    return total


def test_idle_enemy_ignores_distant_player():
    e = make_enemy((100, 100))
    run(e, Vector2(1100, 100), 5)
    assert e.state is AIState.IDLE
    assert e.position == Vector2(100, 100)


def test_enemy_detects_player_in_range_and_chases():
    e = make_enemy((100, 100))
    e.update(0.1, Vector2(400, 100), True, [])
    assert e.state is AIState.CHASE
    assert e.position.x > 100


def test_chase_reduces_distance():
    e = make_enemy((100, 100))
    target = Vector2(400, 100)
    before = e.position.distance_to(target)
    run(e, target, 5)
    assert e.position.distance_to(target) < before


def test_attack_has_windup_then_cooldown():
    e = make_enemy((100, 100))
    target = Vector2(130, 100)               # already inside attack range
    hits = []
    for step in range(1, 40):
        if e.update(0.1, target, True, []):
            hits.append(step * 0.1)
    assert len(hits) >= 2
    assert 0.4 - 1e-9 <= hits[0] <= 0.8      # not instant: wind-up first
    assert 1.1 <= hits[1] - hits[0] <= 1.5   # then roughly one cooldown apart


def test_attack_damage_value():
    e = make_enemy((100, 100), attack_damage=10)
    assert run(e, Vector2(130, 100), 8) == 10


def test_invalid_target_makes_enemy_idle_and_harmless():
    e = make_enemy((100, 100))
    target = Vector2(130, 100)
    run(e, target, 8)
    assert e.state is AIState.ATTACK
    damage = run(e, target, 10, valid=False)
    assert e.state is AIState.IDLE and damage == 0


def test_enemy_loses_interest_then_returns_to_idle():
    e = make_enemy((100, 100))
    e.update(0.1, Vector2(400, 100), True, [])
    assert e.state is AIState.CHASE
    far = Vector2(5000, 100)
    e.update(0.1, far, True, [])
    assert e.state is AIState.SEARCH
    for _ in range(200):
        e.update(0.1, far, True, [])
    assert e.state is AIState.IDLE


def test_shot_from_afar_wakes_idle_enemy():
    e = make_enemy((100, 100))
    far = Vector2(1100, 100)
    e.update(0.1, far, True, [])
    assert e.state is AIState.IDLE
    e.take_damage(1)
    e.update(0.1, far, True, [])
    assert e.state is not AIState.IDLE


def test_death_and_cleanup():
    e = make_enemy((100, 100), max_health=60)
    assert e.take_damage(60) is True
    assert e.state is AIState.DEAD
    assert e.take_damage(10) is False
    assert e.update(0.1, Vector2(110, 100), True, []) == 0
    assert not e.is_removable
    e.update(1.0, Vector2(110, 100), True, [])
    assert e.is_removable


def test_enemy_is_blocked_by_walls():
    wall = pygame.Rect(100, -50, 20, 100)
    e = make_enemy((50, 0))
    run(e, Vector2(300, 0), 60, walls=[wall])
    assert e.rect.right <= wall.left


def test_wave_multipliers_scale_stats():
    e = make_enemy((100, 100), health_multiplier=2.0, damage_multiplier=2.0)
    assert e.max_health == 120 and e.attack_damage == 20