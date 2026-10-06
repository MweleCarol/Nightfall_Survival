import pygame
from pygame import Vector2

from src.core import settings
from src.player.player import Player


def test_diagonal_is_not_faster():
    p = Player((1000, 1000))
    p.update(0.1, Vector2(1, 1), False, [])
    moved = (p.position - Vector2(1000, 1000)).length()
    assert abs(moved - settings.PLAYER_SPEED * 0.1) < 0.001


def test_player_blocked_by_wall():
    wall = pygame.Rect(1030, 900, 50, 200)
    p = Player((1000, 1000))
    for _ in range(30):
        p.update(0.05, Vector2(1, 0), False, [wall])
    assert p.rect.right <= wall.left


def test_sprint_costs_stamina_and_is_faster():
    p = Player((1000, 1000))
    p.update(0.1, Vector2(1, 0), True, [])
    assert p.is_sprinting
    assert p.stats.stamina < p.stats.max_stamina
    assert p.velocity.length() > settings.PLAYER_SPEED