import pygame
import pytest
from pygame import Vector2

from src.combat.grenade import (
    Grenade, GrenadeDef, GrenadeSystem, blast_damage, load_grenade_defs,
)
from src.core import settings
from src.core.event_bus import EventBus
from src.player.inventory import Inventory, load_item_defs
from src.player.player import Player
from src.services.data_loader import DataLoadError
from src.systems.crafting import load_crafting_data
from tests.factories import make_enemy
from tests.test_boss import make_boss

ORIGIN = Vector2(0, 0)


def make_def(**overrides) -> GrenadeDef:
    values = dict(id="grenade", name="Frag Grenade", damage=100, radius=100.0, fuse=1.0,
                  throw_speed=500.0, max_range=400.0, knockback=60.0, self_damage_factor=0.5)
    values.update(overrides)
    return GrenadeDef(**values)


def raw_grenade(**overrides) -> dict:
    data = {"id": "grenade", "name": "Frag", "damage": 100, "radius": 100, "fuse": 1.0,
            "throw_speed": 500, "max_range": 400, "knockback": 60, "self_damage_factor": 0.5}
    data.update(overrides)
    return data


def boom(enemies=(), walls=(), player=None, definition=None, bus=None) -> GrenadeSystem:
    """Throw a grenade at its own feet and let the fuse run out."""
    system = GrenadeSystem(bus)
    system.throw(definition or make_def(), ORIGIN, ORIGIN)
    system.update(1.0, list(enemies), player or Player((1000, 1000)), list(walls))
    return system


def test_blast_damage_falls_off_with_distance():
    definition = make_def()
    assert blast_damage(definition, 0) == 100
    assert blast_damage(definition, 50) == 70
    assert blast_damage(definition, 99) > 0
    assert blast_damage(definition, 100) == 0 and blast_damage(definition, 500) == 0


def test_a_grenade_flies_to_the_target_and_explodes_when_the_fuse_ends():
    grenade = Grenade(make_def(), ORIGIN, Vector2(400, 0))
    assert grenade.update(0.5, []) is False
    assert grenade.position.x == pytest.approx(250)
    assert grenade.update(0.5, []) is True
    assert grenade.position.x == pytest.approx(400)


def test_throws_are_limited_to_the_maximum_range():
    grenade = Grenade(make_def(max_range=400.0), ORIGIN, Vector2(5000, 0))
    assert grenade.travel_left == 400.0


def test_grenades_stop_at_walls():
    wall = pygame.Rect(100, -50, 20, 100)
    grenade = Grenade(make_def(), ORIGIN, Vector2(300, 0))
    grenade.update(0.5, [wall])
    assert grenade.rect.right <= wall.left and grenade.travel_left == 0.0


def test_the_blast_hurts_near_enemies_more_than_far_ones():
    near, mid, far = make_enemy((50, 0), max_health=200), make_enemy((100, 0), max_health=200), \
        make_enemy((300, 0), max_health=200)
    boom([near, mid, far])
    assert near.health == 200 - 80
    assert mid.health == 200 - 50
    assert far.health == 200


def test_walls_shield_enemies_from_the_blast():
    wall = pygame.Rect(20, -50, 10, 100)
    enemy = make_enemy((50, 0), max_health=200)
    boom([enemy], [wall])
    assert enemy.health == 200


def test_kills_report_hit_and_death_events():
    bus, hits, deaths = EventBus(), [], []
    bus.on("ENEMY_HIT", hits.append)
    bus.on("ENEMY_DIED", deaths.append)
    enemy = make_enemy((30, 0), max_health=50)
    boom([enemy], bus=bus)
    assert enemy.is_dead
    assert hits[0]["damage"] == 50 and hits[0]["direction"] == pytest.approx((1, 0))
    assert deaths[0]["enemy_id"] == "test_walker" and deaths[0]["xp"] == enemy.xp_reward
    assert deaths[0]["position"] == pytest.approx((30, 0))


def test_enemies_are_knocked_back_away_from_the_blast():
    enemy = make_enemy((50, 0), max_health=500)
    boom([enemy])
    assert enemy.position.x > 80        # shoved away from the blast along x
    assert enemy.position.y >= 0        # and never out of the world (the top edge is y=0)


def test_knockback_stops_at_walls():
    wall = pygame.Rect(75, -50, 10, 100)
    enemy = make_enemy((50, 0), max_health=500)
    boom([enemy], [wall])
    assert enemy.rect.right <= wall.left


def test_bosses_are_not_knocked_back():
    boss = make_enemy((50, 0), max_health=500, type="boss")
    boom([boss])
    assert boss.health < 500 and boss.position.x == pytest.approx(50)


def test_a_boss_in_its_intro_is_unharmed():
    bus, hits = EventBus(), []
    bus.on("ENEMY_HIT", hits.append)
    boss = make_boss((50, 0))
    boom([boss], bus=bus)
    assert boss.health == boss.max_health and hits == []


def test_the_player_takes_reduced_damage_and_it_is_reported():
    bus, damaged = EventBus(), []
    bus.on("PLAYER_DAMAGED", damaged.append)
    definition = make_def()
    near, far = Player((40, 0)), Player((1000, 1000))
    boom(player=near, definition=definition, bus=bus)
    expected = round(blast_damage(definition, 40 - settings.PLAYER_SIZE / 2) * 0.5)
    assert near.stats.health == 100 - expected and damaged == [{"amount": expected}]
    boom(player=far, definition=definition)
    assert far.stats.health == 100


def test_throwing_is_reported_and_blasts_fade():
    bus, thrown = EventBus(), []
    bus.on("GRENADE_THROWN", thrown.append)
    system = GrenadeSystem(bus)
    system.throw(make_def(), ORIGIN, Vector2(100, 0))
    assert len(system.grenades) == 1 and thrown[0]["target"] == (100, 0)
    system.update(2.0, [], Player((1000, 1000)), [])
    assert system.grenades == [] and len(system.blasts) == 1
    system.update(1.0, [], Player((1000, 1000)), [])
    assert system.blasts == []


def test_shipped_grenade_data_is_valid():
    items = load_item_defs()
    grenade = load_grenade_defs(items)["grenade"]
    assert grenade.fuse > 0 and grenade.radius > 0 and items["grenade"].type == "throwable"


def test_grenade_data_rejects_unknown_items():
    with pytest.raises(DataLoadError, match="ghost"):
        GrenadeDef.from_dict(raw_grenade(id="ghost"), load_item_defs(), "test")


def test_grenade_data_rejects_items_that_are_not_throwable():
    with pytest.raises(DataLoadError, match="throwable"):
        GrenadeDef.from_dict(raw_grenade(id="scrap"), load_item_defs(), "test")


def test_grenade_data_rejects_bad_numbers():
    with pytest.raises(DataLoadError, match="radius"):
        GrenadeDef.from_dict(raw_grenade(radius=0), load_item_defs(), "test")


def test_throwables_cannot_be_used_or_quick_healed():
    items = load_item_defs()
    inventory = Inventory(10, items)
    inventory.add("grenade", 2)
    player = Player((1000, 1000), inventory=inventory)
    player.stats.health = 50
    assert player.use_item("grenade") is False
    assert player.quick_heal() is None
    assert inventory.count("grenade") == 2


def test_grenades_can_be_crafted_and_the_player_starts_with_some():
    data = load_crafting_data(load_item_defs())
    assert any(recipe.output_item == "grenade" for recipe in data.recipes.values())
    assert settings.PLAYER_START_ITEMS.get("grenade", 0) >= 1