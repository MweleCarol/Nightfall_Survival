from pygame import Vector2

from src.player.player import Player


def test_bonuses_raise_the_maximum_and_grant_the_difference():
    player = Player((1000, 1000))
    player.stats.health = 60
    player.apply_bonuses(health_bonus=20, stamina_bonus=10, speed_bonus=0.0)
    assert player.stats.max_health == 120 and player.stats.health == 80
    assert player.stats.max_stamina == 110 and player.stats.stamina == 110


def test_speed_bonus_moves_the_player_further():
    base, fast = Player((1000, 1000)), Player((1000, 1000))
    fast.apply_bonuses(0, 0.0, 0.5)
    base.update(0.1, Vector2(1, 0), False, [])
    fast.update(0.1, Vector2(1, 0), False, [])
    assert abs((fast.position.x - 1000) - 1.5 * (base.position.x - 1000)) < 1e-9


def test_dead_player_is_not_healed_by_bonuses():
    player = Player((1000, 1000))
    player.stats.health = 0
    player.apply_bonuses(health_bonus=20, stamina_bonus=0.0, speed_bonus=0.0)
    assert player.stats.health == 0