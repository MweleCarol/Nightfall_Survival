import random

import pytest

from src.ui.effects import EmberField, FogLayer, LightningFlash, RainField


def test_rain_keeps_its_drops_inside_the_screen_area():
    rain = RainField(200, 100, count=50, rng=random.Random(1))
    for _ in range(300):
        rain.update(0.05)
    assert len(rain.drops) == 50
    assert all(-30 <= x <= 260 and y <= 100 for x, y, _speed, _length in rain.drops)


def test_wind_pushes_the_rain_sideways():
    rain = RainField(200, 100, count=1, rng=random.Random(2), wind=-100.0)
    drop = rain.drops[0]
    drop[0], drop[1] = 100.0, 10.0
    rain.update(0.01)
    assert drop[0] == pytest.approx(99.0)


def test_rain_is_repeatable_with_the_same_seed():
    first = RainField(200, 100, count=20, rng=random.Random(5))
    second = RainField(200, 100, count=20, rng=random.Random(5))
    assert first.drops == second.drops


def test_embers_rise_and_then_die_out():
    field = EmberField([(100, 100)], rate=50.0, rng=random.Random(1))
    field.update(0.1)
    assert field.particles and all(e.y < 100 for e in field.particles)
    for _ in range(20):
        field.update(0.1)
    assert 0 < len(field.particles) <= field.max_particles
    field.rate = 0.0
    for _ in range(10):
        field.update(1.0)                     # every ember lives less than 4 seconds
    assert field.particles == []


def test_fog_offset_wraps_around():
    fog = FogLayer(200, 100, speed=50.0)
    for _ in range(10):
        fog.update(0.5)
    assert 0.0 <= fog.offset < 200.0


def test_lightning_strikes_after_the_gap_and_fades():
    bolt = LightningFlash(100, 50, rng=random.Random(1), min_gap=1.0, max_gap=1.0)
    bolt.update(0.5)
    assert bolt.flash == 0.0
    bolt.update(0.6)
    assert bolt.flash == 1.0
    bolt.update(0.1)
    assert bolt.flash == pytest.approx(0.7)
    bolt.update(0.2)
    bolt.update(0.2)
    assert bolt.flash == 0.0