"""Where should the HUD point the player for a mission objective? Pure logic."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from pygame import Vector2


@dataclass
class MarkerSources:
    locations: dict[str, Vector2] = field(default_factory=dict)     # location id -> centre
    objects: dict[str, Vector2] = field(default_factory=dict)       # story object / station id -> position
    item_givers: dict[str, Vector2] = field(default_factory=dict)   # item id -> where to get it
    bosses: dict[str, Vector2] = field(default_factory=dict)        # boss id -> arena centre


def build_marker_sources(locations: Iterable, objects: Iterable, interactables: Iterable,
                         arenas: Iterable) -> MarkerSources:
    """Collect every place an objective can refer to. Takes the loaded world data."""
    sources = MarkerSources()
    for location in locations:
        sources.locations[location.id] = Vector2(location.rect.center)
    for interactable in interactables:
        sources.objects[interactable.id] = Vector2(interactable.rect.center)
    for obj in objects:
        sources.objects[obj.id] = Vector2(obj.position)
        if obj.definition.give_item:
            sources.item_givers[obj.definition.give_item] = Vector2(obj.position)
    for arena in arenas:
        sources.bosses[arena.boss_id] = Vector2(arena.rect.center)
    return sources


def objective_marker(objective, sources: MarkerSources) -> Vector2 | None:
    """The map position for one objective, or None when it has no particular place."""
    kind, target = objective.type, objective.target
    if kind == "reach_location":
        return sources.locations.get(target)
    if kind == "interact":
        return sources.objects.get(target)
    if kind == "collect_item":
        return sources.item_givers.get(target)
    if kind == "defeat_enemy":
        return sources.bosses.get(target)
    return None


def next_marker(mission, is_done: Callable[[int], bool], sources: MarkerSources) -> Vector2 | None:
    """The first unfinished objective that has a place on the map."""
    for index, objective in enumerate(mission.objectives):
        if is_done(index):
            continue
        position = objective_marker(objective, sources)
        if position is not None:
            return position
    return None