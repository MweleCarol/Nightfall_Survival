from src.player.inventory import Inventory, ItemDef
from src.player.player import Player


def make_defs():
    return {
        "medkit": ItemDef("medkit", "Medkit", "consumable", 5, "uncommon", heal=35),
        "bandage": ItemDef("bandage", "Bandage", "consumable", 10, "common", heal=15),
        "scrap": ItemDef("scrap", "Scrap", "resource", 99, "common"),
    }


def make_player(health: int = 50) -> Player:
    player = Player((1000, 1000), inventory=Inventory(10, make_defs()))
    player.stats.health = health
    return player


def test_medkit_heals_and_is_consumed():
    player = make_player(50)
    player.inventory.add("medkit", 1)
    assert player.use_item("medkit") is True
    assert player.stats.health == 85 and player.inventory.count("medkit") == 0


def test_healing_item_not_wasted_at_full_health():
    player = make_player(100)
    player.inventory.add("medkit", 1)
    assert player.use_item("medkit") is False
    assert player.inventory.count("medkit") == 1


def test_non_consumables_cannot_be_used():
    player = make_player(50)
    player.inventory.add("scrap", 5)
    assert player.use_item("scrap") is False


def test_quick_heal_prefers_the_smallest_sufficient_item():
    player = make_player(90)                    # missing 10
    player.inventory.add("medkit", 1)
    player.inventory.add("bandage", 1)
    assert player.quick_heal() == "Bandage"
    assert player.inventory.count("medkit") == 1


def test_quick_heal_uses_the_biggest_when_nothing_covers_it():
    player = make_player(20)                    # missing 80
    player.inventory.add("medkit", 1)
    player.inventory.add("bandage", 1)
    assert player.quick_heal() == "Medkit"


def test_quick_heal_with_nothing_available():
    assert make_player(50).quick_heal() is None