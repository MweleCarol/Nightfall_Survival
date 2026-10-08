import pygame
import pytest

from src.core import settings
from src.enemies.enemy import load_enemy_defs
from src.player.inventory import load_item_defs
from src.services.data_loader import DataLoadError
from src.systems.mission_system import load_missions, validate_references
from src.systems.story import load_story_data
from src.world.map import GameMap
from src.world.story_world import load_story_world, parse_story_world


@pytest.fixture(scope="module")
def content() -> dict:
    items = load_item_defs()
    return {
        "items": items,
        "world": load_story_world(items),
        "missions": load_missions(items),
        "story": load_story_data(),
        "map": GameMap.load(settings.DEFAULT_MAP),
    }


def raw_object(**overrides) -> dict:
    data = {"id": "x", "kind": "device", "name": "X", "pos": [100, 100], "prompt": "Press E"}
    data.update(overrides)
    return data


def test_every_mission_reference_is_valid(content):
    world, city = content["world"], content["map"]
    problems = validate_references(
        content["missions"],
        {loc.id for loc in world.locations},
        {obj.id for obj in world.objects} | {item.id for item in city.interactables},
        set(load_enemy_defs()))
    assert problems == []


def test_unlocked_chapters_exist(content):
    for mission in content["missions"].values():
        chapter = mission.rewards.unlock_chapter
        assert chapter is None or chapter in content["story"].chapters, mission.id


def test_story_missions_belong_to_real_chapters(content):
    for mission in content["missions"].values():
        if mission.category == "story":
            assert mission.chapter in content["story"].chapters, mission.id


def test_radio_triggers_reference_real_missions(content):
    for message in content["story"].messages.values():
        if message.trigger_type in ("mission_started", "mission_completed"):
            assert message.trigger_value in content["missions"], message.id


def test_every_note_object_has_text_and_every_note_has_an_object(content):
    note_objects = {o.id for o in content["world"].objects if o.definition.kind == "note"}
    assert note_objects == set(content["story"].notes)


def test_object_gating_points_at_real_missions_and_objects(content):
    ids = {o.id for o in content["world"].objects}
    for obj in content["world"].objects:
        definition = obj.definition
        assert definition.mission is None or definition.mission in content["missions"], obj.id
        assert definition.after is None or definition.after in ids, obj.id


def test_everything_is_placed_in_free_space(content):
    city = content["map"]
    world_rect = pygame.Rect(0, 0, city.width, city.height)
    for obj in content["world"].objects:
        assert world_rect.collidepoint(obj.position), obj.id
        assert not any(wall.collidepoint(obj.position) for wall in city.walls), obj.id
    for location in content["world"].locations:
        assert world_rect.contains(location.rect), location.id
        assert location.rect.collidelist(city.walls) == -1, location.id


def test_quest_items_can_always_be_obtained(content):
    givers = {o.definition.give_item for o in content["world"].objects if o.definition.give_item}
    for mission in content["missions"].values():
        for objective in mission.objectives:
            if objective.type == "collect_item" and content["items"][objective.target].type == "quest":
                assert objective.target in givers, objective.target


def test_a_mission_is_available_from_the_start(content):
    assert any(not mission.requires for mission in content["missions"].values())


def test_board_and_radio_stations_exist(content):
    kinds = {item.kind for item in content["map"].interactables}
    assert {"missions", "radio"} <= kinds


def test_unknown_object_kind_is_rejected(content):
    data = {"story_objects": [raw_object(kind="portal")]}
    with pytest.raises(DataLoadError, match="kind"):
        parse_story_world(data, content["items"], "test")


def test_item_object_needs_give_item(content):
    data = {"story_objects": [raw_object(kind="item")]}
    with pytest.raises(DataLoadError, match="give_item"):
        parse_story_world(data, content["items"], "test")


def test_item_object_with_unknown_item_is_rejected(content):
    data = {"story_objects": [raw_object(kind="item", give_item="ghost")]}
    with pytest.raises(DataLoadError, match="ghost"):
        parse_story_world(data, content["items"], "test")