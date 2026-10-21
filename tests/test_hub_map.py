import pygame
import pytest
from pygame import Vector2

from src.ui.hub_map import MapPage, fit_scale, world_to_map
from tests.hub_factory import make_context

AREA = pygame.Rect(14, 108, 1252, 560)


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def test_world_points_map_onto_the_screen():
    assert world_to_map((1000, 500), (10, 20), 0.2) == (210, 120)
    assert world_to_map((0, 0), (10, 20), 0.2) == (10, 20)
    assert fit_scale((3200, 2400), (880, 560)) == pytest.approx(560 / 2400)
    assert fit_scale((100, 100), (400, 200)) == pytest.approx(2.0)


def test_the_map_draws_everywhere_with_markers():
    ctx, page, surface = make_context(), MapPage(), pygame.Surface((1280, 720))
    page.draw(surface, AREA, ctx)                                       # nothing found, nothing tracked
    ctx.discovered = {"safehouse_door", "hospital_entrance"}
    ctx.objective_marker = Vector2(2600, 450)
    ctx.missions.start("first_light")
    ctx.tracked_id = "first_light"
    for position in (Vector2(0, 0), Vector2(1600, 1200), Vector2(3200, 2400)):
        ctx.player.position = position
        ctx.player.aim_direction = Vector2(0, -1)
        page.draw(surface, AREA, ctx)
    ctx.player.aim_direction = Vector2(0, 0)                            # a zero aim must not crash
    page.draw(surface, AREA, ctx)


def test_the_map_draws_without_a_map():
    ctx, page = make_context(), MapPage()
    ctx.game_map = None
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)