import pygame
import pytest
from pygame import Vector2

from src.ui.hub_missions import (
    TABS, MissionsPage, missions_for_tab, pick_tracked_mission, reward_lines,
)
from tests.hub_factory import make_context

AREA = pygame.Rect(14, 108, 1252, 560)


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def press(page: MissionsPage, ctx, key: int):
    return page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), ctx)


def ids(missions) -> list[str]:
    return [m.id for m in missions]


def open_log_with_three_active(ctx):
    """First Light is done; three more missions are active; one is still available."""
    ctx.missions.start("first_light")
    ctx.missions.force_complete("first_light")
    for mission_id in ("survive_night_one", "clear_the_streets", "scavenger"):
        assert ctx.missions.start(mission_id)


def test_missions_are_listed_under_the_right_tab():
    ctx = make_context()
    m = ctx.missions
    assert ids(missions_for_tab(m, "available")) == ["first_light"]
    assert missions_for_tab(m, "active") == []
    m.start("first_light")
    assert ids(missions_for_tab(m, "active")) == ["first_light"]
    m.force_complete("first_light")
    m.fail("supply_run")
    assert ids(missions_for_tab(m, "completed")) == ["first_light", "supply_run"]
    assert missions_for_tab(m, "story") == []


def test_the_tracked_mission_is_the_chosen_one_or_the_first_story_mission():
    ctx = make_context()
    m = ctx.missions
    assert pick_tracked_mission(m, None) is None
    m.start("first_light")
    m.force_complete("first_light")
    m.start("scavenger")
    m.start("survive_night_one")
    assert pick_tracked_mission(m, None).id == "survive_night_one"     # story beats side
    assert pick_tracked_mission(m, "scavenger").id == "scavenger"
    assert pick_tracked_mission(m, "ghost").id == "survive_night_one"  # unknown: fall back


def test_reward_lines_are_readable():
    ctx = make_context()
    mission = ctx.missions.missions["survive_night_one"]
    assert reward_lines(mission, ctx.item_defs) == ["120 XP", "1 Medkit", "24 9mm Ammo", "Unlocks chapter 2"]


def test_the_page_draws_every_tab():
    ctx, page, surface = make_context(), MissionsPage(), pygame.Surface((1280, 720))
    ctx.missions.start("first_light")
    ctx.story.add_note("collapse_note")
    ctx.tracked_id = "first_light"
    for _ in range(len(TABS) + 1):
        page.draw(surface, AREA, ctx)
        press(page, ctx, pygame.K_d)
    ctx.missions.force_complete("first_light")
    for _ in range(len(TABS)):
        page.draw(surface, AREA, ctx)
        press(page, ctx, pygame.K_d)


def test_enter_accepts_a_mission_at_the_board():
    ctx, page = make_context(), MissionsPage()
    ctx.can_accept = True
    page.on_open(ctx)
    assert press(page, ctx, pygame.K_RETURN) == "Mission accepted: First Light"
    assert ids(ctx.missions.active()) == ["first_light"]


def test_missions_cannot_be_accepted_away_from_the_board():
    ctx, page = make_context(), MissionsPage()
    press(page, ctx, pygame.K_d)                                       # the AVAILABLE tab
    assert press(page, ctx, pygame.K_RETURN) == "Accept missions at the safehouse mission board"
    assert ctx.missions.active() == []


def test_the_mission_log_can_be_full():
    ctx, page = make_context(), MissionsPage()
    open_log_with_three_active(ctx)
    ctx.can_accept = True
    page.on_open(ctx)
    assert ids(page.rows(ctx)) == ["supply_run"]
    assert press(page, ctx, pygame.K_RETURN) == "Mission log is full"
    assert len(ctx.missions.active()) == 3


def test_enter_tracks_an_active_mission():
    ctx, page = make_context(), MissionsPage()
    ctx.missions.start("first_light")
    assert press(page, ctx, pygame.K_RETURN) == "Tracking: First Light"
    assert ctx.tracked_id == "first_light"
    assert press(page, ctx, pygame.K_RETURN) == "Already tracking this mission"


def test_opening_at_the_board_jumps_to_available():
    ctx, page = make_context(), MissionsPage()
    assert page.tab == "active"
    ctx.can_accept = True
    page.on_open(ctx)
    assert page.tab == "available"


def test_the_tab_keys_cycle_and_reset_the_selection():
    ctx, page = make_context(), MissionsPage()
    page.selected = 2
    press(page, ctx, pygame.K_d)
    assert page.tab == "available" and page.selected == 0
    for _ in range(len(TABS) - 1):
        press(page, ctx, pygame.K_d)
    assert page.tab == "active"
    press(page, ctx, pygame.K_a)
    assert page.tab == "notes"


def test_clicking_selects_a_row():
    ctx, page = make_context(), MissionsPage()
    ctx.missions.start("first_light")
    ctx.missions.force_complete("first_light")
    press(page, ctx, pygame.K_d)                                       # four missions are available now
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)
    row = next(r for r, index in page.row_rects if index == 2)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=row.center), ctx)
    assert page.selected == 2