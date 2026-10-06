"""Item definitions (from JSON) and the slot-based Inventory."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.core import settings
from src.services.data_loader import DataLoadError, load_json, require_field

ITEM_TYPES = ("ammo", "resource", "consumable", "quest")
RARITIES = ("common", "uncommon", "rare", "epic", "legendary")


@dataclass(frozen=True)
class ItemDef:
    """Static item data: one per entry in items.json."""
    id: str
    name: str
    type: str
    max_stack: int
    rarity: str
    heal: int = 0
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict, where: str) -> ItemDef:
        item_type = require_field(data, "type", str, where)
        if item_type not in ITEM_TYPES:
            raise DataLoadError(f"{where}: field 'type' must be one of {ITEM_TYPES}")
        rarity = require_field(data, "rarity", str, where)
        if rarity not in RARITIES:
            raise DataLoadError(f"{where}: field 'rarity' must be one of {RARITIES}")
        max_stack = require_field(data, "max_stack", int, where)
        if max_stack <= 0:
            raise DataLoadError(f"{where}: field 'max_stack' must be > 0")
        heal = require_field(data, "heal", int, where) if "heal" in data else 0
        if heal < 0:
            raise DataLoadError(f"{where}: field 'heal' must be >= 0")
        description = require_field(data, "description", str, where) if "description" in data else ""
        return cls(
            id=require_field(data, "id", str, where),
            name=require_field(data, "name", str, where),
            type=item_type, max_stack=max_stack, rarity=rarity,
            heal=heal, description=description,
        )


def load_item_defs(path: str = settings.ITEMS_FILE) -> dict[str, ItemDef]:
    data = load_json(path)
    items = require_field(data, "items", list, path)
    definitions: dict[str, ItemDef] = {}
    for index, item in enumerate(items):
        where = f"{path}: items[{index}]"
        if not isinstance(item, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = ItemDef.from_dict(item, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


class Inventory:
    """Slot-based storage. A slot holds one item type, up to that item's max_stack."""

    def __init__(self, capacity: int, definitions: dict[str, ItemDef]) -> None:
        if capacity <= 0:
            raise ValueError("Inventory capacity must be positive")
        self.capacity = capacity
        self.definitions = definitions
        self._items: dict[str, int] = {}

    # ---- queries ----
    def _definition(self, item_id: str) -> ItemDef:
        try:
            return self.definitions[item_id]
        except KeyError:
            raise ValueError(f"Unknown item id '{item_id}'") from None

    @property
    def slots_used(self) -> int:
        return sum(math.ceil(qty / self._definition(item_id).max_stack)
                   for item_id, qty in self._items.items())

    def count(self, item_id: str) -> int:
        return self._items.get(item_id, 0)

    def has(self, item_id: str, quantity: int = 1) -> bool:
        return self.count(item_id) >= quantity

    def items(self) -> list[tuple[str, int]]:
        """Contents sorted by type, then name (for display)."""
        def sort_key(entry: tuple[str, int]) -> tuple[int, str]:
            definition = self._definition(entry[0])
            return (ITEM_TYPES.index(definition.type), definition.name)
        return sorted(self._items.items(), key=sort_key)

    def can_add(self, item_id: str, quantity: int) -> int:
        """How many of `quantity` would actually fit right now."""
        if quantity <= 0:
            return 0
        max_stack = self._definition(item_id).max_stack
        current = self.count(item_id)
        room_in_existing = math.ceil(current / max_stack) * max_stack - current
        free_slots = self.capacity - self.slots_used
        return max(0, min(quantity, room_in_existing + free_slots * max_stack))

    # ---- changes ----
    def add(self, item_id: str, quantity: int = 1) -> int:
        """Add as many as fit. Returns the number actually added."""
        if quantity <= 0:
            return 0
        added = self.can_add(item_id, quantity)
        if added:
            self._items[item_id] = self.count(item_id) + added
        return added

    def remove(self, item_id: str, quantity: int = 1) -> int:
        """Remove up to `quantity`. Returns the number actually removed."""
        removed = min(max(0, quantity), self.count(item_id))
        if removed:
            remaining = self.count(item_id) - removed
            if remaining > 0:
                self._items[item_id] = remaining
            else:
                del self._items[item_id]
        return removed

    # ---- persistence (used by the save system in Milestone 10) ----
    def serialize(self) -> dict[str, int]:
        return dict(self._items)

    @classmethod
    def deserialize(cls, data: dict[str, Any], capacity: int,
                    definitions: dict[str, ItemDef]) -> Inventory:
        inventory = cls(capacity, definitions)
        for item_id, quantity in data.items():
            valid = (item_id in definitions and isinstance(quantity, int)
                     and not isinstance(quantity, bool) and quantity > 0)
            if valid:
                inventory.add(item_id, quantity)
        return inventory