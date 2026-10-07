"""City district map, loaded from a JSON file (data-driven)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame

from src.core import settings
from src.services.data_loader import DataLoadError, load_json
from src.world.camera import Camera

GRID_SIZE = 100

COLOR_GROUND = (18, 22, 34)
COLOR_GRID = (24, 30, 46)
COLOR_EDGE = (70, 88, 120)
COLOR_STREET_LIGHT = (210, 200, 150)
COLOR_DOOR = (70, 52, 20)

BUILDING_COLORS = {
    "office": (38, 50, 78), "store": (58, 52, 44), "hospital": (46, 72, 76),
    "house": (44, 48, 62), "apartments": (44, 52, 68), "warehouse": (50, 50, 56),
    "garage": (54, 46, 46), "safehouse": (52, 44, 30),
}
DEFAULT_BUILDING_COLOR = (40, 52, 76)
OBSTACLE_COLORS = {"vehicle": (62, 66, 84), "dumpster": (44, 70, 56)}
STATION_LABELS = {"workbench": "WORKBENCH", "weapon_station": "WEAPON STATION"}


@dataclass
class Building:
    id: str
    type: str
    name: str
    rect: pygame.Rect


@dataclass
class Obstacle:
    type: str
    rect: pygame.Rect


@dataclass
class Interactable:
    id: str
    rect: pygame.Rect
    prompt: str
    kind: str


@dataclass
class LootPoint:
    id: str
    pos: tuple[int, int]
    category: str


@dataclass
class SpawnZone:
    id: str
    rect: pygame.Rect


# ---------- validation helpers: errors name the file and the field ----------
def _get(data: dict, key: str, expected: type, where: str) -> Any:
    if key not in data:
        raise DataLoadError(f"{where}: missing field '{key}'")
    value = data[key]
    if not isinstance(value, expected):
        raise DataLoadError(f"{where}: field '{key}' must be {expected.__name__}")
    return value


def _dicts(data: dict, key: str, where: str) -> list[dict]:
    items = _get(data, key, list, where)
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise DataLoadError(f"{where}: {key}[{i}] must be an object")
    return items


def _rect(value: Any, where: str) -> pygame.Rect:
    if not (isinstance(value, (list, tuple)) and len(value) == 4
            and all(isinstance(v, int) for v in value)):
        raise DataLoadError(f"{where}: expected [x, y, width, height] integers")
    return pygame.Rect(*value)


def _point(value: Any, where: str) -> tuple[int, int]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, int) for v in value)):
        raise DataLoadError(f"{where}: expected [x, y] integers")
    return (value[0], value[1])


class GameMap:
    def __init__(self, data: dict[str, Any], source: str = "<map>") -> None:
        self.id: str = _get(data, "id", str, source)
        self.name: str = _get(data, "name", str, source)
        self.width: int = _get(data, "width", int, source)
        self.height: int = _get(data, "height", int, source)
        if (self.width, self.height) != (settings.WORLD_WIDTH, settings.WORLD_HEIGHT):
            raise DataLoadError(
                f"{source}: map size {self.width}x{self.height} must match "
                f"settings WORLD_WIDTH/WORLD_HEIGHT"
            )
        self.player_spawn = _point(data.get("player_spawn"), f"{source}: player_spawn")

        self.buildings: list[Building] = []
        for i, b in enumerate(_dicts(data, "buildings", source)):
            where = f"{source}: buildings[{i}]"
            self.buildings.append(Building(
                _get(b, "id", str, where), _get(b, "type", str, where),
                _get(b, "name", str, where), _rect(b.get("rect"), f"{where}.rect")))

        self.obstacles: list[Obstacle] = []
        for i, o in enumerate(_dicts(data, "obstacles", source)):
            where = f"{source}: obstacles[{i}]"
            self.obstacles.append(Obstacle(
                _get(o, "type", str, where), _rect(o.get("rect"), f"{where}.rect")))

        self.street_lights: list[tuple[int, int]] = [
            _point(p, f"{source}: street_lights[{i}]")
            for i, p in enumerate(_get(data, "street_lights", list, source))]

        self.loot_points: list[LootPoint] = []
        for i, lp in enumerate(_dicts(data, "loot_points", source)):
            where = f"{source}: loot_points[{i}]"
            self.loot_points.append(LootPoint(
                _get(lp, "id", str, where), _point(lp.get("pos"), f"{where}.pos"),
                _get(lp, "category", str, where)))

        self.spawn_zones: list[SpawnZone] = []
        for i, z in enumerate(_dicts(data, "spawn_zones", source)):
            where = f"{source}: spawn_zones[{i}]"
            self.spawn_zones.append(SpawnZone(
                _get(z, "id", str, where), _rect(z.get("rect"), f"{where}.rect")))

        # Safehouse: a building + a door interaction zone + a protected area.
        sh = _get(data, "safehouse", dict, source)
        building_id = _get(sh, "building_id", str, f"{source}: safehouse")
        found = [b for b in self.buildings if b.id == building_id]
        if not found:
            raise DataLoadError(f"{source}: safehouse building '{building_id}' not found")
        self.safehouse: Building = found[0]
        margin = _get(sh, "safe_margin", int, f"{source}: safehouse")
        self.safe_zone = self.safehouse.rect.inflate(2 * margin, 2 * margin)
        door = _rect(sh.get("door_zone"), f"{source}: safehouse.door_zone")
        self.interactables: list[Interactable] = [
            Interactable("safehouse_rest", door, "Press E to prepare for nightfall", "rest")
        ]

        # Optional crafting / upgrade stations placed around the safehouse.
        stations = data.get("stations", [])
        if not isinstance(stations, list):
            raise DataLoadError(f"{source}: field 'stations' must be list")
        for i, station in enumerate(stations):
            where = f"{source}: stations[{i}]"
            if not isinstance(station, dict):
                raise DataLoadError(f"{where}: must be an object")
            self.interactables.append(Interactable(
                _get(station, "id", str, where),
                _rect(station.get("rect"), f"{where}.rect"),
                _get(station, "prompt", str, where),
                _get(station, "kind", str, where)))

        self.walls: list[pygame.Rect] = (
            [b.rect for b in self.buildings] + [o.rect for o in self.obstacles])

        self._font: pygame.font.Font | None = None
        self._station_font: pygame.font.Font | None = None
        self._labels: dict[str, pygame.Surface] = {}

    @classmethod
    def load(cls, relative_path: str) -> GameMap:
        return cls(load_json(relative_path), source=relative_path)

    # ---- queries ----
    def interactable_at(self, rect: pygame.Rect) -> Interactable | None:
        for item in self.interactables:
            if rect.colliderect(item.rect):
                return item
        return None

    def in_safe_zone(self, rect: pygame.Rect) -> bool:
        return self.safe_zone.contains(rect)

    # ---- drawing ----
    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        surface.fill(COLOR_GROUND)
        view = camera.view_rect()
        self._draw_grid(surface, camera, view)

        for item in self.interactables:               # the doormat and the stations
            if item.rect.colliderect(view):
                r = camera.apply(item.rect)
                pygame.draw.rect(surface, COLOR_DOOR, r)
                pygame.draw.rect(surface, settings.COLOR_AMBER, r, 2)
                if item.kind != "rest":
                    label = self._station_label(item)
                    surface.blit(label, label.get_rect(center=r.center))

        for building in self.buildings:               # culling: on-screen only
            if building.rect.colliderect(view):
                self._draw_building(surface, camera, building)

        for obstacle in self.obstacles:
            if obstacle.rect.colliderect(view):
                r = camera.apply(obstacle.rect)
                pygame.draw.rect(surface, OBSTACLE_COLORS.get(obstacle.type, COLOR_EDGE), r)
                pygame.draw.rect(surface, COLOR_EDGE, r, 1)

        near = view.inflate(40, 40)
        for pos in self.street_lights:
            if near.collidepoint(pos):
                p = camera.world_to_screen(pygame.Vector2(pos))
                pygame.draw.circle(surface, COLOR_STREET_LIGHT, p, 5)
                pygame.draw.circle(surface, COLOR_EDGE, p, 9, 1)

    def draw_debug(self, surface: pygame.Surface, camera: Camera) -> None:
        """F3 overlay: shows invisible gameplay data."""
        pygame.draw.rect(surface, settings.COLOR_SAFE, camera.apply(self.safe_zone), 2)
        for item in self.interactables:
            pygame.draw.rect(surface, (80, 200, 255), camera.apply(item.rect), 2)
        for zone in self.spawn_zones:
            pygame.draw.rect(surface, settings.COLOR_ACCENT, camera.apply(zone.rect), 2)
        for loot in self.loot_points:
            p = camera.world_to_screen(pygame.Vector2(loot.pos))
            pygame.draw.circle(surface, (255, 220, 80), p, 7)

    def _draw_grid(self, surface: pygame.Surface, camera: Camera, view: pygame.Rect) -> None:
        for x in range(view.left - view.left % GRID_SIZE, view.right + GRID_SIZE, GRID_SIZE):
            sx = x - round(camera.offset.x)
            pygame.draw.line(surface, COLOR_GRID, (sx, 0), (sx, view.height))
        for y in range(view.top - view.top % GRID_SIZE, view.bottom + GRID_SIZE, GRID_SIZE):
            sy = y - round(camera.offset.y)
            pygame.draw.line(surface, COLOR_GRID, (0, sy), (view.width, sy))

    def _draw_building(self, surface: pygame.Surface, camera: Camera, b: Building) -> None:
        r = camera.apply(b.rect)
        pygame.draw.rect(surface, BUILDING_COLORS.get(b.type, DEFAULT_BUILDING_COLOR), r)
        is_safehouse = b.type == "safehouse"
        pygame.draw.rect(surface, settings.COLOR_AMBER if is_safehouse else COLOR_EDGE,
                         r, 3 if is_safehouse else 2)
        label = self._label(b)
        surface.blit(label, label.get_rect(center=r.center))

    def _label(self, b: Building) -> pygame.Surface:
        if b.id not in self._labels:               # render each label once, then reuse
            if self._font is None:
                self._font = pygame.font.SysFont("arial", 22, bold=True)
            color = settings.COLOR_AMBER if b.type == "safehouse" else settings.COLOR_MUTED
            self._labels[b.id] = self._font.render(b.name.upper(), True, color)
        return self._labels[b.id]

    def _station_label(self, item: Interactable) -> pygame.Surface:
        key = f"station:{item.id}"
        if key not in self._labels:
            if self._station_font is None:
                self._station_font = pygame.font.SysFont("arial", 16, bold=True)
            text = STATION_LABELS.get(item.kind, item.kind.upper())
            self._labels[key] = self._station_font.render(text, True, settings.COLOR_AMBER)
        return self._labels[key]