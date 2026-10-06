import pygame

from src.world.collision import collide_axis


def test_moving_right_stops_at_wall():
    wall = pygame.Rect(40, 0, 50, 50)
    rect = pygame.Rect(20, 0, 32, 32)       # overlapping after moving right
    assert collide_axis(rect, [wall], "x", 5) is True
    assert rect.right == wall.left


def test_moving_down_stops_on_wall_top():
    wall = pygame.Rect(0, 40, 50, 50)
    rect = pygame.Rect(0, 20, 32, 32)
    assert collide_axis(rect, [wall], "y", 5) is True
    assert rect.bottom == wall.top


def test_no_collision_returns_false():
    wall = pygame.Rect(200, 200, 50, 50)
    rect = pygame.Rect(0, 0, 32, 32)
    assert collide_axis(rect, [wall], "x", 5) is False