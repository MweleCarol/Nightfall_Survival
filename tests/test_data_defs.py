import pytest

from src.combat.weapon import WeaponDef, load_weapon_defs
from src.core import settings
from src.enemies.enemy import EnemyDef, load_enemy_defs
from src.enemies.factory import EnemyFactory
from src.enemies.walker import Walker
from src.services.data_loader import DataLoadError

GOOD_WEAPON = {
    "id": "x", "name": "X", "damage": 20, "fire_rate": 4, "magazine_size": 10,
    "ammo_type": "9mm", "reload_time": 1.0, "range": 400, "spread": 1.0,
    "rarity": "common", "automatic": False,
}


def test_shipped_weapons_load():
    defs = load_weapon_defs()
    assert settings.PLAYER_START_WEAPON in defs
    pistol = defs["pistol_01"]
    assert pistol.damage == 25 and pistol.magazine_size == 12


def test_shipped_enemies_load():
    walker = load_enemy_defs()["walker"]
    assert walker.max_health > 0 and walker.speed > 0 and len(walker.color) == 3


def test_weapon_missing_field_names_the_field():
    data = dict(GOOD_WEAPON)
    del data["damage"]
    with pytest.raises(DataLoadError, match="damage"):
        WeaponDef.from_dict(data, "test")


def test_weapon_non_positive_damage_rejected():
    data = dict(GOOD_WEAPON, damage=0)
    with pytest.raises(DataLoadError):
        WeaponDef.from_dict(data, "test")


def test_enemy_bad_color_rejected():
    data = {
        "id": "x", "name": "X", "type": "walker", "max_health": 10, "speed": 50,
        "detection_range": 100, "attack_range": 30, "attack_damage": 5,
        "attack_cooldown": 1.0, "attack_windup": 0.3, "search_time": 2.0,
        "xp_reward": 5, "radius": 12, "color": [300, 0, 0],
    }
    with pytest.raises(DataLoadError, match="color"):
        EnemyDef.from_dict(data, "test")


def test_factory_builds_walker_from_data():
    enemy = EnemyFactory().create("walker", (500, 500))
    assert isinstance(enemy, Walker)
    assert enemy.health == enemy.definition.max_health


def test_factory_unknown_enemy_raises():
    with pytest.raises(DataLoadError, match="Unknown enemy"):
        EnemyFactory().create("dragon", (0, 0))