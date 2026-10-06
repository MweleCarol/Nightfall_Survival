import pygame

from src.core import settings
from src.states.playing_state import TEST_WALKER_POSITIONS
from src.world.map import GameMap


def test_test_walkers_spawn_in_free_space():
    city = GameMap.load(settings.DEFAULT_MAP)
    for pos in TEST_WALKER_POSITIONS:
        rect = pygame.Rect(0, 0, 32, 32)
        rect.center = pos
        assert rect.collidelist(city.walls) == -1, pos