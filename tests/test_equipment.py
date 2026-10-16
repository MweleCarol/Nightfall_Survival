import pytest

from src.combat.armor import damage_reduction  # noqa: F401  (kept to show the two modules work together)
from src.core import settings
from src.enemies.boss import load_boss_defs
from src.player.equipment import (
    SLOTS, Equipment, EquipmentDef, bonus_lines, load_equipment_defs,
)
from src.player.inventory import Inventory, ItemDef, load_item_defs
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.systems.crafting import load_crafting_data
from src.systems.mission_system import load_missions


def make_items() -> dict[str, ItemDef]:
    items = {name: ItemDef(name, name.replace("_", " ").title(), "equipment", 1, "common")
             for name in ("cap", "helmet", "vest", "pack_small", "pack_big")}
    items["scrap"] = ItemDef("scrap", "Scrap", "resource", 99, "common")
    return items


def make_equipment() -> Equipment:
    return Equipment({
        "cap": EquipmentDef("cap", "head", 2, 0, 0, 0, 0.0),
        "helmet": EquipmentDef("helmet", "head", 12, 0, 0, 0, 0.0),
        "vest": EquipmentDef("vest", "body", 18, 0, 0, 0, -0.02),
        "pack_small": EquipmentDef("pack_small", "backpack", 0, 2, 0, 0, 0.0),
        "pack_big": EquipmentDef("pack_big", "backpack", 0, 6, 0, 0, 0.0),
    })


def make_inventory(capacity: int = 10) -> Inventory:
    return Inventory(capacity, make_items())


def raw_piece(**overrides) -> dict:
    data = {"id": "work_cap", "slot": "head", "armor": 2}
    data.update(overrides)
    return data


def test_totals_add_up_across_slots():
    gear = make_equipment()
    for item in ("cap", "vest", "pack_big"):
        gear.place(item)
    totals = gear.totals()
    assert totals["armor"] == 20 and totals["carry_slots"] == 6
    assert totals["move_speed"] == pytest.approx(-0.02)


def test_equipping_moves_the_item_from_the_pack_to_the_slot():
    gear, inv = make_equipment(), make_inventory()
    inv.add("helmet")
    result = gear.equip("helmet", inv, 10)
    assert result.success and gear.item_in("head") == "helmet" and inv.count("helmet") == 0


def test_equipping_swaps_with_the_piece_already_worn():
    gear, inv = make_equipment(), make_inventory()
    gear.place("cap")
    inv.add("helmet")
    assert gear.equip("helmet", inv, 10).success
    assert gear.item_in("head") == "helmet" and inv.count("cap") == 1


def test_you_cannot_wear_what_you_do_not_have():
    gear, inv = make_equipment(), make_inventory()
    assert gear.equip("helmet", inv, 10).success is False
    assert gear.item_in("head") is None


def test_things_that_are_not_gear_cannot_be_worn():
    gear, inv = make_equipment(), make_inventory()
    inv.add("scrap", 5)
    result = gear.equip("scrap", inv, 10)
    assert result.success is False and "can't" in result.message


def test_unequipping_returns_the_piece_to_the_pack():
    gear, inv = make_equipment(), make_inventory()
    gear.place("cap")
    result = gear.unequip("head", inv, 10)
    assert result.success and gear.item_in("head") is None and inv.count("cap") == 1


def test_unequipping_needs_room_in_the_pack():
    gear, inv = make_equipment(), make_inventory(2)
    inv.add("scrap", 198)                                   # both slots are full
    gear.place("cap")
    result = gear.unequip("head", inv, 2)
    assert result.success is False and "room" in result.message
    assert gear.item_in("head") == "cap"


def test_a_bigger_pack_raises_the_capacity():
    gear, inv = make_equipment(), make_inventory(10)
    inv.add("pack_big")
    assert gear.equip("pack_big", inv, 10).success
    assert inv.capacity == 16


def test_a_pack_cannot_be_taken_off_if_the_contents_would_not_fit():
    gear, inv = make_equipment(), make_inventory(10)
    inv.add("pack_big")
    gear.equip("pack_big", inv, 10)
    inv.add("scrap", 99 * 14)                               # 14 slots in use
    assert gear.unequip("backpack", inv, 10).success is False
    assert gear.item_in("backpack") == "pack_big" and inv.capacity == 16
    inv.remove("scrap", 99 * 9)                             # now only 5 slots in use
    assert gear.unequip("backpack", inv, 10).success is True
    assert inv.capacity == 10 and inv.count("pack_big") == 1


def test_swapping_to_a_smaller_pack_is_refused_when_too_full():
    gear, inv = make_equipment(), make_inventory(10)
    inv.add("pack_big")
    gear.equip("pack_big", inv, 10)                         # capacity 16
    inv.add("pack_small")
    inv.add("scrap", 99 * 13)                               # 14 slots in use
    result = gear.equip("pack_small", inv, 10)              # would shrink the capacity to 12
    assert result.success is False
    assert gear.item_in("backpack") == "pack_big" and inv.capacity == 16


def test_serialization_round_trips_and_ignores_garbage():
    gear = make_equipment()
    gear.place("cap")
    data = gear.serialize()
    assert data["head"] == "cap" and data["body"] is None
    assert Equipment.deserialize(data, gear.definitions).item_in("head") == "cap"
    messy = Equipment.deserialize({"head": "vest", "ghost": "cap", "body": 5, "face": None},
                                  gear.definitions)
    assert all(messy.item_in(slot) is None for slot in SLOTS)


def test_bonus_lines_are_readable():
    gear = make_equipment()
    assert bonus_lines(gear.definitions["helmet"].stats()) == ["12 armor"]
    assert bonus_lines(gear.definitions["vest"].stats()) == ["18 armor", "-2% speed"]
    assert bonus_lines(gear.definitions["pack_big"].stats()) == ["+6 slots"]


def test_shipped_equipment_data_is_valid():
    items = load_item_defs()
    defs = load_equipment_defs(items)
    assert {d.slot for d in defs.values()} == set(SLOTS)
    assert all(items[i].type == "equipment" and items[i].max_stack == 1 for i in defs)


def test_equipment_data_rejects_unknown_items():
    with pytest.raises(DataLoadError, match="ghost"):
        EquipmentDef.from_dict(raw_piece(id="ghost"), load_item_defs(), "test")


def test_equipment_data_rejects_items_that_are_not_gear():
    with pytest.raises(DataLoadError, match="equipment"):
        EquipmentDef.from_dict(raw_piece(id="scrap"), load_item_defs(), "test")


def test_equipment_data_rejects_unknown_slots():
    with pytest.raises(DataLoadError, match="slot"):
        EquipmentDef.from_dict(raw_piece(slot="foot"), load_item_defs(), "test")


def test_equipment_data_rejects_negative_values():
    with pytest.raises(DataLoadError, match="armor"):
        EquipmentDef.from_dict(raw_piece(armor=-1), load_item_defs(), "test")


def test_starting_equipment_fits_its_slots():
    defs = load_equipment_defs(load_item_defs())
    for slot, item_id in settings.PLAYER_START_EQUIPMENT.items():
        assert defs[item_id].slot == slot


def test_every_piece_of_gear_can_be_obtained_somewhere():
    items = load_item_defs()
    obtainable = set(settings.PLAYER_START_EQUIPMENT.values())
    for recipe in load_crafting_data(items).recipes.values():
        obtainable.add(recipe.output_item)
    for mission in load_missions(items).values():
        obtainable |= set(mission.rewards.items)
    for boss in load_boss_defs(items).values():
        obtainable |= set(boss.rewards.items)
    assert set(load_equipment_defs(items)) <= obtainable


def test_worn_gear_cannot_be_used_like_a_consumable():
    items = load_item_defs()
    inventory = Inventory(10, items)
    inventory.add("work_cap")
    player = Player((1000, 1000), inventory=inventory)
    player.stats.health = 50
    assert player.use_item("work_cap") is False and player.quick_heal() is None