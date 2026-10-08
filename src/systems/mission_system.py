"""Missions and objectives (LLD section 15), driven entirely by events."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core import settings
from src.core.event_bus import EventBus
from src.player.inventory import ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field


class MissionStatus(Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Which event feeds each kind of objective.
OBJECTIVE_EVENTS = {
    "reach_location": "LOCATION_REACHED",
    "collect_item": "ITEM_COLLECTED",
    "defeat_enemy": "ENEMY_DIED",
    "survive_wave": "WAVE_COMPLETED",
    "survive_night": "NIGHT_COMPLETED",
    "interact": "OBJECT_INTERACTED",
    "search_containers": "CONTAINER_SEARCHED",
}
TARGETED_TYPES = ("reach_location", "collect_item", "interact")   # need a specific target
NUMBER_TYPES = ("survive_wave", "survive_night")                  # target is a number
CATEGORIES = ("story", "side")


@dataclass(frozen=True)
class ObjectiveDef:
    type: str
    target: str
    quantity: int
    description: str

    @classmethod
    def from_dict(cls, data: dict, where: str) -> ObjectiveDef:
        kind = require_field(data, "type", str, where)
        if kind not in OBJECTIVE_EVENTS:
            raise DataLoadError(f"{where}: field 'type' must be one of {tuple(OBJECTIVE_EVENTS)}")
        raw_target = data.get("target", "any")
        if isinstance(raw_target, bool) or not isinstance(raw_target, (str, int)):
            raise DataLoadError(f"{where}: field 'target' must be a string or a number")
        target = str(raw_target)
        if kind in TARGETED_TYPES and target == "any":
            raise DataLoadError(f"{where}: objective '{kind}' needs a specific 'target'")
        if kind in NUMBER_TYPES and (not target.isdigit() or int(target) < 1):
            raise DataLoadError(f"{where}: objective '{kind}' needs a 'target' number >= 1")
        quantity = require_field(data, "quantity", int, where) if "quantity" in data else 1
        if quantity < 1:
            raise DataLoadError(f"{where}: field 'quantity' must be >= 1")
        return cls(kind, target, quantity, require_field(data, "description", str, where))


def objective_progress(objective: ObjectiveDef, event: str, data: dict[str, Any]) -> int:
    """How much progress an event adds to an objective (0 if it doesn't match)."""
    if OBJECTIVE_EVENTS[objective.type] != event:
        return 0
    kind = objective.type
    if kind == "reach_location":
        return 1 if data.get("location") == objective.target else 0
    if kind == "collect_item":
        return int(data.get("quantity", 0)) if data.get("item") == objective.target else 0
    if kind == "defeat_enemy":
        return 1 if objective.target in ("any", data.get("enemy_id")) else 0
    if kind == "survive_wave":
        return 1 if data.get("wave", 0) >= int(objective.target) else 0
    if kind == "survive_night":
        return 1 if data.get("night", 0) >= int(objective.target) else 0
    if kind == "interact":
        return 1 if data.get("id") == objective.target else 0
    return 1                                   # search_containers


@dataclass(frozen=True)
class Rewards:
    xp: int = 0
    items: dict[str, int] = field(default_factory=dict)
    unlock_chapter: int | None = None

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> Rewards:
        xp = require_field(data, "xp", int, where) if "xp" in data else 0
        if xp < 0:
            raise DataLoadError(f"{where}: field 'xp' must be >= 0")
        raw_items = require_field(data, "items", dict, where) if "items" in data else {}
        items: dict[str, int] = {}
        for item_id, quantity in raw_items.items():
            if item_id not in item_defs:
                raise DataLoadError(f"{where}: unknown reward item '{item_id}'")
            if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
                raise DataLoadError(f"{where}: reward '{item_id}' must be an integer >= 1")
            items[item_id] = quantity
        chapter = require_field(data, "unlock_chapter", int, where) if "unlock_chapter" in data else None
        if chapter is not None and chapter < 1:
            raise DataLoadError(f"{where}: field 'unlock_chapter' must be >= 1")
        return cls(xp, items, chapter)


@dataclass(frozen=True)
class MissionDef:
    id: str
    title: str
    description: str
    category: str                       # "story" or "side"
    chapter: int                        # 0 for side missions
    objectives: tuple[ObjectiveDef, ...]
    rewards: Rewards
    requires: tuple[str, ...] = ()      # missions that must be completed first
    deadline_day: int | None = None     # the mission fails when this day has passed

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> MissionDef:
        category = require_field(data, "category", str, where)
        if category not in CATEGORIES:
            raise DataLoadError(f"{where}: field 'category' must be one of {CATEGORIES}")
        chapter = require_field(data, "chapter", int, where) if "chapter" in data else 0
        if chapter < 0:
            raise DataLoadError(f"{where}: field 'chapter' must be >= 0")
        requires = require_field(data, "requires", list, where) if "requires" in data else []
        if not all(isinstance(r, str) for r in requires):
            raise DataLoadError(f"{where}: field 'requires' must be a list of mission ids")
        deadline = require_field(data, "deadline_day", int, where) if "deadline_day" in data else None
        if deadline is not None and deadline < 1:
            raise DataLoadError(f"{where}: field 'deadline_day' must be >= 1")

        raw_objectives = require_field(data, "objectives", list, where)
        if not raw_objectives:
            raise DataLoadError(f"{where}: 'objectives' must not be empty")
        objectives: list[ObjectiveDef] = []
        for index, raw in enumerate(raw_objectives):
            objective_where = f"{where}.objectives[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{objective_where}: must be an object")
            objective = ObjectiveDef.from_dict(raw, objective_where)
            if objective.type == "collect_item" and objective.target not in item_defs:
                raise DataLoadError(
                    f"{objective_where}: collect_item target '{objective.target}' is not an item")
            objectives.append(objective)

        raw_rewards = require_field(data, "rewards", dict, where) if "rewards" in data else {}
        return cls(
            id=require_field(data, "id", str, where),
            title=require_field(data, "title", str, where),
            description=require_field(data, "description", str, where),
            category=category, chapter=chapter, objectives=tuple(objectives),
            rewards=Rewards.from_dict(raw_rewards, item_defs, f"{where}.rewards"),
            requires=tuple(requires), deadline_day=deadline,
        )


def parse_missions(data: dict, item_defs: dict[str, ItemDef], where: str) -> dict[str, MissionDef]:
    items = require_field(data, "missions", list, where)
    missions: dict[str, MissionDef] = {}
    for index, raw in enumerate(items):
        mission_where = f"{where}: missions[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{mission_where}: must be an object")
        mission = MissionDef.from_dict(raw, item_defs, mission_where)
        if mission.id in missions:
            raise DataLoadError(f"{mission_where}: duplicate id '{mission.id}'")
        missions[mission.id] = mission

    for mission in missions.values():
        for required in mission.requires:
            if required not in missions or required == mission.id:
                raise DataLoadError(
                    f"{where}: mission '{mission.id}' requires unknown mission '{required}'")

    # Every mission must be reachable: no circular requirements.
    reachable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for mission in missions.values():
            if mission.id not in reachable and all(r in reachable for r in mission.requires):
                reachable.add(mission.id)
                changed = True
    stuck = [mission_id for mission_id in missions if mission_id not in reachable]
    if stuck:
        raise DataLoadError(f"{where}: missions {stuck} can never become available (circular requirements)")
    return missions


def load_missions(item_defs: dict[str, ItemDef],
                  path: str = settings.MISSIONS_FILE) -> dict[str, MissionDef]:
    return parse_missions(load_json(path), item_defs, path)


def validate_references(missions: dict[str, MissionDef], location_ids: set[str],
                        object_ids: set[str], enemy_ids: set[str]) -> list[str]:
    """Check that objectives point at things that exist. Returns a list of problems."""
    problems: list[str] = []
    for mission in missions.values():
        for index, objective in enumerate(mission.objectives):
            where = f"mission '{mission.id}' objective {index + 1}"
            if objective.type == "reach_location" and objective.target not in location_ids:
                problems.append(f"{where}: unknown location '{objective.target}'")
            elif objective.type == "interact" and objective.target not in object_ids:
                problems.append(f"{where}: unknown object '{objective.target}'")
            elif (objective.type == "defeat_enemy" and objective.target != "any"
                  and objective.target not in enemy_ids):
                problems.append(f"{where}: unknown enemy '{objective.target}'")
    return problems


class MissionManager:
    """Tracks every mission's status and objective progress. No UI, no Pygame."""

    def __init__(self, missions: dict[str, MissionDef], event_bus: EventBus | None = None) -> None:
        self.missions = missions
        self.event_bus = event_bus
        self.status: dict[str, MissionStatus] = {mid: MissionStatus.LOCKED for mid in missions}
        self.progress: dict[str, list[int]] = {
            mid: [0] * len(m.objectives) for mid, m in missions.items()}
        self._refresh_availability()

    # ---- queries ----
    def active(self) -> list[MissionDef]:
        return [m for m in self.missions.values() if self.status[m.id] is MissionStatus.ACTIVE]

    def available(self) -> list[MissionDef]:
        return [m for m in self.missions.values() if self.status[m.id] is MissionStatus.AVAILABLE]

    def progress_of(self, mission_id: str, index: int) -> int:
        return self.progress[mission_id][index]

    def is_objective_done(self, mission_id: str, index: int) -> bool:
        return self.progress[mission_id][index] >= self.missions[mission_id].objectives[index].quantity

    def is_complete(self, mission_id: str) -> bool:
        mission = self.missions[mission_id]
        return all(self.is_objective_done(mission_id, i) for i in range(len(mission.objectives)))

    # ---- changes ----
    def start(self, mission_id: str, max_active: int = settings.MAX_ACTIVE_MISSIONS) -> bool:
        if self.status.get(mission_id) is not MissionStatus.AVAILABLE:
            return False
        if len(self.active()) >= max_active:
            return False
        self.status[mission_id] = MissionStatus.ACTIVE
        self._emit("MISSION_STARTED", {"id": mission_id})
        return True

    def notify(self, event: str, data: dict[str, Any] | None = None) -> list[str]:
        """Feed a game event to the active missions. Returns the ids completed by it."""
        payload = data or {}
        if event == "DAY_STARTED":
            self._check_deadlines(payload.get("day", 0))
        completed: list[str] = []
        for mission in self.active():                     # a fresh list: statuses may change below
            if self.status[mission.id] is not MissionStatus.ACTIVE:
                continue
            for index, objective in enumerate(mission.objectives):
                gained = objective_progress(objective, event, payload)
                if gained > 0 and self.progress[mission.id][index] < objective.quantity:
                    self.progress[mission.id][index] = min(
                        objective.quantity, self.progress[mission.id][index] + gained)
            if self.is_complete(mission.id):
                self._complete(mission.id)
                completed.append(mission.id)
        return completed

    def fail(self, mission_id: str) -> bool:
        if self.status.get(mission_id) not in (MissionStatus.ACTIVE, MissionStatus.AVAILABLE):
            return False
        self.status[mission_id] = MissionStatus.FAILED
        self._emit("MISSION_FAILED", {"id": mission_id})
        return True

    def force_complete(self, mission_id: str) -> bool:
        """Debug helper: fill every objective and complete the mission."""
        if self.status.get(mission_id) is not MissionStatus.ACTIVE:
            return False
        mission = self.missions[mission_id]
        self.progress[mission_id] = [o.quantity for o in mission.objectives]
        self._complete(mission_id)
        return True

    # ---- internals ----
    def _complete(self, mission_id: str) -> None:
        self.status[mission_id] = MissionStatus.COMPLETED
        self._refresh_availability()                       # unlock anything that required it
        self._emit("MISSION_COMPLETED", {"id": mission_id})

    def _check_deadlines(self, day: int) -> None:
        for mission in self.missions.values():
            if (mission.deadline_day is not None and day > mission.deadline_day
                    and self.status[mission.id] in (MissionStatus.ACTIVE, MissionStatus.AVAILABLE)):
                self.fail(mission.id)

    def _refresh_availability(self) -> None:
        for mission in self.missions.values():
            if (self.status[mission.id] is MissionStatus.LOCKED
                    and all(self.status[r] is MissionStatus.COMPLETED for r in mission.requires)):
                self.status[mission.id] = MissionStatus.AVAILABLE

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, data)

    # ---- persistence (used by the save system in Milestone 10) ----
    def serialize(self) -> dict[str, Any]:
        return {
            "status": {mid: status.name for mid, status in self.status.items()},
            "progress": {mid: list(values) for mid, values in self.progress.items()},
        }

    @classmethod
    def deserialize(cls, data: dict[str, Any], missions: dict[str, MissionDef],
                    event_bus: EventBus | None = None) -> MissionManager:
        manager = cls(missions, event_bus)
        raw_status = data.get("status", {}) if isinstance(data, dict) else {}
        if isinstance(raw_status, dict):
            for mission_id, name in raw_status.items():
                if (mission_id in missions and isinstance(name, str)
                        and name in MissionStatus.__members__):
                    manager.status[mission_id] = MissionStatus[name]
        raw_progress = data.get("progress", {}) if isinstance(data, dict) else {}
        if isinstance(raw_progress, dict):
            for mission_id, values in raw_progress.items():
                mission = missions.get(mission_id)
                if mission is None or not isinstance(values, list):
                    continue
                valid = (len(values) == len(mission.objectives)
                         and all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                                 for v in values))
                if valid:
                    manager.progress[mission_id] = [
                        min(v, o.quantity) for v, o in zip(values, mission.objectives)]
        manager._refresh_availability()
        return manager