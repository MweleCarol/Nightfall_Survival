from src.player.inventory import Inventory, ItemDef
from src.combat.weapon import Weapon
from tests.factories import make_weapon_def


def make_inventory(ammo: int) -> Inventory:
    defs = {"ammo_9mm": ItemDef("ammo_9mm", "9mm Ammo", "ammo", 60, "common")}
    inventory = Inventory(10, defs)
    inventory.add("ammo_9mm", ammo)
    return inventory


def test_reserve_reads_from_the_inventory():
    weapon = Weapon(make_weapon_def(), ammo_source=make_inventory(30))
    assert weapon.reserve == 30


def test_reload_consumes_inventory_ammo():
    inventory = make_inventory(30)
    weapon = Weapon(make_weapon_def(), loaded=5, ammo_source=inventory)
    weapon.start_reload()
    weapon.update(1.5)
    assert weapon.loaded == 12 and inventory.count("ammo_9mm") == 23


def test_reload_limited_by_inventory_ammo():
    inventory = make_inventory(3)
    weapon = Weapon(make_weapon_def(), loaded=0, ammo_source=inventory)
    weapon.start_reload()
    weapon.update(1.5)
    assert weapon.loaded == 3 and inventory.count("ammo_9mm") == 0


def test_reload_refused_with_no_ammo_in_inventory():
    weapon = Weapon(make_weapon_def(), loaded=0, ammo_source=make_inventory(0))
    assert weapon.start_reload() is False