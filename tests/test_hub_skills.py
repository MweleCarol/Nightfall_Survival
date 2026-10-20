import pygame
import pytest

from src.ui.hub_skills import SkillsPage
from tests.hub_factory import make_context


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


AREA = pygame.Rect(14, 108, 1252, 560)


def press(page: SkillsPage, ctx, key: int):
    return page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), ctx)


def test_the_page_draws_with_and_without_points_and_with_a_maxed_skill():
    ctx, page, surface = make_context(), SkillsPage(), pygame.Surface((1280, 720))
    page.draw(surface, AREA, ctx)
    ctx.progression.skill_points = 3
    page.draw(surface, AREA, ctx)
    ctx.skills.ranks["vitality"] = 5
    page.draw(surface, AREA, ctx)


def test_enter_buys_a_rank_with_a_skill_point():
    ctx, page = make_context(), SkillsPage()
    ctx.progression.skill_points = 2
    assert press(page, ctx, pygame.K_RETURN) == "Vitality - rank 1"
    assert ctx.skills.rank("vitality") == 1 and ctx.progression.skill_points == 1


def test_enter_without_points_explains_why():
    ctx, page = make_context(), SkillsPage()
    assert press(page, ctx, pygame.K_RETURN) == "No skill points available"
    assert ctx.skills.rank("vitality") == 0


def test_a_maxed_skill_keeps_its_point():
    ctx, page = make_context(), SkillsPage()
    ctx.progression.skill_points = 3
    ctx.skills.ranks["vitality"] = 5
    assert press(page, ctx, pygame.K_RETURN) == "Vitality is already maxed"
    assert ctx.progression.skill_points == 3


def test_the_arrow_keys_move_between_the_columns_and_rows():
    ctx, page = make_context(), SkillsPage()
    press(page, ctx, pygame.K_d)
    assert (page.col, page.row) == (1, 0) and page.selected_skill(ctx).id == "hard_hitter"
    for _ in range(5):
        press(page, ctx, pygame.K_s)
    assert page.row == 2 and page.selected_skill(ctx).id == "precision"      # stops at the last row
    press(page, ctx, pygame.K_d)
    press(page, ctx, pygame.K_d)
    assert page.col == 2                                                      # stops at the last column
    press(page, ctx, pygame.K_a)
    assert page.col == 1


def test_clicking_a_skill_selects_it():
    ctx, page = make_context(), SkillsPage()
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)
    rect = next(r for r, col, row in page.card_rects if (col, row) == (2, 1))
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), ctx)
    assert page.selected_skill(ctx).id == "scavenger"