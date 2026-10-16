import pygame
import pytest

from src.player.equipment import Equipment, EquipmentDef
from src.player.inventory import Inventory, ItemDef
from src.player.player import Player
from src.ui.inventory_ui import InventoryUI


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def make_world():
    items = {
        "combat_helmet": ItemDef("combat_helmet", "Combat Helmet", "equipment", 1, "uncommon"),
        "work_cap": ItemDef("work_cap", "Work Cap", "equipment", 1, "common"),
        "medkit": ItemDef("medkit", "Medkit", "consumable", 5, "uncommon", heal=35),
    }
    equipment = Equipment({
        "combat_helmet": EquipmentDef("combat_helmet", "head", 12, 0, 0, 0, 0.0),
        "work_cap": EquipmentDef("work_cap", "head", 2, 0, 0, 0, 0.0),
    })
    inventory = Inventory(10, items)
    player = Player((1000, 1000), inventory=inventory)
    return equipment, inventory, player, InventoryUI(equipment, lambda: 10)


def press(ui: InventoryUI, player: Player, key: int):
    return ui.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key), player)


def test_the_screen_draws_in_every_state():
    equipment, inventory, player, ui = make_world()
    surface = pygame.Surface((1280, 720))
    ui.draw(surface, player)                                  # an empty pack
    inventory.add("combat_helmet")
    inventory.add("medkit", 2)
    equipment.place("work_cap")
    ui.draw(surface, player)
    press(ui, player, pygame.K_d)
    ui.draw(surface, player)                                  # the equipment list focused


def test_enter_equips_the_selected_piece():
    equipment, inventory, player, ui = make_world()
    inventory.add("combat_helmet")
    message = press(ui, player, pygame.K_RETURN)
    assert message == "Equipped Combat Helmet"
    assert equipment.item_in("head") == "combat_helmet" and inventory.count("combat_helmet") == 0


def test_enter_on_the_equipment_list_takes_the_piece_off():
    equipment, inventory, player, ui = make_world()
    equipment.place("work_cap")
    press(ui, player, pygame.K_d)
    message = press(ui, player, pygame.K_RETURN)
    assert message == "Removed Work Cap" and inventory.count("work_cap") == 1


def test_the_arrow_keys_switch_between_the_two_lists():
    _equipment, _inventory, player, ui = make_world()
    assert ui.focus == "items"
    press(ui, player, pygame.K_RIGHT)
    assert ui.focus == "equipment"
    press(ui, player, pygame.K_LEFT)
    assert ui.focus == "items"