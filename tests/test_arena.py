import pygame
import pytest

from src.core import settings
from src.enemies.boss import load_boss_defs
from src.player.inventory import load_item_defs
from src.services.data_loader import DataLoadError
from src.systems.mission_system import load_missions
from src.world.arena import Arena, ArenaDef, ArenaState, load_arenas, parse_arenas
from src.world.map import GameMap

CELL = 20


@pytest.fixture(scope="module")
def content() -> dict:
    items = load_item_defs()
    bosses = load_boss_defs(items)
    return {"bosses": bosses, "arenas": load_arenas(set(bosses)),
            "missions": load_missions(items), "city": GameMap.load(settings.DEFAULT_MAP)}


def flood(start, blockers, width, height) -> set[tuple[int, int]]:
    """Every point (sampled on a grid) a walker could reach from `start`."""
    cols, rows = width // CELL, height // CELL

    def free(cx: int, cy: int) -> bool:
        point = (cx * CELL + CELL // 2, cy * CELL + CELL // 2)
        return not any(rect.collidepoint(point) for rect in blockers)

    first = (start[0] // CELL, start[1] // CELL)
    seen, stack = {first}, [first]
    while stack:
        cx, cy = stack.pop()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in seen and free(nx, ny):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return {(cx * CELL + CELL // 2, cy * CELL + CELL // 2) for cx, cy in seen}


def raw_arena(**overrides) -> dict:
    data = {"id": "a", "name": "A", "boss": "the_butcher", "rect": [0, 0, 100, 100],
            "boss_spawn": [50, 50], "barriers": [[100, 0, 10, 100]]}
    data.update(overrides)
    return data


def make_arena() -> Arena:
    return Arena(ArenaDef("a", "A", "boss", None, pygame.Rect(0, 0, 200, 200), (100, 100),
                          (pygame.Rect(200, 0, 20, 200),)))


def test_arenas_reference_real_bosses_and_missions(content):
    for arena in content["arenas"].values():
        assert arena.boss_id in content["bosses"]
        assert arena.mission is None or arena.mission in content["missions"]


def test_arena_geometry_is_sound(content):
    arena, city = content["arenas"]["butcher_yard"], content["city"]
    world = pygame.Rect(0, 0, city.width, city.height)
    assert world.contains(arena.rect)
    for barrier in arena.barriers:
        assert world.contains(barrier)
        assert not barrier.colliderect(arena.rect), "a gate would trap the player"
    spawn = pygame.Rect(0, 0, 68, 68)
    spawn.center = arena.boss_spawn
    assert arena.rect.contains(spawn)
    assert spawn.collidelist(city.walls + list(arena.barriers)) == -1
    assert not city.safe_zone.colliderect(arena.rect)


def test_the_gates_seal_the_arena(content):
    arena, city = content["arenas"]["butcher_yard"], content["city"]
    reachable = flood(arena.boss_spawn, city.walls + list(arena.barriers), city.width, city.height)
    assert all(arena.rect.collidepoint(point) for point in reachable)


def test_without_the_gates_the_arena_leaks(content):
    arena, city = content["arenas"]["butcher_yard"], content["city"]
    reachable = flood(arena.boss_spawn, city.walls, city.width, city.height)
    assert any(not arena.rect.collidepoint(point) for point in reachable)


def test_trigger_needs_everything():
    arena = make_arena()
    inside, partly = pygame.Rect(50, 50, 32, 32), pygame.Rect(190, 50, 32, 32)
    assert arena.can_trigger(inside, True, True) is True
    assert arena.can_trigger(partly, True, True) is False
    assert arena.can_trigger(inside, False, True) is False
    assert arena.can_trigger(inside, True, False) is False


def test_barriers_only_exist_during_the_fight():
    arena, inside = make_arena(), pygame.Rect(50, 50, 32, 32)
    assert arena.barriers == []
    arena.start()
    assert arena.state is ArenaState.ACTIVE and len(arena.barriers) == 1
    assert arena.can_trigger(inside, True, True) is False
    arena.clear()
    assert arena.state is ArenaState.CLEARED and arena.barriers == []
    assert arena.can_trigger(inside, True, True) is False


def test_unknown_boss_is_rejected():
    with pytest.raises(DataLoadError, match="ghost"):
        parse_arenas({"arenas": [raw_arena(boss="ghost")]}, {"the_butcher"}, "test")


def test_bad_barrier_rect_is_rejected():
    with pytest.raises(DataLoadError, match="rect"):
        parse_arenas({"arenas": [raw_arena(barriers=[[1, 2, 3]])]}, {"the_butcher"}, "test")