import random

import pygame
from pygame import Vector2

from src.core.event_bus import EventBus
from src.world.camera import Camera
from src.world.effects_manager import EffectsManager


def make():
    bus = EventBus()
    return bus, EffectsManager(bus, 320, 180, rng=random.Random(1))


def test_a_shot_throws_muzzle_sparks_and_a_little_shake():
    bus, effects = make()
    bus.emit("SHOT_FIRED", {"weapon": "x", "origin": (100, 100), "direction": (1, 0)})
    assert len(effects.particles.particles) > 0 and effects.shake.trauma > 0


def test_wall_impacts_throw_sparks_back_at_the_shooter():
    bus, effects = make()
    bus.emit("SHOT_IMPACT", {"position": (300, 100), "direction": (1, 0)})
    particles = effects.particles.particles
    assert particles and sum(p.vx for p in particles) < 0


def test_critical_hits_make_more_blood():
    bus, effects = make()
    bus.emit("ENEMY_HIT", {"position": (50, 50), "direction": (1, 0), "critical": False})
    normal = len(effects.particles.particles)
    bus2, effects2 = make()
    bus2.emit("ENEMY_HIT", {"position": (50, 50), "direction": (1, 0), "critical": True})
    assert len(effects2.particles.particles) > normal


def test_taking_damage_flashes_shakes_and_bleeds_at_the_player():
    bus, effects = make()
    effects.update(0.0, Vector2(50, 60), 0.0, 1.0)
    bus.emit("PLAYER_DAMAGED", {"amount": 20})
    assert effects.hurt.intensity > 0 and effects.shake.trauma > 0
    assert effects.particles.particles
    assert all(p.x == 50 and p.y == 60 for p in effects.particles.particles)


def test_closing_the_manager_stops_it_listening():
    bus, effects = make()
    effects.close()
    bus.emit("SHOT_FIRED", {"weapon": "x", "origin": (0, 0), "direction": (1, 0)})
    assert effects.particles.particles == []


def test_the_camera_is_shaken_only_between_begin_and_end():
    bus, effects = make()
    camera = Camera(1280, 720, 3200, 2400)
    camera.offset = Vector2(100, 200)
    effects.shake.add_trauma(1.0)
    effects.update(0.1, Vector2(0, 0), 0.0, 1.0)
    effects.begin_world(camera)
    assert camera.offset != Vector2(100, 200)
    effects.end_world(camera)
    assert camera.offset == Vector2(100, 200)
    effects.draw_world(pygame.Surface((320, 180)), camera)
    effects.draw_weather(pygame.Surface((320, 180)))
    effects.draw_overlay(pygame.Surface((320, 180)))