"""Named locations and story objects placed in the world (loaded from the map JSON)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pygame
from pygame import Vector2

from src.core import settings
from src.player.inventory import ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field
from src.world.camera import Camera

OBJECT_KINDS = ("note", "device", "item")


def _ints(value: Any, length: int, where: str, what: str) -> tuple[int, ...]:
    valid = (isinstance(value, (list, tuple)) and len(value) == length
             and all(isinstance(v, int) and not isinstance(v, bool) for v in value))
    if not valid:
        raise DataLoadError(f"{where}: expected {what}")
    return tuple(value)


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    rect: pygame.Rect


@dataclass(frozen=True)
class StoryObjectDef:
    id: str
    kind: str                       # note | device | item
    name: str
    pos: tuple[int, int]
    prompt: str
    mission: str | None = None      # only exists while this mission is ACTIVE
    after: str | None = None        # only appears once this other object has been used
    give_item: str | None = None    # for kind "item"
    quantity: int = 1
    message: str = ""               # shown when a "device" is used


class StoryObject:
    """A story object in the world, with its runtime state (used or not)."""

    def __init__(self, definition: StoryObjectDef) -> None:
        self.definition = definition
        self.position = Vector2(definition.pos)
        self.used = False

    @property
    def id(self) -> str:
        return self.definition.id

    def draw(self, surface: pygame.Surface, camera: Camera,
             font: pygame.font.Font, show_label: bool) -> None:
        center = camera.world_to_screen(self.position)
        kind = self.definition.kind
        if kind == "note":
            page = pygame.Rect(0, 0, 16, 20)
            page.center = center
            pygame.draw.rect(surface, (90, 90, 96) if self.used else (232, 226, 200), page)
            for line in range(3):
                y = page.y + 5 + line * 5
                pygame.draw.line(surface, (40, 44, 56), (page.x + 3, y), (page.right - 3, y))
        elif kind == "device":
            box = pygame.Rect(0, 0, 22, 22)
            box.center = center
            pygame.draw.rect(surface, (40, 70, 90), box)
            pygame.draw.rect(surface, (80, 200, 255), box, 2)
        else:
            r = 10
            points = [(center.x, center.y - r), (center.x + r, center.y),
                      (center.x, center.y + r), (center.x - r, center.y)]
            pygame.draw.polygon(surface, settings.COLOR_AMBER, points)
            pygame.draw.polygon(surface, (15, 18, 26), points, 2)
        if show_label and not self.used:
            text = font.render(self.definition.name, True, settings.COLOR_TEXT)
            surface.blit(text, text.get_rect(midbottom=(center.x, center.y - 18)))


@dataclass
class StoryWorld:
    locations: list[Location]
    objects: list[StoryObject]

    def object_by_id(self, object_id: str) -> StoryObject | None:
        return next((o for o in self.objects if o.id == object_id), None)


def parse_story_world(data: dict, item_defs: dict[str, ItemDef], where: str) -> StoryWorld:
    locations: list[Location] = []
    for index, raw in enumerate(data.get("locations", [])):
        loc_where = f"{where}: locations[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{loc_where}: must be an object")
        x, y, w, h = _ints(raw.get("rect"), 4, f"{loc_where}.rect", "[x, y, width, height] integers")
        locations.append(Location(require_field(raw, "id", str, loc_where),
                                  require_field(raw, "name", str, loc_where),
                                  pygame.Rect(x, y, w, h)))

    objects: list[StoryObject] = []
    seen: set[str] = set()
    for index, raw in enumerate(data.get("story_objects", [])):
        obj_where = f"{where}: story_objects[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{obj_where}: must be an object")
        kind = require_field(raw, "kind", str, obj_where)
        if kind not in OBJECT_KINDS:
            raise DataLoadError(f"{obj_where}: field 'kind' must be one of {OBJECT_KINDS}")
        object_id = require_field(raw, "id", str, obj_where)
        if object_id in seen:
            raise DataLoadError(f"{obj_where}: duplicate id '{object_id}'")
        seen.add(object_id)

        give_item = None
        quantity = 1
        if kind == "item":
            give_item = require_field(raw, "give_item", str, obj_where)
            if give_item not in item_defs:
                raise DataLoadError(f"{obj_where}: unknown item '{give_item}'")
            quantity = require_field(raw, "quantity", int, obj_where) if "quantity" in raw else 1
            if quantity < 1:
                raise DataLoadError(f"{obj_where}: field 'quantity' must be >= 1")
        for optional in ("mission", "after", "message"):
            if optional in raw and not isinstance(raw[optional], str):
                raise DataLoadError(f"{obj_where}: field '{optional}' must be str")

        px, py = _ints(raw.get("pos"), 2, f"{obj_where}.pos", "[x, y] integers")
        objects.append(StoryObject(StoryObjectDef(
            id=object_id, kind=kind, name=require_field(raw, "name", str, obj_where),
            pos=(px, py), prompt=require_field(raw, "prompt", str, obj_where),
            mission=raw.get("mission"), after=raw.get("after"),
            give_item=give_item, quantity=quantity, message=raw.get("message", ""))))
    return StoryWorld(locations, objects)


def load_story_world(item_defs: dict[str, ItemDef],
                     path: str = settings.DEFAULT_MAP) -> StoryWorld:
    return parse_story_world(load_json(path), item_defs, path)