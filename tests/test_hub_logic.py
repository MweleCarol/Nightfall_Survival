from src.player.inventory import ItemDef
from src.systems.skills import load_skill_defs
from src.ui.hub_widgets import (
    filter_items, format_skill_effect, item_category, move_in_grid, sort_items,
)


def defs() -> dict[str, ItemDef]:
    return {
        "ammo_9mm": ItemDef("ammo_9mm", "9mm Ammo", "ammo", 60, "common"),
        "scrap": ItemDef("scrap", "Scrap", "resource", 99, "common"),
        "medkit": ItemDef("medkit", "Medkit", "consumable", 5, "uncommon", heal=35),
        "grenade": ItemDef("grenade", "Frag Grenade", "throwable", 5, "uncommon"),
        "helmet": ItemDef("helmet", "Combat Helmet", "equipment", 1, "rare"),
        "red_dot": ItemDef("red_dot", "Red Dot", "attachment", 1, "uncommon"),
        "radio": ItemDef("radio", "Emergency Radio", "quest", 1, "epic"),
    }


def test_items_are_sorted_into_the_right_categories():
    d = defs()
    expected = {"ammo_9mm": "ammo", "scrap": "materials", "medkit": "consumables",
                "grenade": "consumables", "helmet": "gear", "red_dot": "gear", "radio": "materials"}
    assert {item_id: item_category(d[item_id]) for item_id in d} == expected


def test_filters_keep_only_their_category():
    d = defs()
    items = [(item_id, 1) for item_id in d]
    assert [i for i, _ in filter_items(items, d, "gear")] == ["helmet", "red_dot"]
    assert [i for i, _ in filter_items(items, d, "materials")] == ["scrap", "radio"]
    assert len(filter_items(items, d, "all")) == len(items)


def test_sort_modes_order_the_items():
    d = defs()
    items = [("scrap", 30), ("medkit", 2), ("helmet", 1), ("ammo_9mm", 20)]
    assert [i for i, _ in sort_items(items, d, "type")] == ["ammo_9mm", "scrap", "medkit", "helmet"]
    assert [i for i, _ in sort_items(items, d, "name")] == ["ammo_9mm", "helmet", "medkit", "scrap"]
    assert [i for i, _ in sort_items(items, d, "amount")] == ["scrap", "ammo_9mm", "medkit", "helmet"]
    assert [i for i, _ in sort_items(items, d, "rarity")] == ["helmet", "medkit", "ammo_9mm", "scrap"]


def test_grid_navigation_stays_inside_the_items():
    assert move_in_grid(0, 1, 0, 10, 5) == 1
    assert move_in_grid(4, 1, 0, 10, 5) == 4              # the right edge
    assert move_in_grid(0, -1, 0, 10, 5) == 0             # the left edge
    assert move_in_grid(2, 0, 1, 10, 5) == 7
    assert move_in_grid(7, 0, -1, 10, 5) == 2
    assert move_in_grid(0, 0, -1, 10, 5) == 0             # the top edge
    assert move_in_grid(3, 0, 1, 7, 5) == 6               # down into a half-empty last row
    assert move_in_grid(6, 0, 1, 7, 5) == 6
    assert move_in_grid(6, 1, 0, 7, 5) == 6
    assert move_in_grid(0, 1, 1, 0, 5) == 0               # nothing to select


def test_skill_effects_are_readable():
    skills = load_skill_defs()
    assert format_skill_effect(skills["vitality"], 3) == "+30 maximum health"
    assert format_skill_effect(skills["hard_hitter"], 2) == "+16% weapon damage"
    assert format_skill_effect(skills["pack_rat"], 2) == "+4 inventory slots"
    assert format_skill_effect(skills["vitality"], 0) == "No bonus yet"


def test_every_shipped_skill_has_a_readable_effect():
    for skill in load_skill_defs().values():
        assert format_skill_effect(skill, 1).startswith("+"), skill.id