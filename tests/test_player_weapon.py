from pygame import Vector2

from src.player.player import Player
from tests.factories import make_weapon


def test_player_update_ticks_weapon_cooldown():
    weapon = make_weapon(fire_rate=4.0)
    player = Player((1000, 1000), weapon)
    weapon.fire()
    assert not weapon.can_fire()
    player.update(0.25, Vector2(0, 0), False, [])
    assert weapon.can_fire()


def test_take_damage_reduces_health_and_flashes():
    player = Player((1000, 1000))
    assert player.take_damage(10) == 10
    assert player.stats.health == 90 and player.hurt_timer > 0


def test_hurt_flash_decays():
    player = Player((1000, 1000))
    player.take_damage(10)
    player.update(1.0, Vector2(0, 0), False, [])
    assert player.hurt_timer == 0


def test_player_without_weapon_still_updates():
    player = Player((1000, 1000))
    player.update(0.1, Vector2(1, 0), False, [])
    assert player.position.x > 1000