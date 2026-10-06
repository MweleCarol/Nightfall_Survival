from tests.factories import make_weapon


def test_fire_consumes_ammo_and_starts_cooldown():
    w = make_weapon(fire_rate=4.0)
    assert w.fire() is True
    assert w.loaded == 11
    assert w.can_fire() is False


def test_cooldown_expires():
    w = make_weapon(fire_rate=4.0)
    w.fire()
    w.update(0.25)
    assert w.can_fire() is True


def test_cannot_fire_empty_magazine():
    w = make_weapon(loaded=0)
    assert w.fire() is False
    assert w.loaded == 0


def test_reload_takes_time_then_fills_magazine():
    w = make_weapon(loaded=5, reserve=30, reload_time=1.5)
    assert w.start_reload() is True
    w.update(1.0)
    assert w.is_reloading and w.loaded == 5
    w.update(0.5)
    assert not w.is_reloading
    assert w.loaded == 12 and w.reserve == 23


def test_reload_limited_by_reserve():
    w = make_weapon(loaded=0, reserve=5)
    w.start_reload()
    w.update(1.5)
    assert w.loaded == 5 and w.reserve == 0


def test_reload_never_exceeds_magazine():
    w = make_weapon(loaded=11, reserve=30)
    w.start_reload()
    w.update(1.5)
    assert w.loaded == 12 and w.reserve == 29


def test_pointless_reloads_are_refused():
    assert make_weapon(loaded=12, reserve=30).start_reload() is False   # full
    assert make_weapon(loaded=3, reserve=0).start_reload() is False     # no spare ammo


def test_cannot_fire_while_reloading():
    w = make_weapon(loaded=5)
    w.start_reload()
    assert w.fire() is False
    assert w.loaded == 5


def test_reload_progress():
    w = make_weapon(loaded=0, reload_time=2.0)
    w.start_reload()
    w.update(0.5)
    assert abs(w.reload_progress - 0.25) < 1e-9