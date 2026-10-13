"""Ties the in-game visual effects together. It listens to game events itself."""
from __future__ import annotations

import random

import pygame
from pygame import Vector2

from src.core.event_bus import EventBus
from src.ui.screen_effects import HurtFlash, Vignette, low_health_intensity
from src.world.camera import Camera
from src.world.particles import ParticleSystem
from src.world.shake import ScreenShake
from src.world.weather import WeatherSystem

FLASH_COLOR = (255, 235, 170)
IMPACT_COLOR = (255, 170, 70)
BLOOD_COLOR = (150, 20, 24)


class EffectsManager:
    def __init__(self, event_bus: EventBus, width: int, height: int,
                 rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self.particles = ParticleSystem(self.rng)
        self.shake = ScreenShake(rng=self.rng)
        self.hurt = HurtFlash()
        self.weather = WeatherSystem(width, height, self.rng)
        self.vignette = Vignette(width, height)

        self.player_position = Vector2(0, 0)
        self.darkness = 0.0
        self.health_fraction = 1.0
        self.time = 0.0
        self._saved_offset: Vector2 | None = None

        self._event_bus = event_bus
        self._handlers = [
            ("SHOT_FIRED", self._on_shot_fired),
            ("SHOT_IMPACT", self._on_shot_impact),
            ("ENEMY_HIT", self._on_enemy_hit),
            ("ENEMY_DIED", self._on_enemy_died),
            ("PLAYER_DAMAGED", self._on_player_damaged),
            ("BOSS_PHASE_CHANGED", self._on_boss_phase_changed),
            ("BOSS_STUNNED", self._on_boss_stunned),
            ("BOSS_DEFEATED", self._on_boss_defeated),
        ]
        for name, handler in self._handlers:
            event_bus.on(name, handler)

    def close(self) -> None:
        """Stop listening (called when the game state is left)."""
        for name, handler in self._handlers:
            self._event_bus.off(name, handler)

    # ---- reactions to game events ----
    def _on_shot_fired(self, data: dict) -> None:
        self.particles.burst(Vector2(data["origin"]), Vector2(data["direction"]), 5,
                             speed=(120, 320), spread=28, life=(0.08, 0.18), size=(2, 3),
                             color=FLASH_COLOR, drag=6.0)
        self.shake.add_trauma(0.10)                      # a little recoil

    def _on_shot_impact(self, data: dict) -> None:
        bounce = -Vector2(data["direction"])             # sparks fly back towards the shooter
        self.particles.burst(Vector2(data["position"]), bounce, 6, speed=(80, 260), spread=55,
                             life=(0.15, 0.4), size=(1, 3), color=IMPACT_COLOR, drag=4.0)

    def _on_enemy_hit(self, data: dict) -> None:
        count = 10 if data.get("critical") else 6
        self.particles.burst(Vector2(data["position"]), Vector2(data["direction"]), count,
                             speed=(60, 240), spread=35, life=(0.3, 0.7), size=(2, 4),
                             color=BLOOD_COLOR, drag=3.5)

    def _on_enemy_died(self, data: dict) -> None:
        self.particles.burst(Vector2(data["position"]), Vector2(0, 0), 18, speed=(40, 220),
                             life=(0.4, 0.9), size=(2, 5), color=BLOOD_COLOR, drag=3.0)
        self.shake.add_trauma(0.12)

    def _on_player_damaged(self, data: dict) -> None:
        amount = data.get("amount", 10)
        self.hurt.trigger(min(1.0, 0.35 + amount / 60))
        self.shake.add_trauma(0.25 + min(0.3, amount / 100))
        self.particles.burst(self.player_position, Vector2(0, 0), 8, speed=(50, 180),
                             life=(0.3, 0.6), size=(2, 4), color=BLOOD_COLOR, drag=3.0)

    def _on_boss_phase_changed(self, data: dict) -> None:
        self.shake.add_trauma(0.7)

    def _on_boss_stunned(self, data: dict) -> None:
        self.shake.add_trauma(0.45)

    def _on_boss_defeated(self, data: dict) -> None:
        self.shake.add_trauma(0.9)

    # ---- per-frame update and drawing ----
    def update(self, dt: float, player_position: Vector2, darkness: float,
               health_fraction: float) -> None:
        self.time += dt
        self.player_position = Vector2(player_position)
        self.darkness = darkness
        self.health_fraction = health_fraction
        self.particles.update(dt)
        self.shake.update(dt)
        self.hurt.update(dt)
        self.weather.update(dt, darkness)

    def begin_world(self, camera: Camera) -> None:
        """Shake the camera for the world drawing. Always pair with end_world()."""
        self._saved_offset = Vector2(camera.offset)
        camera.offset += self.shake.offset

    def draw_world(self, surface: pygame.Surface, camera: Camera) -> None:
        self.particles.draw(surface, camera)

    def draw_weather(self, surface: pygame.Surface) -> None:
        self.weather.draw_fog(surface)
        self.weather.draw_rain(surface)
        self.weather.draw_lightning(surface)

    def end_world(self, camera: Camera) -> None:
        if self._saved_offset is not None:
            camera.offset = self._saved_offset
            self._saved_offset = None

    def draw_overlay(self, surface: pygame.Surface) -> None:
        """Vignette and damage flash. Drawn before the HUD so the HUD stays clear."""
        low = low_health_intensity(self.health_fraction, self.time)
        self.vignette.draw(surface, self.darkness, self.hurt.intensity, low)