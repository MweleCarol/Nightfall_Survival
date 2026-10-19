import pygame
import pytest

from src.combat.attachments import load_attachment_defs
from src.player.inventory import Inventory, load_item_defs
from src.systems.crafting import CraftingSystem, load_crafting_data
from src.systems.skills import SkillSet, load_skill_defs
from src.ui.workshop_ui import TABS, VISIBLE_ROWS, WorkshopUI
from tests.factories import make_weapon


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def make_workshop():
    items = load_item_defs()
    inventory = Inventory(20, items)
    weapon = make_weapon()
    crafting = CraftingSystem(load_crafting_data(items), inventory)
    ui = WorkshopUI(crafting, inventory, weapon, SkillSet(load_skill_defs()), load_attachment_defs(items))
    return ui, inventory, weapon


def press(ui: WorkshopUI, key: int):
    return ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_every_tab_draws():
    ui, inventory, weapon = make_workshop()
    inventory.add("red_dot_sight")
    weapon.attachments["muzzle"] = "suppressor"
    surface = pygame.Surface((1280, 720))
    for tab in TABS:
        ui.open_tab(tab)
        ui.draw(surface)


def test_enter_on_a_pack_attachment_fits_it():
    ui, inventory, weapon = make_workshop()
    inventory.add("red_dot_sight")
    ui.open_tab("attach")
    for _ in range(3):                                   # past the three slot rows
        press(ui, pygame.K_DOWN)
    assert press(ui, pygame.K_RETURN) == "Attached Red Dot Sight"
    assert weapon.attachments["optic"] == "red_dot_sight" and inventory.count("red_dot_sight") == 0


def test_enter_on_a_slot_takes_the_attachment_off():
    ui, inventory, weapon = make_workshop()
    weapon.attachments["muzzle"] = "suppressor"
    ui.open_tab("attach")
    press(ui, pygame.K_DOWN)                             # the muzzle row
    assert press(ui, pygame.K_RETURN) == "Removed Suppressor"
    assert weapon.attachments["muzzle"] is None and inventory.count("suppressor") == 1


def test_the_arrow_keys_cycle_through_the_tabs():
    ui, _inventory, _weapon = make_workshop()
    assert ui.tab == "craft"
    press(ui, pygame.K_RIGHT)
    assert ui.tab == "weapon"
    press(ui, pygame.K_RIGHT)
    assert ui.tab == "attach"
    press(ui, pygame.K_RIGHT)
    assert ui.tab == "craft"
    press(ui, pygame.K_LEFT)
    assert ui.tab == "attach"


def test_the_long_recipe_list_scrolls():
    ui, _inventory, _weapon = make_workshop()
    recipes = list(ui.crafting.data.recipes.values())
    assert len(recipes) > VISIBLE_ROWS
    for _ in range(len(recipes) + 5):
        press(ui, pygame.K_DOWN)
    assert ui.nav.selected == len(recipes) - 1
    ui.draw(pygame.Surface((1280, 720)))