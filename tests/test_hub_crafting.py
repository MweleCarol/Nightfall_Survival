import pygame
import pytest

from src.systems.crafting import load_crafting_data
from src.ui.hub_crafting import (
    CATEGORIES, NEEDS_BENCH, CraftingPage, max_craftable, recipe_category,
)
from tests.hub_factory import make_context

AREA = pygame.Rect(14, 108, 1252, 560)


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def press(page: CraftingPage, ctx, key: int):
    return page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), ctx)


def test_recipes_are_sorted_into_categories():
    ctx = make_context()
    recipes = ctx.crafting.data.recipes
    assert recipe_category(recipes["craft_medkit"], ctx.item_defs) == "supplies"
    assert recipe_category(recipes["craft_ammo"], ctx.item_defs) == "supplies"
    assert recipe_category(recipes["craft_combat_helmet"], ctx.item_defs) == "gear"
    assert recipe_category(recipes["craft_red_dot_sight"], ctx.item_defs) == "attachments"


def test_max_craftable_is_limited_by_the_scarcest_material():
    have = {"scrap": 10, "chemicals": 2}.get
    count = lambda item: have(item, 0)
    assert max_craftable({"scrap": 2, "chemicals": 1}, count) == 2
    assert max_craftable({"scrap": 1}, count) == 9                    # capped at the limit
    assert max_craftable({"scrap": 1, "batteries": 1}, count) == 0
    assert max_craftable({}, count) == 0


def test_the_page_draws_every_category():
    ctx, page, surface = make_context(), CraftingPage(), pygame.Surface((1280, 720))
    for item, quantity in (("scrap", 30), ("chemicals", 10), ("weapon_parts", 3), ("batteries", 2)):
        ctx.inventory.add(item, quantity)
    ctx.player.weapon.attachments["muzzle"] = "suppressor"
    for name in CATEGORIES:
        page.set_category(name)
        for _ in range(7):                                             # walk through the rows
            page.draw(surface, AREA, ctx)
            press(page, ctx, pygame.K_s)
    ctx.can_craft = False
    page.draw(surface, AREA, ctx)
    ctx.crafting = None
    page.draw(surface, AREA, ctx)


def test_enter_crafts_the_selected_recipe():
    ctx, page = make_context(), CraftingPage()
    ctx.inventory.add("scrap", 3)
    ctx.inventory.add("medical_supplies", 1)
    assert press(page, ctx, pygame.K_RETURN) == "Crafted Bandage x2"
    assert ctx.inventory.count("bandage") == 2 and ctx.inventory.count("scrap") == 2


def test_missing_materials_change_nothing():
    ctx, page = make_context(), CraftingPage()
    ctx.inventory.add("scrap", 3)
    assert press(page, ctx, pygame.K_RETURN) == "Missing materials"
    assert ctx.inventory.count("scrap") == 3 and ctx.inventory.count("bandage") == 0


def test_quantity_follows_what_you_can_afford_and_crafts_in_bulk():
    ctx, page = make_context(), CraftingPage()
    ctx.inventory.add("scrap", 10)
    ctx.inventory.add("medical_supplies", 3)
    for _ in range(5):
        press(page, ctx, pygame.K_e)
    assert page.quantity == 3                                          # limited by medical supplies
    assert press(page, ctx, pygame.K_RETURN) == "Crafted Bandage x6"
    assert ctx.inventory.count("bandage") == 6 and page.quantity == 1
    press(page, ctx, pygame.K_q)
    assert page.quantity == 1


def test_the_category_keys_cycle_and_wrap():
    ctx, page = make_context(), CraftingPage()
    press(page, ctx, pygame.K_a)
    assert page.category == len(CATEGORIES) - 1
    press(page, ctx, pygame.K_d)
    assert page.category == 0
    page.selected = 3
    press(page, ctx, pygame.K_d)
    assert page.category == 1 and page.selected == 0


def test_the_weapon_category_lists_slots_then_upgrades_and_enter_takes_a_part_off():
    ctx, page = make_context(), CraftingPage()
    page.set_category("weapon")
    kinds = [kind for kind, _ in page.entries(ctx)]
    assert kinds == ["slot"] * 3 + ["upgrade"] * 3
    ctx.player.weapon.attachments["muzzle"] = "suppressor"
    press(page, ctx, pygame.K_s)                                       # the muzzle row
    assert press(page, ctx, pygame.K_RETURN) == "Removed Suppressor"
    assert ctx.player.weapon.attachments["muzzle"] is None and ctx.inventory.count("suppressor") == 1


def test_enter_on_an_upgrade_spends_materials():
    ctx, page = make_context(), CraftingPage()
    ctx.inventory.add("scrap", 20)
    ctx.inventory.add("weapon_parts", 3)
    page.set_category("weapon")
    for _ in range(3):
        press(page, ctx, pygame.K_s)
    assert press(page, ctx, pygame.K_RETURN) == "Hardened Rounds upgraded to level 1"
    assert ctx.player.weapon.upgrade_levels["damage"] == 1


def test_crafting_needs_the_safehouse_but_taking_a_part_off_does_not():
    ctx, page = make_context(), CraftingPage()
    ctx.can_craft = False
    ctx.inventory.add("scrap", 3)
    ctx.inventory.add("medical_supplies", 1)
    assert press(page, ctx, pygame.K_RETURN) == NEEDS_BENCH
    assert ctx.inventory.count("scrap") == 3
    page.set_category("weapon")
    ctx.player.weapon.attachments["optic"] = "red_dot_sight"
    assert press(page, ctx, pygame.K_RETURN) == "Removed Red Dot Sight"


def test_clicking_a_category_and_a_row_selects_them():
    ctx, page = make_context(), CraftingPage()
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)                  # drawing records the positions
    rect = next(r for r, index in page.category_rects if index == 2)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), ctx)
    assert page.category == 2
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)
    row = next(r for r, index in page.row_rects if index == 1)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=row.center), ctx)
    assert page.selected == 1