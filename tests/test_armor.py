import pytest

from src.combat.armor import damage_reduction
from src.player.player import Player


def test_no_armor_means_no_reduction():
    assert damage_reduction(0) == 0.0 and damage_reduction(-5) == 0.0


def test_reduction_grows_but_stays_below_the_cap():
    assert damage_reduction(10) < damage_reduction(50)
    assert 0.59 < damage_reduction(100000) < 0.6


def test_armor_has_diminishing_returns():
    assert damage_reduction(60) == pytest.approx(0.3)
    assert damage_reduction(60) - damage_reduction(30) > damage_reduction(90) - damage_reduction(60)


def test_armor_reduces_the_damage_the_player_takes():
    player = Player((1000, 1000))
    player.armor = 60
    assert player.take_damage(10) == 7 and player.stats.health == 93
    assert player.take_damage(1) == 1                     # a hit is never reduced to nothing


def test_an_unarmored_player_takes_full_damage():
    player = Player((1000, 1000))
    assert player.take_damage(10) == 10 and player.take_damage(0) == 0