import pygame
import pytest

from src.ui.hub import HubPage, HubUI
from src.ui.hub_inventory import InventoryPage
from src.ui.hub_skills import SkillsPage
from tests.hub_factory import make_context


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


class StubPage(HubPage):
    def __init__(self):
        self.events, self.opened = [], 0

    def on_open(self, ctx):
        self.opened += 1

    def handle_event(self, event, ctx):
        self.events.append(event)
        return "stub"


def key(code: int, mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod)


def make_hub():
    ctx = make_context()
    hub = HubUI(None, lambda: ctx)
    pages = {"inventory": StubPage(), "skills": StubPage()}
    for tab, page in pages.items():
        hub.set_page(tab, page)
    return hub, pages, ctx


def test_opening_a_tab_shows_it_and_tells_the_page():
    hub, pages, _ctx = make_hub()
    hub.open("skills")
    assert hub.tab == "skills" and pages["skills"].opened == 1


def test_opening_a_tab_without_a_page_falls_back_to_the_first_available():
    hub, _pages, _ctx = make_hub()
    hub.open("settings")
    assert hub.tab == "inventory"


def test_tab_cycles_through_the_available_tabs_and_shift_tab_goes_back():
    hub, _pages, _ctx = make_hub()
    hub.open("skills")
    hub.handle_event(key(pygame.K_TAB))
    assert hub.tab == "inventory"
    hub.handle_event(key(pygame.K_TAB))
    assert hub.tab == "skills"
    hub.handle_event(key(pygame.K_TAB, pygame.KMOD_SHIFT))
    assert hub.tab == "inventory"


def test_number_keys_jump_to_a_tab_when_it_exists():
    hub, _pages, _ctx = make_hub()
    hub.open("inventory")
    hub.handle_event(key(pygame.K_4))
    assert hub.tab == "skills"
    hub.handle_event(key(pygame.K_3))                     # crafting is not built yet
    assert hub.tab == "skills"
    hub.handle_event(key(pygame.K_2))
    assert hub.tab == "inventory"


def test_escape_asks_to_close():
    hub, _pages, _ctx = make_hub()
    assert hub.close_requested is False
    hub.handle_event(key(pygame.K_ESCAPE))
    assert hub.close_requested is True


def test_other_keys_go_to_the_active_page():
    hub, pages, _ctx = make_hub()
    hub.open("inventory")
    assert hub.handle_event(key(pygame.K_RETURN)) == "stub"
    assert len(pages["inventory"].events) == 1 and pages["skills"].events == []


def test_clicking_a_tab_switches_to_it():
    hub, _pages, _ctx = make_hub()
    hub.open("inventory")
    hub.draw(pygame.Surface((1280, 720)))                  # drawing records where the tabs are
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hub._tab_rects["skills"].center)
    hub.handle_event(click)
    assert hub.tab == "skills"
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=hub._tab_rects["crafting"].center)
    hub.handle_event(click)
    assert hub.tab == "skills"                             # no crafting page yet


def test_the_real_pages_draw_in_day_night_and_low_health():
    ctx = make_context()
    hub = HubUI(None, lambda: ctx)
    hub.set_page("inventory", InventoryPage())
    hub.set_page("skills", SkillsPage())
    surface = pygame.Surface((1280, 720))
    for tab in ("inventory", "skills"):
        hub.open(tab)
        hub.draw(surface)
        ctx.is_day, ctx.cycle_label, ctx.location = False, "NIGHT 2", "SAFEHOUSE"
        ctx.player.stats.health = 20
        hub.draw(surface)