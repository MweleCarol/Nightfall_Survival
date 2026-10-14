import pygame
import pytest
from pygame import Vector2

from src.core import settings
from src.ui.minimap import Minimap, project
from src.world.map import GameMap


@pytest.fixture(scope="module")
def city() -> GameMap:
    pygame.font.init()
    return GameMap.load(settings.DEFAULT_MAP)


def test_the_player_is_at_the_centre():
    point, clamped = project(Vector2(0, 0), 0.1, 66)
    assert point == Vector2(0, 0) and clamped is False


def test_nearby_points_stay_inside_the_circle():
    point, clamped = project(Vector2(100, 0), 0.1, 66)
    assert point == Vector2(10, 0) and clamped is False


def test_far_points_are_pulled_to_the_rim_in_their_direction():
    point, clamped = project(Vector2(5000, 0), 0.1, 66)
    assert clamped is True
    assert point.length() == pytest.approx(59) and point.y == pytest.approx(0)


def test_the_minimap_draws_everywhere_on_the_map(city):
    minimap = Minimap(city, pygame.font.Font(None, 16))
    surface = pygame.Surface((1280, 720))
    for position in (Vector2(0, 0), Vector2(1600, 1200), Vector2(3200, 2400)):
        minimap.draw(surface, (1198, 94), position, Vector2(1, 0), [Vector2(1700, 1250)],
                     [Vector2(1650, 1210)], Vector2(2600, 450))