"""Wearable gear: five slots with bonuses (armor, carry slots, health, stamina, speed)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.core import settings
from src.player.inventory import Inventory, ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field

SLOTS = ("head", "face", "body", "backpack", "accessory")
STAT_KEYS = ("armor", "carry_slots", "max_health", "max_stamina", "move_speed")


@dataclass(frozen=True)
class EquipmentDef:
    id: str                    # also the id of the inventory item
    slot: str
    armor: int
    carry_slots: int
    max_health: int
    max_stamina: int
    move_speed: float          # a fraction: -0.02 means 2% slower

    def stats(self) -> dict[str, float]:
        return {"armor": self.armor, "carry_slots": self.carry_slots, "max_health": self.max_health,
                "max_stamina": self.max_stamina, "move_speed": self.move_speed}

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> EquipmentDef:
        item_id = require_field(data, "id", str, where)
        if item_id not in item_defs:
            raise DataLoadError(f"{where}: unknown item '{item_id}'")
        if item_defs[item_id].type != "equipment":
            raise DataLoadError(f"{where}: item '{item_id}' must have type 'equipment'")
        if item_defs[item_id].max_stack != 1:
            raise DataLoadError(f"{where}: item '{item_id}' must have max_stack 1")
        slot = require_field(data, "slot", str, where)
        if slot not in SLOTS:
            raise DataLoadError(f"{where}: field 'slot' must be one of {SLOTS}")

        def whole(key: str) -> int:
            value = require_field(data, key, int, where) if key in data else 0
            if value < 0:
                raise DataLoadError(f"{where}: field '{key}' must be >= 0")
            return value

        speed = float(require_field(data, "move_speed", (int, float), where)) if "move_speed" in data else 0.0
        if not -0.5 <= speed <= 0.5:
            raise DataLoadError(f"{where}: field 'move_speed' must be between -0.5 and 0.5")
        return cls(item_id, slot, whole("armor"), whole("carry_slots"), whole("max_health"),
                   whole("max_stamina"), speed)


def load_equipment_defs(item_defs: dict[str, ItemDef],
                        path: str = settings.EQUIPMENT_FILE) -> dict[str, EquipmentDef]:
    data = load_json(path)
    items = require_field(data, "equipment", list, path)
    definitions: dict[str, EquipmentDef] = {}
    for index, raw in enumerate(items):
        where = f"{path}: equipment[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = EquipmentDef.from_dict(raw, item_defs, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


def bonus_lines(stats: dict[str, float]) -> list[str]:
    """Human-readable bonuses, e.g. ['18 armor', '-2% speed']. Zero values are left out."""
    lines: list[str] = []
    if stats.get("armor"):
        lines.append(f"{int(stats['armor'])} armor")
    if stats.get("carry_slots"):
        lines.append(f"+{int(stats['carry_slots'])} slots")
    if stats.get("max_health"):
        lines.append(f"+{int(stats['max_health'])} HP")
    if stats.get("max_stamina"):
        lines.append(f"+{int(stats['max_stamina'])} stamina")
    if stats.get("move_speed"):
        lines.append(f"{stats['move_speed']:+.0%} speed")
    return lines


@dataclass
class EquipResult:
    success: bool
    message: str


def _slots_needed(counts: dict[str, int], definitions: dict[str, ItemDef]) -> int:
    return sum(math.ceil(quantity / definitions[item_id].max_stack)
               for item_id, quantity in counts.items() if quantity > 0)


class Equipment:
    """What the player is wearing. Equipping moves items between the pack and the slots."""

    def __init__(self, definitions: dict[str, EquipmentDef]) -> None:
        self.definitions = definitions
        self.slots: dict[str, str | None] = {slot: None for slot in SLOTS}

    def item_in(self, slot: str) -> str | None:
        return self.slots.get(slot)

    def totals(self) -> dict[str, float]:
        totals: dict[str, float] = {key: 0 for key in STAT_KEYS}
        totals["move_speed"] = 0.0
        for item_id in self.slots.values():
            if item_id is None:
                continue
            for key, value in self.definitions[item_id].stats().items():
                totals[key] += value
        return totals

    def place(self, item_id: str) -> bool:
        """Put a piece straight into its slot (new game or loading a save). No inventory involved."""
        definition = self.definitions.get(item_id)
        if definition is None:
            return False
        self.slots[definition.slot] = item_id
        return True

    def _carry_of(self, item_id: str | None) -> int:
        return self.definitions[item_id].carry_slots if item_id else 0

    def equip(self, item_id: str, inventory: Inventory, base_capacity: int) -> EquipResult:
        """Wear an item from the pack. The piece it replaces goes back to the pack."""
        definition = self.definitions.get(item_id)
        if definition is None:
            return EquipResult(False, "That can't be worn")
        if not inventory.has(item_id):
            return EquipResult(False, "You don't have that")
        previous = self.slots[definition.slot]
        carry = self.totals()["carry_slots"] - self._carry_of(previous) + definition.carry_slots
        new_capacity = base_capacity + int(carry)

        counts = inventory.serialize()                    # would everything still fit afterwards?
        counts[item_id] -= 1
        if previous is not None:
            counts[previous] = counts.get(previous, 0) + 1
        if _slots_needed(counts, inventory.definitions) > new_capacity:
            return EquipResult(False, "Not enough room in your pack")

        inventory.remove(item_id, 1)
        inventory.capacity = new_capacity
        if previous is not None:
            inventory.add(previous, 1)
        self.slots[definition.slot] = item_id
        return EquipResult(True, f"Equipped {inventory.definitions[item_id].name}")

    def unequip(self, slot: str, inventory: Inventory, base_capacity: int) -> EquipResult:
        item_id = self.slots.get(slot)
        if item_id is None:
            return EquipResult(False, "Nothing to take off")
        carry = self.totals()["carry_slots"] - self._carry_of(item_id)
        new_capacity = base_capacity + int(carry)

        counts = inventory.serialize()
        counts[item_id] = counts.get(item_id, 0) + 1
        if _slots_needed(counts, inventory.definitions) > new_capacity:
            return EquipResult(False, "Not enough room in your pack")

        inventory.capacity = new_capacity
        inventory.add(item_id, 1)
        self.slots[slot] = None
        return EquipResult(True, f"Removed {inventory.definitions[item_id].name}")

    # ---- persistence (used by the save system in Milestone 10) ----
    def serialize(self) -> dict[str, str | None]:
        return dict(self.slots)

    @classmethod
    def deserialize(cls, data: dict[str, Any], definitions: dict[str, EquipmentDef]) -> Equipment:
        equipment = cls(definitions)
        for slot, item_id in data.items():
            if slot in SLOTS and isinstance(item_id, str) and item_id in definitions \
                    and definitions[item_id].slot == slot:
                equipment.slots[slot] = item_id
        return equipment