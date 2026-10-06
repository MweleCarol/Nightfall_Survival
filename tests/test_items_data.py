import random
from collections import Counter

import pytest

from src.core import settings
from src.player.inventory import ItemDef, load_item_defs
from src.services.data_loader import DataLoadError
from src.systems.loot_system import LootEntry, LootSystem, LootTable, load_loot_tables
from src.world.map import GameMap


def make_table(entries, rolls=(1, 1), empty=0.0) -> LootTable:
    return LootTable(rolls[0], rolls[1], empty, tuple(entries))


def test_shipped_items_load():
    defs = load_item_defs()
    assert {"ammo_9mm", "scrap", "medkit", "bandage"} <= set(defs)
    assert defs["medkit"].heal > defs["bandage"].heal > 0


def test_shipped_loot_tables_reference_real_items():
    tables = load_loot_tables(load_item_defs())
    assert "enemy_drop" in tables


def test_every_map_loot_category_has_a_table():
    tables = load_loot_tables(load_item_defs())
    city = GameMap.load(settings.DEFAULT_MAP)
    for point in city.loot_points:
        assert point.category in tables, point.category


def test_heavier_entries_drop_more_often():
    table = make_table([LootEntry("scrap", 90, 1, 1), LootEntry("medkit", 10, 1, 1)])
    loot = LootSystem({"t": table}, random.Random(1))
    counts: Counter = Counter()
    for _ in range(1000):
        for item, quantity in loot.roll("t"):
            counts[item] += quantity
    assert counts["scrap"] > counts["medkit"] * 4


def test_quantities_stay_within_bounds():
    table = make_table([LootEntry("scrap", 1, 2, 5)])
    loot = LootSystem({"t": table}, random.Random(1))
    for _ in range(200):
        for _item, quantity in loot.roll("t"):
            assert 2 <= quantity <= 5


def test_empty_weight_can_produce_nothing():
    table = make_table([LootEntry("scrap", 1, 1, 1)], empty=1000.0)
    loot = LootSystem({"t": table}, random.Random(1))
    empties = sum(1 for _ in range(300) if not loot.roll("t"))
    assert empties > 250


def test_same_item_across_rolls_is_combined():
    table = make_table([LootEntry("scrap", 1, 1, 1)], rolls=(3, 3))
    assert LootSystem({"t": table}, random.Random(1)).roll("t") == [("scrap", 3)]


def test_unknown_item_in_table_is_rejected():
    data = {"rolls": [1, 1], "empty_weight": 0,
            "entries": [{"item": "ghost", "weight": 1, "min": 1, "max": 1}]}
    with pytest.raises(DataLoadError, match="ghost"):
        LootTable.from_dict(data, load_item_defs(), "test")


def test_enemy_specific_table_falls_back_to_default():
    table = make_table([LootEntry("scrap", 1, 1, 1)])
    loot = LootSystem({"enemy_drop": table, "drop_brute": table})
    assert loot.table_for_enemy("brute") == "drop_brute"
    assert loot.table_for_enemy("walker") == "enemy_drop"


def test_invalid_item_type_is_rejected():
    data = {"id": "x", "name": "X", "type": "weapon", "max_stack": 1, "rarity": "common"}
    with pytest.raises(DataLoadError, match="type"):
        ItemDef.from_dict(data, "test")