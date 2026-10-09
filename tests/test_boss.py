import random

import pygame
import pytest
from pygame import Vector2

from src.combat.combat_system import CombatSystem
from src.core.event_bus import EventBus
from src.enemies.boss import (
    Boss, BossDef, BossMode, BossRewards, ChargeDef, CleaveDef, PhaseDef, SlamDef, load_boss_defs,
)
from src.player.inventory import load_item_defs
from src.services.data_loader import DataLoadError
from tests.factories import make_weapon


def make_def(**overrides) -> BossDef:
    values = dict(
        id="boss", name="Boss", max_health=100, speed=100.0, radius=30, intro_time=1.0,
        transition_time=0.5, vulnerable_multiplier=2.0,
        rewards=BossRewards(xp=100, skill_points=1, items={}),
        cleave=CleaveDef(damage=20, windup=0.5, cooldown=2.0, radius=50.0, reach=60.0, trigger_range=100.0),
        charge=ChargeDef(damage=30, windup=0.5, cooldown=5.0, speed=500.0, max_duration=1.0,
                         min_distance=200.0, recover=1.0, wall_recover=2.0),
        slam=SlamDef(damage=25, windup=0.5, cooldown=6.0, radius=150.0, trigger_range=180.0, recover=1.0),
        phases=(PhaseDef("One", 1.0, 1.0, (150, 60, 60), ("cleave",)),
                PhaseDef("Two", 0.6, 1.5, (190, 90, 40), ("cleave", "charge")),
                PhaseDef("Three", 0.3, 2.0, (220, 40, 40), ("cleave", "charge", "slam"))),
    )
    values.update(overrides)
    return BossDef(**values)


def make_boss(position=(500, 500), **overrides) -> Boss:
    return Boss(make_def(**overrides), position, rng=random.Random(1))


def ready(boss: Boss, phase: int = 0) -> Boss:
    """Skip the introduction and set the phase."""
    boss.mode = BossMode.CHASE
    boss.mode_timer = 0.0
    boss.phase_index = phase
    return boss


def raw_boss(**overrides) -> dict:
    data = {
        "id": "boss", "name": "Boss", "max_health": 100, "speed": 100, "radius": 30,
        "intro_time": 1.0, "transition_time": 0.5, "vulnerable_multiplier": 2.0,
        "rewards": {"xp": 100, "skill_points": 1, "items": {"scrap": 5}},
        "attacks": {
            "cleave": {"damage": 20, "windup": 0.5, "cooldown": 2.0, "radius": 50, "reach": 60,
                       "trigger_range": 100},
            "charge": {"damage": 30, "windup": 0.5, "cooldown": 5.0, "speed": 500, "max_duration": 1.0,
                       "min_distance": 200, "recover": 1.0, "wall_recover": 2.0},
            "slam": {"damage": 25, "windup": 0.5, "cooldown": 6.0, "radius": 150, "trigger_range": 180,
                     "recover": 1.0},
        },
        "phases": [
            {"name": "One", "starts_at": 1.0, "speed_multiplier": 1.0, "color": [150, 60, 60],
             "attacks": ["cleave"]},
            {"name": "Two", "starts_at": 0.5, "speed_multiplier": 1.5, "color": [190, 90, 40],
             "attacks": ["cleave", "charge"]},
        ],
    }
    data.update(overrides)
    return data


def test_boss_is_invulnerable_and_passive_during_the_intro():
    boss, target = make_boss(), Vector2(570, 500)
    assert boss.mode is BossMode.INTRO
    assert boss.take_damage(50) is False and boss.health == 100
    assert boss.update(0.4, target, True, []) == 0
    assert boss.update(0.4, target, True, []) == 0
    assert boss.mode is BossMode.INTRO
    boss.update(0.3, target, True, [])
    assert boss.mode is BossMode.CHASE


def test_boss_walks_toward_the_player():
    boss = ready(make_boss())
    boss.update(0.5, Vector2(900, 500), True, [])
    assert boss.position.x == pytest.approx(550)


def test_cleave_hits_a_player_in_front():
    boss, target = ready(make_boss()), Vector2(570, 500)
    boss.update(0.1, target, True, [])                    # picks the cleave and starts the wind-up
    assert boss.mode is BossMode.TELEGRAPH and boss.current_attack == "cleave"
    assert boss.update(0.3, target, True, []) == 0        # still winding up
    assert boss.update(0.3, target, True, []) == 20       # the swing lands


def test_cleave_can_be_dodged():
    boss, target = ready(make_boss()), Vector2(570, 500)
    boss.update(0.1, target, True, [])
    assert boss.update(0.6, Vector2(400, 500), True, []) == 0


def test_phase_change_triggers_a_transition():
    boss = ready(make_boss())
    assert boss.take_damage(50) is False                  # 50% health: phase two begins at 60%
    assert boss.phase_index == 1 and boss.mode is BossMode.TRANSITION
    events = boss.pop_events()
    assert events[-1][0] == "BOSS_PHASE_CHANGED" and events[-1][1]["phase"] == 2
    assert boss.take_damage(10) is False and boss.health == 50     # invulnerable while roaring
    boss.update(0.6, Vector2(900, 500), True, [])
    assert boss.mode is BossMode.CHASE


def test_one_huge_hit_skips_straight_to_the_last_phase():
    boss = ready(make_boss())
    boss.take_damage(80)
    phase_events = [e for e in boss.pop_events() if e[0] == "BOSS_PHASE_CHANGED"]
    assert boss.phase_index == 2
    assert len(phase_events) == 1 and phase_events[0][1]["phase"] == 3


def test_killing_the_boss():
    boss = ready(make_boss())
    assert boss.take_damage(100) is True
    assert boss.is_dead
    assert [e[0] for e in boss.pop_events()] == ["BOSS_DEFEATED"]
    assert boss.take_damage(10) is False


def test_charge_hits_once_then_leaves_the_boss_exposed():
    boss, target = ready(make_boss(), phase=1), Vector2(800, 500)
    boss.update(0.1, target, True, [])
    assert boss.mode is BossMode.TELEGRAPH and boss.current_attack == "charge"
    boss.update(0.5, target, True, [])                    # the wind-up ends: the charge begins
    assert boss.mode is BossMode.CHARGE
    damage = [boss.update(0.1, target, True, []) for _ in range(15)]
    assert sum(damage) == 30 and damage.count(30) == 1
    assert boss.mode is BossMode.RECOVER and boss.vulnerable


def test_exposed_boss_takes_extra_damage():
    boss = ready(make_boss())
    boss.vulnerable = True
    boss.take_damage(10)
    assert boss.health == 80                              # 10 damage x 2.0


def test_charging_into_a_wall_stuns_the_boss():
    wall = pygame.Rect(650, 400, 20, 200)
    boss, target = ready(make_boss(), phase=1), Vector2(900, 500)
    for _ in range(30):
        boss.update(0.1, target, True, [wall])
        if boss.mode is BossMode.RECOVER:
            break
    assert boss.mode is BossMode.RECOVER and boss.vulnerable
    assert boss.rect.right <= wall.left
    assert boss.mode_timer == pytest.approx(2.0)
    assert "BOSS_STUNNED" in [e[0] for e in boss.pop_events()]


def test_slam_hits_nearby_players():
    boss = ready(make_boss(), phase=2)
    boss.cooldowns.update({"cleave": 99.0, "charge": 99.0})
    target = Vector2(600, 500)
    boss.update(0.1, target, True, [])
    assert boss.current_attack == "slam"
    assert boss.update(0.6, target, True, []) == 25
    assert boss.mode is BossMode.RECOVER and boss.vulnerable


def test_slam_can_be_escaped():
    boss = ready(make_boss(), phase=2)
    boss.cooldowns.update({"cleave": 99.0, "charge": 99.0})
    boss.update(0.1, Vector2(600, 500), True, [])
    assert boss.update(0.6, Vector2(800, 500), True, []) == 0


def test_phase_one_never_charges():
    boss, target = ready(make_boss()), Vector2(900, 500)
    for _ in range(20):
        boss.update(0.1, target, True, [])
        assert boss.mode is BossMode.CHASE and boss.current_attack is None


def test_attacks_respect_their_cooldown():
    boss, target = ready(make_boss()), Vector2(570, 500)
    hits = [step for step in range(70) if boss.update(0.1, target, True, []) > 0]
    assert len(hits) >= 2
    assert all(later - earlier >= 20 for earlier, later in zip(hits, hits[1:]))   # 2.0 s apart


def test_boss_ignores_an_invalid_target():
    boss = ready(make_boss())
    assert boss.update(1.0, Vector2(900, 500), False, []) == 0
    assert boss.position == Vector2(500, 500)


def test_shipped_boss_data_is_valid():
    boss = load_boss_defs(load_item_defs())["the_butcher"]
    starts = [phase.starts_at for phase in boss.phases]
    assert starts[0] == 1.0 and starts == sorted(starts, reverse=True)
    assert boss.rewards.xp > 0 and boss.max_health > 0


def test_first_phase_must_start_at_full_health():
    phases = raw_boss()["phases"]
    phases[0]["starts_at"] = 0.9
    with pytest.raises(DataLoadError, match="starts_at"):
        BossDef.from_dict(raw_boss(phases=phases), load_item_defs(), "test")


def test_unknown_attack_in_a_phase_is_rejected():
    phases = raw_boss()["phases"]
    phases[1]["attacks"] = ["bite"]
    with pytest.raises(DataLoadError, match="bite"):
        BossDef.from_dict(raw_boss(phases=phases), load_item_defs(), "test")


def test_phases_must_descend():
    phases = raw_boss()["phases"]
    phases.append({"name": "Three", "starts_at": 0.5, "speed_multiplier": 2.0,
                   "color": [220, 40, 40], "attacks": ["cleave"]})
    with pytest.raises(DataLoadError, match="descending"):
        BossDef.from_dict(raw_boss(phases=phases), load_item_defs(), "test")


def test_unknown_reward_item_is_rejected():
    raw = raw_boss(rewards={"xp": 1, "items": {"ghost": 1}})
    with pytest.raises(DataLoadError, match="ghost"):
        BossDef.from_dict(raw, load_item_defs(), "test")


def test_boss_becomes_a_normal_enemy_definition():
    definition = make_def().to_enemy_def()
    assert definition.id == "boss" and definition.type == "boss"
    assert definition.xp_reward == 100 and definition.max_health == 100


def test_boss_works_with_the_combat_system():
    bus, died = EventBus(), []
    bus.on("ENEMY_DIED", died.append)
    boss = ready(make_boss((200, 0), max_health=10))
    weapon = make_weapon(damage=25, spread=0)
    CombatSystem(event_bus=bus, rng=random.Random(1)).fire_weapon(
        Vector2(0, 0), Vector2(1, 0), weapon, [boss], [])
    assert boss.is_dead and len(died) == 1 and died[0]["enemy_id"] == "boss"