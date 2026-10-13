import pygame
import pytest

from src.player.stats import Stats
from src.ui.combat_hud import CombatHUD
from src.ui.hud import HUD
from src.world.day_night import DayNightCycle
from tests.factories import make_weapon


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def test_the_hud_draws_every_element_without_errors():
    surface = pygame.Surface((1280, 720))
    hud = HUD()
    hud.notify("MISSION COMPLETE: TEST")
    stats, cycle = Stats(), DayNightCycle()
    hud.draw(surface, stats, 60.0, cycle, "Press E to search", True)
    hud.update(0.1)
    stats.health = 20                           # the low-health pulse
    cycle.skip_to_next_phase()                  # the moon
    hud.draw(surface, stats, 60.0, cycle, None, False)
    stats.health = 0                            # the "YOU DIED" text
    hud.draw(surface, stats, 60.0, cycle, None, False)


def test_the_combat_hud_draws_in_every_weapon_state():
    surface = pygame.Surface((1280, 720))
    hud = CombatHUD()
    ready = make_weapon()
    hud.draw(surface, ready, (640, 360), 3)
    reloading = make_weapon(loaded=0, reserve=10)
    reloading.start_reload()
    hud.draw(surface, reloading, (640, 360), 0)
    hud.draw(surface, make_weapon(loaded=0, reserve=0), (640, 360), 0)