from src.player.stats import Stats


def test_heal_cannot_exceed_max():
    s = Stats(max_health=100, health=80)
    assert s.heal(50) == 20
    assert s.health == 100


def test_damage_cannot_go_below_zero_and_kills():
    s = Stats(max_health=100, health=10)
    assert s.take_damage(50) == 10
    assert s.health == 0 and s.is_dead


def test_dead_cannot_be_healed():
    s = Stats(max_health=100, health=0)
    assert s.heal(20) == 0


def test_sprint_drains_then_regen_after_delay():
    s = Stats(max_stamina=100, drain_rate=25, regen_rate=15, regen_delay=1.0)
    s.update_stamina(1.0, sprinting=True)
    assert s.stamina == 75
    s.update_stamina(1.5, sprinting=False)   # still waiting out the delay
    assert s.stamina == 75
    s.update_stamina(1.0, sprinting=False)   # regen begins
    assert s.stamina == 90


def test_stamina_never_negative():
    s = Stats(max_stamina=10, stamina=1, drain_rate=100)
    s.update_stamina(1.0, sprinting=True)
    assert s.stamina == 0