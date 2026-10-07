from src.core.event_bus import EventBus
from src.systems.progression import Progression


def make(**overrides) -> Progression:
    values = dict(base_xp=100, growth=1.5, max_level=10)
    values.update(overrides)
    return Progression(**values)


def test_xp_required_follows_the_formula():
    p = make()
    assert [p.xp_required(level) for level in (1, 2, 3)] == [100, 150, 225]


def test_small_xp_does_not_level_up():
    p = make()
    assert p.add_xp(40) == 0
    assert (p.level, p.xp, p.skill_points) == (1, 40, 0)


def test_level_up_carries_leftover_xp_and_grants_a_point():
    p = make()
    assert p.add_xp(150) == 1
    assert (p.level, p.xp, p.skill_points) == (2, 50, 1)


def test_one_big_reward_can_level_several_times():
    p = make(max_level=20)
    gained = p.add_xp(1000)
    assert gained > 1
    assert p.level == 1 + gained and p.skill_points == gained


def test_xp_and_level_events_are_emitted():
    bus, levels, gains = EventBus(), [], []
    bus.on("LEVEL_UP", levels.append)
    bus.on("XP_GAINED", gains.append)
    p = make(event_bus=bus)
    p.add_xp(260)                                 # 100 -> level 2, 150 -> level 3
    assert gains == [{"amount": 260}]
    assert [event["level"] for event in levels] == [2, 3]


def test_max_level_caps_and_discards_extra_xp():
    p = make(max_level=3)
    p.add_xp(100000)
    assert p.level == 3 and p.xp == 0 and p.is_max_level and p.progress == 1.0
    assert p.add_xp(50) == 0


def test_spend_skill_point():
    p = make()
    p.add_xp(100)
    assert p.spend_skill_point() is True and p.skill_points == 0
    assert p.spend_skill_point() is False


def test_non_positive_xp_is_ignored():
    p = make()
    assert p.add_xp(0) == 0 and p.add_xp(-5) == 0
    assert p.xp == 0


def test_serialize_round_trip():
    p = make()
    p.add_xp(160)
    clone = Progression.deserialize(p.serialize(), base_xp=100, growth=1.5, max_level=10)
    assert (clone.level, clone.xp, clone.skill_points) == (p.level, p.xp, p.skill_points)


def test_bad_saved_data_falls_back_to_defaults():
    p = Progression.deserialize({"level": "x", "xp": -4, "skill_points": None})
    assert (p.level, p.xp, p.skill_points) == (1, 0, 0)


def test_progress_fraction():
    p = make()
    p.add_xp(50)
    assert p.progress == 0.5