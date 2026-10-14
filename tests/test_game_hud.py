import pygame
import pytest
from pygame import Vector2

from src.core import settings
from src.player.stats import Stats
from src.ui.game_hud import GameHUD, HudState
from src.world.camera import Camera
from src.world.map import GameMap
from tests.factories import make_enemy, make_weapon


@pytest.fixture(scope="module")
def city() -> GameMap:
    pygame.font.init()
    return GameMap.load(settings.DEFAULT_MAP)


def make_state(**overrides) -> HudState:
    values = dict(stats=Stats(), weapon=make_weapon(), camera=Camera(1280, 720, 3200, 2400))
    values.update(overrides)
    return HudState(**values)


def test_the_day_hud_draws_every_panel(city):
    surface = pygame.Surface((1280, 720))
    hud = GameHUD(None, city)
    hurt = make_enemy((300, 300))
    hurt.health = 10
    state = make_state(
        prompt="Press E to search", mission_title="First Light", unread_radio=2, protected=True,
        objectives=[("Search crates (1/3)", False), ("Return to the safehouse door", True)],
        objective_marker=Vector2(2000, 1300), enemies=[hurt], crates=[Vector2(1700, 1100)],
        quick_items=[("medkit", "consumable", 3), ("bandage", "consumable", 0)])
    hud.notify("MISSION COMPLETE")
    hud.draw(surface, state)
    hud.update(0.1)
    hud.draw(surface, state)


def test_the_night_hud_draws_every_wave_state(city):
    surface = pygame.Surface((1280, 720))
    hud = GameHUD(None, city)
    for status in ("countdown", "fighting", "cleared"):
        hud.draw(surface, make_state(is_day=False, wave_status=status, wave_number=2, wave_total=3,
                                     wave_remaining=18, wave_countdown=8, night_remaining=47.0,
                                     truce_broken=True))


def test_low_health_radio_popup_and_death_screen_draw(city):
    surface = pygame.Surface((1280, 720))
    hud = GameHUD(None, city)
    state = make_state()
    state.stats.health = 20
    hud.show_radio("DR. REYES", "If you are hearing this, the hospital's backup power failed.")
    hud.draw(surface, state)
    hud.update(10.0)                                  # the popup times out
    hud.draw(surface, state)
    state.stats.health = 0
    hud.draw(surface, state)