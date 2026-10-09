from src.systems.safehouse_rules import NightResult, SafeZoneRules


def test_safe_zone_protects_by_default():
    rules = SafeZoneRules(6.0)
    assert rules.protects(True) is True and not rules.truce_broken


def test_never_protects_outside_the_zone():
    assert SafeZoneRules(6.0).protects(False) is False


def test_shooting_inside_breaks_the_truce():
    rules = SafeZoneRules(6.0)
    assert rules.on_shot_fired(True) is True
    assert rules.truce_broken and rules.protects(True) is False


def test_shooting_outside_does_nothing():
    rules = SafeZoneRules(6.0)
    assert rules.on_shot_fired(False) is False
    assert not rules.truce_broken


def test_truce_returns_after_the_duration():
    rules = SafeZoneRules(6.0)
    rules.on_shot_fired(True)
    rules.update(5.9)
    assert rules.protects(True) is False
    rules.update(0.2)
    assert rules.protects(True) is True


def test_more_shots_restart_the_timer_but_only_the_first_is_news():
    rules = SafeZoneRules(6.0)
    assert rules.on_shot_fired(True) is True
    rules.update(4.0)
    assert rules.on_shot_fired(True) is False
    assert rules.break_remaining == 6.0
    rules.update(5.9)
    assert rules.truce_broken


def test_reset_restores_protection():
    rules = SafeZoneRules(6.0)
    rules.on_shot_fired(True)
    rules.reset()
    assert rules.protects(True) is True


def test_night_counts_only_when_every_wave_was_cleared():
    night = NightResult()
    assert night.counts_as_survived is False
    night.mark_cleared()
    assert night.counts_as_survived is True
    night.start_night()
    assert night.counts_as_survived is False