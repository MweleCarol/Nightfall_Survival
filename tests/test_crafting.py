import random

import pytest

from src.player.inventory import Inventory, ItemDef, load_item_defs
from src.services.data_loader import DataLoadError
from src.systems.crafting import (
    UPGRADE_STATS, CraftingData, CraftingSystem, Recipe, WeaponUpgradeDef, load_crafting_data,
)
from tests.factories import make_weapon


def item_defs() -> dict[str, ItemDef]:
    return {
        "scrap": ItemDef("scrap", "Scrap", "resource", 99, "common"),
        "medical_supplies": ItemDef("medical_supplies", "Medical Supplies", "resource", 30, "uncommon"),
        "weapon_parts": ItemDef("weapon_parts", "Weapon Parts", "resource", 20, "rare"),
        "bandage": ItemDef("bandage", "Bandage", "consumable", 10, "common", heal=15),
    }


def make_data() -> CraftingData:
    recipes = {"craft_bandage": Recipe(
        "craft_bandage", "Bandage x2", "d", "bandage", 2, {"scrap": 1, "medical_supplies": 1})}
    upgrades = {"damage": WeaponUpgradeDef(
        "damage", "Hardened Rounds", "d", "damage", 0.2,
        ({"scrap": 5, "weapon_parts": 1}, {"scrap": 8, "weapon_parts": 2}))}
    return CraftingData(recipes, upgrades)


def make_system(capacity: int = 10, **items: int):
    inventory = Inventory(capacity, item_defs())
    for item_id, quantity in items.items():
        inventory.add(item_id, quantity)
    return CraftingSystem(make_data(), inventory, random.Random(1)), inventory


def test_craft_consumes_the_cost_and_adds_the_output():
    system, inv = make_system(scrap=3, medical_supplies=1)
    result = system.craft("craft_bandage")
    assert result.success
    assert inv.count("scrap") == 2 and inv.count("medical_supplies") == 0
    assert inv.count("bandage") == 2


def test_craft_with_missing_materials_changes_nothing():
    system, inv = make_system(scrap=3)
    assert not system.craft("craft_bandage").success
    assert inv.count("scrap") == 3 and inv.count("bandage") == 0


def test_craft_rolls_back_when_the_inventory_is_full():
    system, inv = make_system(capacity=2, scrap=3, medical_supplies=2)
    result = system.craft("craft_bandage")
    assert not result.success and "full" in result.message.lower()
    assert inv.count("scrap") == 3 and inv.count("medical_supplies") == 2
    assert inv.count("bandage") == 0


def test_free_craft_keeps_the_materials():
    system, inv = make_system(scrap=1, medical_supplies=1)
    result = system.craft("craft_bandage", free_chance=1.0)
    assert result.success and result.free
    assert inv.count("scrap") == 1 and inv.count("bandage") == 2


def test_unknown_recipe_fails_politely():
    system, _ = make_system()
    assert not system.craft("nonsense").success


def test_weapon_upgrade_spends_materials_and_raises_the_level():
    system, inv = make_system(scrap=10, weapon_parts=1)
    weapon = make_weapon()
    assert system.upgrade_weapon("damage", weapon).success
    assert weapon.upgrade_levels["damage"] == 1
    assert inv.count("scrap") == 5 and inv.count("weapon_parts") == 0


def test_weapon_upgrade_needs_materials():
    system, _ = make_system(scrap=1)
    weapon = make_weapon()
    assert not system.upgrade_weapon("damage", weapon).success
    assert weapon.upgrade_levels.get("damage", 0) == 0


def test_weapon_upgrade_stops_at_max_level():
    system, _ = make_system(scrap=50, weapon_parts=10)
    weapon = make_weapon()
    weapon.upgrade_levels["damage"] = 2
    result = system.upgrade_weapon("damage", weapon)
    assert not result.success and "max" in result.message.lower()


def test_upgrade_bonus_is_level_times_per_level():
    system, _ = make_system()
    weapon = make_weapon()
    weapon.upgrade_levels = {"damage": 2}
    assert abs(system.upgrade_bonus("damage", weapon) - 0.4) < 1e-9
    assert system.upgrade_bonus("magazine", weapon) == 0


def test_shipped_crafting_data_is_valid():
    defs = load_item_defs()
    data = load_crafting_data(defs)
    assert data.recipes and data.upgrades
    assert all(u.stat in UPGRADE_STATS for u in data.upgrades.values())
    assert all(r.output_item in defs for r in data.recipes.values())


def test_recipe_with_unknown_item_is_rejected():
    data = {"recipes": [{"id": "x", "name": "X", "description": "d",
                         "output": {"item": "bandage", "quantity": 1},
                         "cost": {"ghost": 1}}],
            "weapon_upgrades": []}
    with pytest.raises(DataLoadError, match="ghost"):
        CraftingData.from_dict(data, load_item_defs(), "test")