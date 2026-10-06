import random

import pygame
from pygame import Vector2

from src.combat.hitscan import apply_spread, cast_ray, ray_circle_distance, ray_rect_distance
from tests.factories import make_enemy

RIGHT = Vector2(1, 0)
ORIGIN = Vector2(0, 0)


def test_ray_hits_rect_at_expected_distance():
    assert ray_rect_distance(ORIGIN, RIGHT, pygame.Rect(100, -10, 50, 20), 500) == 100


def test_ray_rect_beyond_range():
    assert ray_rect_distance(ORIGIN, RIGHT, pygame.Rect(100, -10, 50, 20), 50) is None


def test_ray_rect_behind_origin():
    assert ray_rect_distance(Vector2(300, 0), RIGHT, pygame.Rect(100, -10, 50, 20), 500) is None


def test_ray_rect_parallel_miss():
    assert ray_rect_distance(Vector2(0, 50), RIGHT, pygame.Rect(100, -10, 50, 20), 500) is None


def test_ray_circle_hit_distance():
    d = ray_circle_distance(ORIGIN, RIGHT, Vector2(100, 0), 10, 500)
    assert abs(d - 90) < 1e-6


def test_ray_circle_miss():
    assert ray_circle_distance(ORIGIN, RIGHT, Vector2(100, 20), 10, 500) is None


def test_ray_circle_behind():
    assert ray_circle_distance(ORIGIN, RIGHT, Vector2(-100, 0), 10, 500) is None


def test_ray_circle_origin_inside():
    assert ray_circle_distance(ORIGIN, RIGHT, Vector2(5, 0), 10, 500) == 0.0


def test_ray_circle_out_of_range():
    assert ray_circle_distance(ORIGIN, RIGHT, Vector2(600, 0), 10, 500) is None


def test_cast_ray_hits_enemy():
    enemy = make_enemy((200, 0))
    hit = cast_ray(ORIGIN, RIGHT, 500, [enemy], [])
    assert hit.enemy is enemy
    assert abs(hit.distance - 184) < 1e-6


def test_cast_ray_wall_blocks_enemy():
    enemy = make_enemy((200, 0))
    wall = pygame.Rect(100, -50, 20, 100)
    hit = cast_ray(ORIGIN, RIGHT, 500, [enemy], [wall])
    assert hit.enemy is None and hit.distance == 100


def test_cast_ray_picks_nearest_enemy():
    far, near = make_enemy((300, 0)), make_enemy((150, 0))
    assert cast_ray(ORIGIN, RIGHT, 500, [far, near], []).enemy is near


def test_cast_ray_ignores_dead_enemies():
    enemy = make_enemy((200, 0))
    enemy.take_damage(999)
    assert cast_ray(ORIGIN, RIGHT, 500, [enemy], []).enemy is None


def test_cast_ray_respects_range():
    enemy = make_enemy((600, 0))
    hit = cast_ray(ORIGIN, RIGHT, 500, [enemy], [])
    assert hit.enemy is None and hit.distance == 500


def test_cast_ray_clear_path_reaches_max_range():
    assert cast_ray(ORIGIN, RIGHT, 500, [], []).distance == 500


def test_spread_zero_keeps_direction_and_normalizes():
    result = apply_spread(Vector2(3, 0), 0, random.Random(1))
    assert result == Vector2(1, 0)


def test_spread_stays_within_bounds():
    rng = random.Random(1)
    for _ in range(200):
        result = apply_spread(RIGHT, 5.0, rng)
        assert abs(RIGHT.angle_to(result)) <= 5.0 + 1e-6