"""Weighted loot tables (data-driven) and rolling them."""
from __future__ import annotations

import random
from dataclasses import dataclass

from src.core import settings
from src.player.inventory import ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field

_NUMBER = (int, float)


@dataclass(frozen=True)
class LootEntry:
    item_id: str
    weight: float
    min_qty: int
    max_qty: int


@dataclass(frozen=True)
class LootTable:
    rolls_min: int
    rolls_max: int
    empty_weight: float
    entries: tuple[LootEntry, ...]

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> LootTable:
        rolls = require_field(data, "rolls", list, where)
        valid_rolls = (len(rolls) == 2
                       and all(isinstance(r, int) and not isinstance(r, bool) for r in rolls))
        if not valid_rolls or rolls[0] < 0 or rolls[1] < rolls[0]:
            raise DataLoadError(f"{where}: field 'rolls' must be [min, max] integers, 0 <= min <= max")
        empty_weight = float(require_field(data, "empty_weight", _NUMBER, where))
        if empty_weight < 0:
            raise DataLoadError(f"{where}: field 'empty_weight' must be >= 0")
        raw = require_field(data, "entries", list, where)
        if not raw:
            raise DataLoadError(f"{where}: 'entries' must not be empty")

        entries: list[LootEntry] = []
        for index, item in enumerate(raw):
            entry_where = f"{where}.entries[{index}]"
            if not isinstance(item, dict):
                raise DataLoadError(f"{entry_where}: must be an object")
            item_id = require_field(item, "item", str, entry_where)
            if item_id not in item_defs:
                raise DataLoadError(f"{entry_where}: unknown item '{item_id}'")
            weight = float(require_field(item, "weight", _NUMBER, entry_where))
            low = require_field(item, "min", int, entry_where)
            high = require_field(item, "max", int, entry_where)
            if weight <= 0 or low < 1 or high < low:
                raise DataLoadError(f"{entry_where}: weight must be > 0 and 1 <= min <= max")
            entries.append(LootEntry(item_id, weight, low, high))
        return cls(rolls[0], rolls[1], empty_weight, tuple(entries))


def load_loot_tables(item_defs: dict[str, ItemDef],
                     path: str = settings.LOOT_TABLES_FILE) -> dict[str, LootTable]:
    data = load_json(path)
    raw = require_field(data, "tables", dict, path)
    tables: dict[str, LootTable] = {}
    for table_id, table in raw.items():
        where = f"{path}: tables.{table_id}"
        if not isinstance(table, dict):
            raise DataLoadError(f"{where}: must be an object")
        tables[table_id] = LootTable.from_dict(table, item_defs, where)
    return tables


class LootSystem:
    """Rolls loot tables. Returns (item_id, quantity) pairs and never touches the UI."""

    def __init__(self, tables: dict[str, LootTable], rng: random.Random | None = None) -> None:
        self.tables = tables
        self.rng = rng or random.Random()

    def has_table(self, table_id: str) -> bool:
        return table_id in self.tables

    def table_for_enemy(self, enemy_id: str) -> str:
        specific = f"drop_{enemy_id}"
        return specific if specific in self.tables else "enemy_drop"

    def roll(self, table_id: str, luck: float = 0.0) -> list[tuple[str, int]]:
        """Roll a table. `luck` (0.0-1.0) shrinks the chance of getting nothing."""
        table = self.tables.get(table_id)
        if table is None:
            raise DataLoadError(f"Unknown loot table '{table_id}'")
        totals: dict[str, int] = {}
        for _ in range(self.rng.randint(table.rolls_min, table.rolls_max)):
            entry = self._pick(table, luck)
            if entry is None:
                continue
            quantity = self.rng.randint(entry.min_qty, entry.max_qty)
            totals[entry.item_id] = totals.get(entry.item_id, 0) + quantity
        return list(totals.items())

    def _pick(self, table: LootTable, luck: float) -> LootEntry | None:
        empty_weight = table.empty_weight * max(0.0, 1.0 - luck)
        total = empty_weight + sum(e.weight for e in table.entries)
        point = self.rng.uniform(0, total)
        if point < empty_weight:
            return None
        point -= empty_weight
        for entry in table.entries:
            if point < entry.weight:
                return entry
            point -= entry.weight
        return table.entries[-1]          # floating-point safety net