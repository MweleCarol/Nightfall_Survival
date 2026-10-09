"""Boss arenas: a region with barriers that close when the fight starts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import pygame

from src.core import settings
from src.services.data_loader import DataLoadError, load_json, require_field
from src.world.camera import Camera


class ArenaState(Enum):
    WAITING = "WAITING"      # the boss has not been fought yet
    ACTIVE = "ACTIVE"        # the fight is on and the gates are closed
    CLEARED = "CLEARED"      # the boss is dead


def _rect(value: Any, where: str) -> pygame.Rect:
    valid = (isinstance(value, (list, tuple)) and len(value) == 4
             and all(isinstance(v, int) and not isinstance(v, bool) for v in value))
    if not valid:
        raise DataLoadError(f"{where}: expected a rect [x, y, width, height] of integers")
    return pygame.Rect(*value)


@dataclass(frozen=True)
class ArenaDef:
    id: str
    name: str
    boss_id: str
    mission: str | None                 # the fight only starts while this mission is ACTIVE
    rect: pygame.Rect
    boss_spawn: tuple[int, int]
    barriers: tuple[pygame.Rect, ...]


def parse_arenas(data: dict, boss_ids: set[str], where: str) -> dict[str, ArenaDef]:
    arenas: dict[str, ArenaDef] = {}
    for index, raw in enumerate(require_field(data, "arenas", list, where)):
        arena_where = f"{where}: arenas[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{arena_where}: must be an object")
        arena_id = require_field(raw, "id", str, arena_where)
        if arena_id in arenas:
            raise DataLoadError(f"{arena_where}: duplicate id '{arena_id}'")
        boss_id = require_field(raw, "boss", str, arena_where)
        if boss_id not in boss_ids:
            raise DataLoadError(f"{arena_where}: unknown boss '{boss_id}'")
        mission = raw.get("mission")
        if mission is not None and not isinstance(mission, str):
            raise DataLoadError(f"{arena_where}: field 'mission' must be str")
        spawn = raw.get("boss_spawn")
        if not (isinstance(spawn, (list, tuple)) and len(spawn) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in spawn)):
            raise DataLoadError(f"{arena_where}: field 'boss_spawn' must be [x, y] integers")
        barriers = tuple(_rect(b, f"{arena_where}.barriers[{i}]")
                         for i, b in enumerate(require_field(raw, "barriers", list, arena_where)))
        arenas[arena_id] = ArenaDef(
            id=arena_id, name=require_field(raw, "name", str, arena_where), boss_id=boss_id,
            mission=mission, rect=_rect(raw.get("rect"), f"{arena_where}.rect"),
            boss_spawn=(spawn[0], spawn[1]), barriers=barriers)
    return arenas


def load_arenas(boss_ids: set[str], path: str = settings.ARENAS_FILE) -> dict[str, ArenaDef]:
    return parse_arenas(load_json(path), boss_ids, path)


class Arena:
    """An arena in the world, with its runtime state."""

    def __init__(self, definition: ArenaDef) -> None:
        self.definition = definition
        self.state = ArenaState.WAITING
        self.warned = False          # the "gates will close" banner was shown
        self.hinted = False          # the "come back at dawn" banner was shown

    @property
    def barriers(self) -> list[pygame.Rect]:
        """The gates. They only exist while the fight is on."""
        return list(self.definition.barriers) if self.state is ArenaState.ACTIVE else []

    def is_near(self, player_rect: pygame.Rect) -> bool:
        margin = settings.ARENA_WARNING_MARGIN
        return self.definition.rect.inflate(2 * margin, 2 * margin).colliderect(player_rect)

    def can_trigger(self, player_rect: pygame.Rect, mission_active: bool, is_day: bool) -> bool:
        """The fight starts when the player is fully inside, in daylight, with the mission active."""
        return (self.state is ArenaState.WAITING and mission_active and is_day
                and self.definition.rect.contains(player_rect))

    def start(self) -> None:
        self.state = ArenaState.ACTIVE

    def clear(self) -> None:
        self.state = ArenaState.CLEARED

    def draw(self, surface: pygame.Surface, camera: Camera, show_hint: bool) -> None:
        if self.state is ArenaState.ACTIVE:
            for barrier in self.definition.barriers:
                screen_rect = camera.apply(barrier)
                pygame.draw.rect(surface, (110, 28, 28), screen_rect)
                pygame.draw.rect(surface, (230, 80, 60), screen_rect, 2)
        elif self.state is ArenaState.WAITING and show_hint:
            pygame.draw.rect(surface, (150, 40, 40), camera.apply(self.definition.rect), 2)