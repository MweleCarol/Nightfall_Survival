import pytest

from src.player.inventory import Inventory, ItemDef


def make_defs():
    return {
        "scrap": ItemDef("scrap", "Scrap", "resource", 99, "common"),
        "medkit": ItemDef("medkit", "Medkit", "consumable", 5, "uncommon", heal=35),
        "ammo_9mm": ItemDef("ammo_9mm", "9mm Ammo", "ammo", 60, "common"),
    }


def make_inv(capacity=10):
    return Inventory(capacity, make_defs())


def test_inventory_stacks_items():
    inv = make_inv()
    assert inv.add("scrap", 20) == 20
    assert inv.count("scrap") == 20 and inv.slots_used == 1
    assert inv.add("scrap", 30) == 30
    assert inv.slots_used == 1                  # 50 still fits one stack of 99


def test_overflow_uses_a_second_slot():
    inv = make_inv()
    inv.add("scrap", 100)
    assert inv.slots_used == 2


def test_capacity_limits_a_partial_add():
    inv = make_inv(capacity=2)
    assert inv.add("medkit", 12) == 10          # 2 slots x stack of 5
    assert inv.count("medkit") == 10


def test_full_inventory_rejects_new_types_but_fills_existing_stacks():
    inv = make_inv(capacity=1)
    inv.add("scrap", 1)
    assert inv.add("medkit", 1) == 0
    assert inv.add("scrap", 5) == 5


def test_remove_returns_the_amount_removed():
    inv = make_inv()
    inv.add("scrap", 5)
    assert inv.remove("scrap", 3) == 3 and inv.count("scrap") == 2
    assert inv.remove("scrap", 10) == 2 and inv.count("scrap") == 0
    assert inv.remove("scrap", 1) == 0          # nothing left


def test_has():
    inv = make_inv()
    inv.add("medkit", 2)
    assert inv.has("medkit") and inv.has("medkit", 2)
    assert not inv.has("medkit", 3) and not inv.has("scrap")


def test_serialize_round_trip():
    inv = make_inv()
    inv.add("scrap", 120)
    inv.add("medkit", 2)
    data = inv.serialize()
    assert data == {"scrap": 120, "medkit": 2}
    clone = Inventory.deserialize(data, 10, make_defs())
    assert clone.count("scrap") == 120 and clone.count("medkit") == 2


def test_deserialize_skips_unknown_and_invalid_entries():
    clone = Inventory.deserialize({"ghost": 5, "scrap": -3, "medkit": 2}, 10, make_defs())
    assert clone.serialize() == {"medkit": 2}


def test_deserialize_respects_capacity():
    clone = Inventory.deserialize({"scrap": 500}, 2, make_defs())
    assert clone.count("scrap") == 198


def test_unknown_item_raises():
    with pytest.raises(ValueError):
        make_inv().add("ghost", 1)


def test_non_positive_quantity_adds_nothing():
    inv = make_inv()
    assert inv.add("scrap", 0) == 0 and inv.add("scrap", -5) == 0
    assert inv.count("scrap") == 0