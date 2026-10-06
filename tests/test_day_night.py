import pytest

from src.core.event_bus import EventBus
from src.world.day_night import DayNightCycle


def make(day=10.0, night=6.0, bus=None):
    return DayNightCycle(day_duration=day, night_duration=night, event_bus=bus)


def test_starts_in_day_at_eight():
    c = make()
    assert c.is_day and c.day_number == 1 and c.clock_text() == "08:00"


def test_day_becomes_night_after_duration():
    c = make()
    c.update(9.9)
    assert c.is_day
    c.update(0.2)
    assert c.is_night


def test_night_becomes_next_day():
    c = make()
    c.update(10.0)
    assert c.is_night
    c.update(6.0)
    assert c.is_day and c.day_number == 2


def test_large_dt_crosses_several_phases():
    c = make()
    c.update(10 + 6 + 3)
    assert c.is_day and c.day_number == 2
    assert abs(c.elapsed - 3) < 1e-9


def test_events_are_emitted_in_order():
    bus, seen = EventBus(), []
    for name in ("NIGHT_STARTED", "NIGHT_COMPLETED", "DAY_STARTED"):
        bus.on(name, lambda data, name=name: seen.append((name, dict(data))))
    c = make(bus=bus)
    c.update(10.0)
    c.update(6.0)
    assert seen == [
        ("NIGHT_STARTED", {"night": 1}),
        ("NIGHT_COMPLETED", {"night": 1}),
        ("DAY_STARTED", {"day": 2}),
    ]


def test_skip_to_next_phase():
    c = make()
    c.skip_to_next_phase()
    assert c.is_night and c.elapsed == 0.0


def test_darkness_rises_smoothly_at_dusk():
    c = make(day=100, night=100)
    values = []
    for _ in range(99):
        c.update(1.0)
        values.append(c.darkness)
    assert all(0.0 <= v <= 1.0 for v in values)
    assert values == sorted(values)
    assert values[-1] > 0.9


def test_darkness_full_at_night_and_clear_at_dawn():
    c = make(day=100, night=100)
    assert c.darkness == 0.0
    c.skip_to_next_phase()
    c.update(50)
    assert c.darkness == 1.0
    c.update(49)
    assert c.darkness < 0.05


def test_clock_text_day_and_night():
    c = make(day=10, night=6)
    c.update(5)
    assert c.clock_text() == "14:00"
    c.skip_to_next_phase()
    assert c.clock_text() == "20:00"
    c.update(3)
    assert c.clock_text() == "02:00"


def test_invalid_durations_rejected():
    with pytest.raises(ValueError):
        DayNightCycle(day_duration=0)