import pygame
import pytest

from src.ui.hub_inventory import COLUMNS, InventoryPage
from tests.hub_factory import make_context


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


AREA = pygame.Rect(14, 108, 1252, 560)


def press(page: InventoryPage, ctx, key: int):
    return page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), ctx)


def test_the_page_draws_in_every_state():
    ctx, page, surface = make_context(), InventoryPage(), pygame.Surface((1280, 720))
    page.draw(surface, AREA, ctx)                                   # an empty pack
    for item, quantity in (("medkit", 2), ("grenade", 1), ("scrap", 30), ("ammo_9mm", 20),
                           ("combat_helmet", 1), ("red_dot_sight", 1)):
        ctx.inventory.add(item, quantity)
    ctx.equipment.place("work_cap")
    page.draw(surface, AREA, ctx)
    for _ in range(5):                                              # every filter and sort mode
        press(page, ctx, pygame.K_e)
        press(page, ctx, pygame.K_r)
        page.draw(surface, AREA, ctx)
    page.focus = "equipment"
    page.draw(surface, AREA, ctx)


def test_enter_equips_the_selected_piece():
    ctx, page = make_context(), InventoryPage()
    ctx.inventory.add("combat_helmet")
    assert press(page, ctx, pygame.K_RETURN) == "Equipped Combat Helmet"
    assert ctx.equipment.item_in("head") == "combat_helmet"


def test_enter_fits_an_attachment_to_the_weapon():
    ctx, page = make_context(), InventoryPage()
    ctx.inventory.add("red_dot_sight")
    assert press(page, ctx, pygame.K_RETURN) == "Attached Red Dot Sight"
    assert ctx.player.weapon.attachments["optic"] == "red_dot_sight"


def test_enter_uses_a_medkit_but_not_at_full_health():
    ctx, page = make_context(), InventoryPage()
    ctx.inventory.add("medkit", 2)
    ctx.player.stats.health = 50
    assert press(page, ctx, pygame.K_RETURN) == "Used Medkit" and ctx.player.stats.health == 85
    ctx.player.stats.health = ctx.player.stats.max_health
    assert press(page, ctx, pygame.K_RETURN) == "Health is already full"
    assert ctx.inventory.count("medkit") == 1


def test_enter_on_a_grenade_explains_how_to_throw_it():
    ctx, page = make_context(), InventoryPage()
    ctx.inventory.add("grenade")
    assert press(page, ctx, pygame.K_RETURN) == "Throw it with G"
    assert ctx.inventory.count("grenade") == 1


def test_the_left_edge_leads_to_the_equipment_slots_and_enter_takes_a_piece_off():
    ctx, page = make_context(), InventoryPage()
    ctx.equipment.place("work_cap")
    press(page, ctx, pygame.K_a)                                    # column 0: off the left edge
    assert page.focus == "equipment"
    assert press(page, ctx, pygame.K_RETURN) == "Removed Work Cap"
    assert ctx.inventory.count("work_cap") == 1 and ctx.equipment.item_in("head") is None
    press(page, ctx, pygame.K_d)
    assert page.focus == "grid"


def test_filters_and_sort_modes_change_what_is_shown():
    ctx, page = make_context(), InventoryPage()
    for item, quantity in (("scrap", 5), ("medkit", 1), ("ammo_9mm", 10)):
        ctx.inventory.add(item, quantity)
    assert len(page.items(ctx)) == 3
    press(page, ctx, pygame.K_q)                                    # wraps back to the last filter
    assert page.filter_index == 4
    press(page, ctx, pygame.K_e)
    press(page, ctx, pygame.K_e)
    press(page, ctx, pygame.K_e)                                    # ALL -> AMMO -> GEAR -> CONSUMABLES
    assert [item for item, _ in page.items(ctx)] == ["medkit"]
    press(page, ctx, pygame.K_r)
    assert page.sort_index == 1


def test_the_arrow_keys_move_around_the_grid():
    ctx, page = make_context(), InventoryPage()
    for item in ("scrap", "chemicals", "batteries", "medical_supplies", "weapon_parts",
                 "bandage", "medkit", "grenade"):
        ctx.inventory.add(item)
    press(page, ctx, pygame.K_d)
    assert page.selected == 1
    press(page, ctx, pygame.K_s)
    assert page.selected == 1 + COLUMNS
    press(page, ctx, pygame.K_w)
    press(page, ctx, pygame.K_a)
    assert page.selected == 0 and page.focus == "grid"


def test_clicking_a_cell_selects_it():
    ctx, page = make_context(), InventoryPage()
    for item in ("scrap", "chemicals", "batteries"):
        ctx.inventory.add(item)
    page.draw(pygame.Surface((1280, 720)), AREA, ctx)               # drawing records the cell positions
    rect = next(r for r, index in page.cell_rects if index == 2)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), ctx)
    assert page.selected == 2
    empty = next(r for r, index in page.cell_rects if index == 12)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=empty.center), ctx)
    assert page.selected == 2                                       # empty cells cannot be selected