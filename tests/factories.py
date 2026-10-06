"""Test helpers: build weapons/enemies with sensible defaults."""
from __future__ import annotations

from src.combat.weapon import Weapon, WeaponDef
from src.enemies.enemy import Enemy, EnemyDef


def make_weapon_def(**overrides) -> WeaponDef:
    values = dict(
        id="test_gun", name="Test", damage=25, fire_rate=4.0, magazine_size=12,
        ammo_type="9mm", reload_time=1.5, range=500.0, spread=0.0,
        rarity="common", automatic=False,
    )
    values.update(overrides)
    return WeaponDef(**values)


def make_weapon(loaded: int | None = None, reserve: int = 30, **overrides) -> Weapon:
    return Weapon(make_weapon_def(**overrides), loaded=loaded, reserve=reserve)


def make_enemy_def(**overrides) -> EnemyDef:
    values = dict(
        id="test_walker", name="Test Walker", type="walker", max_health=60,
        speed=85.0, detection_range=350.0, attack_range=44.0, attack_damage=10,
        attack_cooldown=1.2, attack_windup=0.4, search_time=4.0, xp_reward=10,
        radius=16, color=(96, 140, 86),
    )
    values.update(overrides)
    return EnemyDef(**values)


def make_enemy(position=(0, 0), health_multiplier: float = 1.0,
               damage_multiplier: float = 1.0, **overrides) -> Enemy:
    return Enemy(make_enemy_def(**overrides), position, health_multiplier, damage_multiplier)