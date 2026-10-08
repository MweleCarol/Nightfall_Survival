import pytest

from src.core.event_bus import EventBus
from src.player.inventory import load_item_defs
from src.services.data_loader import DataLoadError
from src.systems.mission_system import (
    MissionDef, MissionManager, MissionStatus, ObjectiveDef, Rewards, parse_missions,
)

ACTIVE, AVAILABLE = MissionStatus.ACTIVE, MissionStatus.AVAILABLE
COMPLETED, FAILED, LOCKED = MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.LOCKED


def obj(kind: str, target="any", quantity: int = 1) -> ObjectiveDef:
    return ObjectiveDef(kind, str(target), quantity, f"{kind} {target}")


def mission(mission_id: str, objectives, requires=(), deadline_day=None) -> MissionDef:
    return MissionDef(
        id=mission_id, title=mission_id.title(), description="d", category="story", chapter=1,
        objectives=tuple(objectives), rewards=Rewards(xp=10, items={}, unlock_chapter=None),
        requires=tuple(requires), deadline_day=deadline_day)


def manager(*missions: MissionDef, bus=None) -> MissionManager:
    return MissionManager({m.id: m for m in missions}, bus)


def raw_mission(**overrides) -> dict:
    data = {"id": "a", "title": "A", "description": "d", "category": "story", "chapter": 1,
            "requires": [],
            "objectives": [{"type": "defeat_enemy", "target": "any", "quantity": 1,
                            "description": "Kill"}],
            "rewards": {"xp": 10}}
    data.update(overrides)
    return data


def test_missions_without_requirements_start_available():
    m = manager(mission("a", [obj("defeat_enemy")]),
                mission("b", [obj("defeat_enemy")], requires=["a"]))
    assert m.status["a"] is AVAILABLE and m.status["b"] is LOCKED


def test_start_activates_the_mission_and_emits_an_event():
    bus, started = EventBus(), []
    bus.on("MISSION_STARTED", started.append)
    m = manager(mission("a", [obj("defeat_enemy")]), bus=bus)
    assert m.start("a") is True
    assert m.status["a"] is ACTIVE and started == [{"id": "a"}]


def test_cannot_start_locked_active_or_unknown_missions():
    m = manager(mission("a", [obj("defeat_enemy")]),
                mission("b", [obj("defeat_enemy")], requires=["a"]))
    assert m.start("b") is False
    assert m.start("a") is True
    assert m.start("a") is False
    assert m.start("ghost") is False


def test_active_limit_is_respected():
    m = manager(*(mission(name, [obj("defeat_enemy")]) for name in "abc"))
    assert m.start("a", max_active=2) and m.start("b", max_active=2)
    assert m.start("c", max_active=2) is False


def test_defeat_enemy_matches_a_type_or_any():
    m = manager(mission("a", [obj("defeat_enemy", "stalker", 2)]),
                mission("b", [obj("defeat_enemy", "any", 2)]))
    m.start("a")
    m.start("b")
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    assert m.progress["a"] == [0] and m.progress["b"] == [1]
    m.notify("ENEMY_DIED", {"enemy_id": "stalker"})
    assert m.progress["a"] == [1] and m.progress["b"] == [2]


def test_mission_completes_when_every_objective_is_done():
    bus, done = EventBus(), []
    bus.on("MISSION_COMPLETED", done.append)
    m = manager(mission("a", [obj("defeat_enemy", "any", 2), obj("reach_location", "dock")]), bus=bus)
    m.start("a")
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    assert m.status["a"] is ACTIVE                       # the second objective is missing
    assert m.notify("LOCATION_REACHED", {"location": "dock"}) == ["a"]
    assert m.status["a"] is COMPLETED and done == [{"id": "a"}]


def test_only_active_missions_make_progress():
    m = manager(mission("a", [obj("defeat_enemy", "any", 2)]))
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    assert m.progress["a"] == [0]


def test_completing_a_mission_unlocks_the_ones_that_need_it():
    m = manager(mission("a", [obj("defeat_enemy")]),
                mission("b", [obj("defeat_enemy")], requires=["a"]))
    m.start("a")
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    assert m.status["b"] is AVAILABLE


def test_collect_item_adds_quantities_and_caps_at_the_goal():
    m = manager(mission("a", [obj("collect_item", "scrap", 10)]))
    m.start("a")
    m.notify("ITEM_COLLECTED", {"item": "scrap", "quantity": 4})
    m.notify("ITEM_COLLECTED", {"item": "bandage", "quantity": 9})
    assert m.progress["a"] == [4]
    m.notify("ITEM_COLLECTED", {"item": "scrap", "quantity": 50})
    assert m.status["a"] is COMPLETED and m.progress["a"] == [10]


def test_location_interact_and_search_objectives():
    m = manager(mission("a", [obj("reach_location", "dock"), obj("interact", "gen"),
                              obj("search_containers", "any", 2)]))
    m.start("a")
    m.notify("LOCATION_REACHED", {"location": "elsewhere"})
    assert m.progress["a"] == [0, 0, 0]
    m.notify("LOCATION_REACHED", {"location": "dock"})
    m.notify("OBJECT_INTERACTED", {"id": "gen"})
    m.notify("CONTAINER_SEARCHED", {})
    assert m.progress["a"] == [1, 1, 1]


def test_survive_wave_and_night_mean_at_least():
    m = manager(mission("a", [obj("survive_wave", 3), obj("survive_night", 2)]))
    m.start("a")
    m.notify("WAVE_COMPLETED", {"night": 1, "wave": 2})
    m.notify("NIGHT_COMPLETED", {"night": 1})
    assert m.progress["a"] == [0, 0]
    m.notify("WAVE_COMPLETED", {"night": 1, "wave": 3})
    m.notify("NIGHT_COMPLETED", {"night": 5})
    assert m.status["a"] is COMPLETED


def test_missed_deadline_fails_active_and_available_missions():
    bus, failed = EventBus(), []
    bus.on("MISSION_FAILED", failed.append)
    m = manager(mission("a", [obj("defeat_enemy")], deadline_day=3),
                mission("b", [obj("defeat_enemy")], deadline_day=3), bus=bus)
    m.start("a")
    m.notify("DAY_STARTED", {"day": 3})
    assert m.status["a"] is ACTIVE and m.status["b"] is AVAILABLE
    m.notify("DAY_STARTED", {"day": 4})
    assert m.status["a"] is FAILED and m.status["b"] is FAILED
    assert failed == [{"id": "a"}, {"id": "b"}]


def test_completed_missions_ignore_deadlines():
    m = manager(mission("a", [obj("defeat_enemy")], deadline_day=2))
    m.start("a")
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    m.notify("DAY_STARTED", {"day": 9})
    assert m.status["a"] is COMPLETED


def test_fail_works_once():
    m = manager(mission("a", [obj("defeat_enemy")]))
    m.start("a")
    assert m.fail("a") is True and m.status["a"] is FAILED
    assert m.fail("a") is False and m.fail("ghost") is False


def test_force_complete_fills_every_objective():
    m = manager(mission("a", [obj("defeat_enemy", "any", 3), obj("reach_location", "dock")]))
    assert m.force_complete("a") is False                # not active yet
    m.start("a")
    assert m.force_complete("a") is True
    assert m.status["a"] is COMPLETED and m.progress["a"] == [3, 1]


def test_serialize_round_trip():
    missions = {m.id: m for m in (mission("a", [obj("defeat_enemy", "any", 2)]),
                                  mission("b", [obj("defeat_enemy")], requires=["a"]))}
    m = MissionManager(missions)
    m.start("a")
    m.notify("ENEMY_DIED", {"enemy_id": "walker"})
    clone = MissionManager.deserialize(m.serialize(), missions)
    assert clone.status == m.status and clone.progress == m.progress


def test_deserialize_ignores_garbage():
    missions = {"a": mission("a", [obj("defeat_enemy")])}
    clone = MissionManager.deserialize(
        {"status": {"a": "BOGUS", "ghost": "ACTIVE"}, "progress": {"a": "x"}}, missions)
    assert clone.status["a"] is AVAILABLE and clone.progress["a"] == [0]


def test_unknown_objective_type_is_rejected():
    raw = raw_mission(objectives=[{"type": "dance", "description": "d"}])
    with pytest.raises(DataLoadError, match="type"):
        MissionDef.from_dict(raw, load_item_defs(), "test")


def test_unknown_reward_item_is_rejected():
    with pytest.raises(DataLoadError, match="ghost"):
        MissionDef.from_dict(raw_mission(rewards={"items": {"ghost": 1}}), load_item_defs(), "test")


def test_targeted_objective_needs_a_target():
    raw = raw_mission(objectives=[{"type": "reach_location", "description": "d"}])
    with pytest.raises(DataLoadError, match="target"):
        MissionDef.from_dict(raw, load_item_defs(), "test")


def test_requiring_an_unknown_mission_is_rejected():
    data = {"missions": [raw_mission(requires=["ghost"])]}
    with pytest.raises(DataLoadError, match="ghost"):
        parse_missions(data, load_item_defs(), "test")


def test_circular_requirements_are_rejected():
    data = {"missions": [raw_mission(id="a", requires=["b"]), raw_mission(id="b", requires=["a"])]}
    with pytest.raises(DataLoadError, match="never"):
        parse_missions(data, load_item_defs(), "test")