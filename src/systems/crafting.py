"""Crafting recipes and weapon upgrades (data-driven)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from src.combat.weapon import Weapon
from src.core import settings
from src.player.inventory import Inventory, ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field

UPGRADE_STATS = ("damage", "magazine", "reload")


def _parse_cost(value: Any, item_defs: dict[str, ItemDef], where: str) -> dict[str, int]:
    if not isinstance(value, dict) or not value:
        raise DataLoadError(f"{where}: cost must be a non-empty object")
    cost: dict[str, int] = {}
    for item_id, quantity in value.items():
        if item_id not in item_defs:
            raise DataLoadError(f"{where}: unknown item '{item_id}'")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise DataLoadError(f"{where}: cost of '{item_id}' must be an integer >= 1")
        cost[item_id] = quantity
    return cost


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    description: str
    output_item: str
    output_quantity: int
    cost: dict[str, int]


@dataclass(frozen=True)
class WeaponUpgradeDef:
    id: str
    name: str
    description: str
    stat: str
    per_level: float
    levels: tuple[dict[str, int], ...]      # the cost of each level, in order

    @property
    def max_level(self) -> int:
        return len(self.levels)


@dataclass(frozen=True)
class CraftingData:
    recipes: dict[str, Recipe]
    upgrades: dict[str, WeaponUpgradeDef]

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> CraftingData:
        recipes: dict[str, Recipe] = {}
        for index, raw in enumerate(require_field(data, "recipes", list, where)):
            rwhere = f"{where}: recipes[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{rwhere}: must be an object")
            output = require_field(raw, "output", dict, rwhere)
            output_item = require_field(output, "item", str, rwhere + ".output")
            output_quantity = require_field(output, "quantity", int, rwhere + ".output")
            if output_item not in item_defs:
                raise DataLoadError(f"{rwhere}.output: unknown item '{output_item}'")
            if output_quantity < 1:
                raise DataLoadError(f"{rwhere}.output: quantity must be >= 1")
            recipe = Recipe(
                id=require_field(raw, "id", str, rwhere),
                name=require_field(raw, "name", str, rwhere),
                description=require_field(raw, "description", str, rwhere),
                output_item=output_item, output_quantity=output_quantity,
                cost=_parse_cost(raw.get("cost"), item_defs, rwhere + ".cost"))
            if recipe.id in recipes:
                raise DataLoadError(f"{rwhere}: duplicate id '{recipe.id}'")
            recipes[recipe.id] = recipe

        upgrades: dict[str, WeaponUpgradeDef] = {}
        for index, raw in enumerate(require_field(data, "weapon_upgrades", list, where)):
            uwhere = f"{where}: weapon_upgrades[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{uwhere}: must be an object")
            stat = require_field(raw, "stat", str, uwhere)
            if stat not in UPGRADE_STATS:
                raise DataLoadError(f"{uwhere}: field 'stat' must be one of {UPGRADE_STATS}")
            per_level = float(require_field(raw, "per_level", (int, float), uwhere))
            raw_levels = require_field(raw, "levels", list, uwhere)
            if per_level <= 0 or not raw_levels:
                raise DataLoadError(f"{uwhere}: per_level must be > 0 and levels must not be empty")
            upgrade = WeaponUpgradeDef(
                id=require_field(raw, "id", str, uwhere),
                name=require_field(raw, "name", str, uwhere),
                description=require_field(raw, "description", str, uwhere),
                stat=stat, per_level=per_level,
                levels=tuple(_parse_cost(level, item_defs, f"{uwhere}.levels[{i}]")
                             for i, level in enumerate(raw_levels)))
            if upgrade.id in upgrades:
                raise DataLoadError(f"{uwhere}: duplicate id '{upgrade.id}'")
            upgrades[upgrade.id] = upgrade
        return cls(recipes, upgrades)


def load_crafting_data(item_defs: dict[str, ItemDef],
                       path: str = settings.CRAFTING_FILE) -> CraftingData:
    return CraftingData.from_dict(load_json(path), item_defs, path)


@dataclass
class CraftResult:
    success: bool
    message: str
    free: bool = False


class CraftingSystem:
    """Crafting and weapon upgrades. Every action either fully succeeds or changes nothing."""

    def __init__(self, data: CraftingData, inventory: Inventory,
                 rng: random.Random | None = None) -> None:
        self.data = data
        self.inventory = inventory
        self.rng = rng or random.Random()

    def has_materials(self, cost: dict[str, int]) -> bool:
        return all(self.inventory.has(item_id, qty) for item_id, qty in cost.items())

    def craft(self, recipe_id: str, free_chance: float = 0.0) -> CraftResult:
        recipe = self.data.recipes.get(recipe_id)
        if recipe is None:
            return CraftResult(False, "Unknown recipe")
        if not self.has_materials(recipe.cost):
            return CraftResult(False, "Missing materials")

        free = free_chance > 0 and self.rng.random() < free_chance
        if not free:
            for item_id, qty in recipe.cost.items():
                self.inventory.remove(item_id, qty)

        added = self.inventory.add(recipe.output_item, recipe.output_quantity)
        if added < recipe.output_quantity:
            # No room for the result: undo everything so nothing is lost.
            self.inventory.remove(recipe.output_item, added)
            if not free:
                for item_id, qty in recipe.cost.items():
                    self.inventory.add(item_id, qty)
            return CraftResult(False, "Inventory full")
        return CraftResult(True, f"Crafted {recipe.name}" + (" (free!)" if free else ""), free)

    # ---- weapon upgrades ----
    def upgrade_bonus(self, stat: str, weapon: Weapon) -> float:
        """Total bonus for one stat from all of this weapon's upgrades."""
        return sum(u.per_level * weapon.upgrade_levels.get(u.id, 0)
                   for u in self.data.upgrades.values() if u.stat == stat)

    def next_upgrade_cost(self, upgrade_id: str, weapon: Weapon) -> dict[str, int] | None:
        """Cost of the next level, or None when the upgrade is maxed (or unknown)."""
        upgrade = self.data.upgrades.get(upgrade_id)
        if upgrade is None:
            return None
        level = weapon.upgrade_levels.get(upgrade_id, 0)
        return upgrade.levels[level] if level < upgrade.max_level else None

    def upgrade_weapon(self, upgrade_id: str, weapon: Weapon) -> CraftResult:
        upgrade = self.data.upgrades.get(upgrade_id)
        if upgrade is None:
            return CraftResult(False, "Unknown upgrade")
        cost = self.next_upgrade_cost(upgrade_id, weapon)
        if cost is None:
            return CraftResult(False, f"{upgrade.name} is already at max level")
        if not self.has_materials(cost):
            return CraftResult(False, "Missing materials")
        for item_id, qty in cost.items():
            self.inventory.remove(item_id, qty)
        level = weapon.upgrade_levels.get(upgrade_id, 0) + 1
        weapon.upgrade_levels[upgrade_id] = level
        return CraftResult(True, f"{upgrade.name} upgraded to level {level}")