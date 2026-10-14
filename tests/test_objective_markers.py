import pytest
from pygame import Vector2

from src.core import settings
from src.enemies.boss import load_boss_defs
from src.player.inventory import load_item_defs
from src.systems.mission_system import load_missions
from src.ui.objective_markers import build_marker_sources, next_marker, objective_marker
from src.world.arena import load_arenas
from src.world.map import GameMap
from src.world.story_world import load_story_world


@pytest.fixture(scope="module")
def data() -> dict:
    items = load_item_defs()
    world = load_story_world(items)
    city = GameMap.load(settings.DEFAULT_MAP)
    arenas = load_arenas(set(load_boss_defs(items))).values()
    return {"missions": load_missions(items),
            "sources": build_marker_sources(world.locations, world.objects, city.interactables, arenas)}


def objective_of(data, mission_id: str, index: int):
    return data["missions"][mission_id].objectives[index]


def test_reaching_a_location_points_at_its_centre(data):
    marker = objective_marker(objective_of(data, "follow_the_signal", 0), data["sources"])
    assert marker == Vector2(2150, 665)


def test_interacting_points_at_the_object(data):
    marker = objective_marker(objective_of(data, "the_radio", 1), data["sources"])
    assert marker == Vector2(2600, 450)


def test_interacting_with_a_station_points_at_the_station(data):
    marker = objective_marker(objective_of(data, "the_truth", 0), data["sources"])
    assert marker == Vector2(2350, 1115)


def test_collecting_an_item_points_at_where_it_is_found(data):
    marker = objective_marker(objective_of(data, "the_radio", 2), data["sources"])
    assert marker == Vector2(2600, 340)


def test_defeating_a_boss_points_at_its_arena(data):
    assert objective_marker(objective_of(data, "the_butcher", 0), data["sources"]) == Vector2(500, 1500)
    assert objective_marker(objective_of(data, "clear_the_streets", 0), data["sources"]) is None


def test_the_next_marker_skips_finished_and_placeless_objectives(data):
    mission = data["missions"]["the_radio"]
    done = {0}
    assert next_marker(mission, lambda i: i in done, data["sources"]) == Vector2(2600, 450)
    done = {0, 1}
    assert next_marker(mission, lambda i: i in done, data["sources"]) == Vector2(2600, 340)
    done = {0, 1, 2}
    assert next_marker(mission, lambda i: i in done, data["sources"]) is None
    assert next_marker(data["missions"]["clear_the_streets"], lambda i: False, data["sources"]) is None