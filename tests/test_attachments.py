import pytest

from src.combat.attachments import (
    AttachmentDef, attach, attachment_bonus_lines, attachment_modifiers, detach,
    load_attachment_defs,
)
from src.combat.weapon import ATTACHMENT_SLOTS
from src.player.inventory import Inventory, ItemDef, load_item_defs
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.systems.crafting import load_crafting_data
from tests.factories import make_weapon


def make_items() -> dict[str, ItemDef]:
    items = {name: ItemDef(name, name.replace("_", " ").title(), "attachment", 1, "common")
             for name in ("red_dot", "scope", "suppressor", "foregrip", "pistol_only_mod")}
    items["scrap"] = ItemDef("scrap", "Scrap", "resource", 99, "common")
    return items


def make_defs() -> dict[str, AttachmentDef]:
    return {
        "red_dot": AttachmentDef("red_dot", "optic", range=0.10, spread=-0.15),
        "scope": AttachmentDef("scope", "optic", range=0.35, spread=-0.25, fire_rate=-0.05),
        "suppressor": AttachmentDef("suppressor", "muzzle", damage=-0.05, recoil=-0.40),
        "foregrip": AttachmentDef("foregrip", "grip", spread=-0.12, recoil=-0.20),
        "pistol_only_mod": AttachmentDef("pistol_only_mod", "grip", fits=("some_other_gun",)),
    }


def make_inventory(capacity: int = 10) -> Inventory:
    return Inventory(capacity, make_items())


def raw_attachment(**overrides) -> dict:
    data = {"id": "red_dot_sight", "slot": "optic", "range": 0.1}
    data.update(overrides)
    return data


def test_attaching_moves_the_item_from_the_pack_to_the_slot():
    weapon, inv = make_weapon(), make_inventory()
    inv.add("red_dot")
    result = attach(weapon, "red_dot", inv, make_defs())
    assert result.success and weapon.attachments["optic"] == "red_dot" and inv.count("red_dot") == 0


def test_attaching_swaps_with_the_piece_already_fitted():
    weapon, inv = make_weapon(), make_inventory()
    weapon.attachments["optic"] = "red_dot"
    inv.add("scope")
    assert attach(weapon, "scope", inv, make_defs()).success
    assert weapon.attachments["optic"] == "scope" and inv.count("red_dot") == 1


def test_you_cannot_fit_what_you_do_not_have():
    weapon, inv = make_weapon(), make_inventory()
    assert attach(weapon, "red_dot", inv, make_defs()).success is False
    assert weapon.attachments["optic"] is None


def test_things_that_are_not_attachments_are_refused():
    weapon, inv = make_weapon(), make_inventory()
    inv.add("scrap", 3)
    result = attach(weapon, "scrap", inv, make_defs())
    assert result.success is False and "isn't" in result.message


def test_an_attachment_for_another_weapon_does_not_fit():
    weapon, inv = make_weapon(), make_inventory()
    inv.add("pistol_only_mod")
    result = attach(weapon, "pistol_only_mod", inv, make_defs())
    assert result.success is False and "fit" in result.message
    assert inv.count("pistol_only_mod") == 1


def test_detaching_returns_the_piece_to_the_pack():
    weapon, inv = make_weapon(), make_inventory()
    weapon.attachments["muzzle"] = "suppressor"
    assert detach(weapon, "muzzle", inv, make_defs()).success
    assert weapon.attachments["muzzle"] is None and inv.count("suppressor") == 1


def test_detaching_needs_room_in_the_pack():
    weapon, inv = make_weapon(), make_inventory(1)
    inv.add("scrap", 99)                                     # the only slot is full
    weapon.attachments["muzzle"] = "suppressor"
    result = detach(weapon, "muzzle", inv, make_defs())
    assert result.success is False and weapon.attachments["muzzle"] == "suppressor"


def test_detaching_from_an_empty_slot_does_nothing():
    weapon, inv = make_weapon(), make_inventory()
    assert detach(weapon, "grip", inv, make_defs()).success is False


def test_modifiers_add_up_across_slots_and_empty_slots_add_nothing():
    weapon = make_weapon()
    defs = make_defs()
    assert all(value == 0 for value in attachment_modifiers(weapon, defs).values())
    weapon.attachments.update({"optic": "red_dot", "muzzle": "suppressor", "grip": "foregrip"})
    totals = attachment_modifiers(weapon, defs)
    assert totals["range"] == pytest.approx(0.10)
    assert totals["spread"] == pytest.approx(-0.27)
    assert totals["damage"] == pytest.approx(-0.05)
    assert totals["recoil"] == pytest.approx(-0.60)


def test_the_weapon_stats_follow_the_attachments():
    weapon = make_weapon(spread=2.0, range=500.0, fire_rate=4.0)
    weapon.attachments.update({"optic": "scope", "grip": "foregrip"})
    weapon.modifiers = attachment_modifiers(weapon, make_defs())
    assert weapon.range == pytest.approx(675)
    assert weapon.spread == pytest.approx(2.0 * (1 - 0.37))
    assert weapon.fire_rate == pytest.approx(3.8)
    assert weapon.recoil == pytest.approx(0.8)


def test_bonus_lines_are_readable():
    defs = make_defs()
    assert attachment_bonus_lines(defs["red_dot"]) == ["+10% range", "-15% spread"]
    assert attachment_bonus_lines(defs["suppressor"]) == ["-5% damage", "-40% recoil"]


def test_shipped_attachment_data_is_valid():
    items = load_item_defs()
    defs = load_attachment_defs(items)
    assert {d.slot for d in defs.values()} == set(ATTACHMENT_SLOTS)
    assert all(items[i].type == "attachment" and items[i].max_stack == 1 for i in defs)


def test_attachment_data_rejects_unknown_items():
    with pytest.raises(DataLoadError, match="ghost"):
        AttachmentDef.from_dict(raw_attachment(id="ghost"), load_item_defs(), "test")


def test_attachment_data_rejects_items_that_are_not_attachments():
    with pytest.raises(DataLoadError, match="attachment"):
        AttachmentDef.from_dict(raw_attachment(id="scrap"), load_item_defs(), "test")


def test_attachment_data_rejects_unknown_slots():
    with pytest.raises(DataLoadError, match="slot"):
        AttachmentDef.from_dict(raw_attachment(slot="stock"), load_item_defs(), "test")


def test_attachment_data_rejects_an_empty_fits_list():
    with pytest.raises(DataLoadError, match="fits"):
        AttachmentDef.from_dict(raw_attachment(fits=[]), load_item_defs(), "test")


def test_every_attachment_can_be_crafted():
    items = load_item_defs()
    crafted = {recipe.output_item for recipe in load_crafting_data(items).recipes.values()}
    assert set(load_attachment_defs(items)) <= crafted


def test_attachments_cannot_be_used_like_consumables():
    items = load_item_defs()
    inventory = Inventory(10, items)
    inventory.add("red_dot_sight")
    player = Player((1000, 1000), inventory=inventory)
    assert player.use_item("red_dot_sight") is False