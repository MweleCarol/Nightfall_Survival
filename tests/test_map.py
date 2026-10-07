import pygame
import pytest

from src.core import settings
from src.services.data_loader import DataLoadError, load_json
from src.world.map import GameMap


@pytest.fixture(scope="module")
def city() -> GameMap:
    return GameMap.load(settings.DEFAULT_MAP)


def test_map_loads(city):
    assert city.name == "Abandoned City District"
    assert len(city.buildings) >= 10 and city.loot_points and city.spawn_zones


def test_size_matches_settings(city):
    assert (city.width, city.height) == (settings.WORLD_WIDTH, settings.WORLD_HEIGHT)


def test_spawn_is_free(city):
    rect = pygame.Rect(0, 0, settings.PLAYER_SIZE, settings.PLAYER_SIZE)
    rect.center = city.player_spawn
    assert rect.collidelist(city.walls) == -1


def test_walls_inside_world(city):
    world = pygame.Rect(0, 0, city.width, city.height)
    assert all(world.contains(wall) for wall in city.walls)


def test_loot_and_lights_not_inside_walls(city):
    points = [lp.pos for lp in city.loot_points] + city.street_lights
    for pos in points:
        assert not any(wall.collidepoint(pos) for wall in city.walls), pos


def test_spawn_zones_clear_and_inside_world(city):
    world = pygame.Rect(0, 0, city.width, city.height)
    for zone in city.spawn_zones:
        assert world.contains(zone.rect), zone.id
        assert zone.rect.collidelist(city.walls) == -1, zone.id


def test_safehouse_setup(city):
    assert city.safehouse.type == "safehouse"
    door = city.interactables[0].rect
    assert door.collidelist(city.walls) == -1
    assert city.safe_zone.contains(door)


def test_missing_field_raises():
    data = load_json(settings.DEFAULT_MAP)
    del data["buildings"]
    with pytest.raises(DataLoadError, match="buildings"):
        GameMap(data)


def test_bad_rect_raises():
    data = load_json(settings.DEFAULT_MAP)
    data["buildings"][0]["rect"] = [1, 2, 3]
    with pytest.raises(DataLoadError, match="rect"):
        GameMap(data)


def test_missing_file_raises():
    with pytest.raises(DataLoadError, match="Missing"):
        load_json("data/maps/does_not_exist.json")


def test_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataLoadError, match="Invalid JSON"):
        load_json(str(bad))


def test_stations_exist_and_are_safe_and_reachable(city):
    kinds = {item.kind for item in city.interactables}
    assert {"rest", "workbench", "weapon_station"} <= kinds
    for item in city.interactables:
        assert item.rect.collidelist(city.walls) == -1, item.id
        assert city.safe_zone.contains(item.rect), item.id