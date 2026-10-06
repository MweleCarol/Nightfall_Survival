from src.combat.damage import calculate_damage


def test_plain_damage():
    assert calculate_damage(25) == 25


def test_armor_reduces_damage():
    assert calculate_damage(25, armor=10) == 15


def test_armor_cannot_make_damage_negative():
    assert calculate_damage(5, armor=50) == 0


def test_critical_multiplies_damage():
    assert calculate_damage(25, critical=True) == 50