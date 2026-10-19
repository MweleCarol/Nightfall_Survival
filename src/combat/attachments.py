"""Weapon attachments: optic, muzzle and grip slots with stat modifiers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.combat.weapon import ATTACHMENT_SLOTS, Weapon
from src.core import settings
from src.player.inventory import Inventory, ItemDef
from src.services.data_loader import DataLoadError, load_json, require_field

_NUMBER = (int, float)
MODIFIER_KEYS = ("damage", "range", "spread", "fire_rate", "reload", "magazine", "recoil")


@dataclass(frozen=True)
class AttachmentDef:
    id: str                              # also the id of the inventory item
    slot: str
    fits: tuple[str, ...] = ("any",)     # weapon ids it fits, or "any"
    damage: float = 0.0                  # all of these are fractions of the weapon's base stat
    range: float = 0.0
    spread: float = 0.0
    fire_rate: float = 0.0
    reload: float = 0.0
    magazine: float = 0.0                # extra rounds
    recoil: float = 0.0

    def modifiers(self) -> dict[str, float]:
        return {key: getattr(self, key) for key in MODIFIER_KEYS}

    def fits_weapon(self, weapon_id: str) -> bool:
        return "any" in self.fits or weapon_id in self.fits

    @classmethod
    def from_dict(cls, data: dict, item_defs: dict[str, ItemDef], where: str) -> AttachmentDef:
        item_id = require_field(data, "id", str, where)
        if item_id not in item_defs:
            raise DataLoadError(f"{where}: unknown item '{item_id}'")
        if item_defs[item_id].type != "attachment":
            raise DataLoadError(f"{where}: item '{item_id}' must have type 'attachment'")
        if item_defs[item_id].max_stack != 1:
            raise DataLoadError(f"{where}: item '{item_id}' must have max_stack 1")
        slot = require_field(data, "slot", str, where)
        if slot not in ATTACHMENT_SLOTS:
            raise DataLoadError(f"{where}: field 'slot' must be one of {ATTACHMENT_SLOTS}")
        fits = require_field(data, "fits", list, where) if "fits" in data else ["any"]
        if not fits or not all(isinstance(f, str) for f in fits):
            raise DataLoadError(f"{where}: field 'fits' must be a non-empty list of weapon ids")
        values: dict[str, float] = {}
        for key in MODIFIER_KEYS:
            if key in data:
                value = float(require_field(data, key, _NUMBER, where))
                low, high = (0.0, 60.0) if key == "magazine" else (-0.9, 2.0)
                if not low <= value <= high:
                    raise DataLoadError(f"{where}: field '{key}' must be between {low:g} and {high:g}")
                values[key] = value
        return cls(item_id, slot, tuple(fits), **values)


def load_attachment_defs(item_defs: dict[str, ItemDef],
                         path: str = settings.ATTACHMENTS_FILE) -> dict[str, AttachmentDef]:
    data = load_json(path)
    items = require_field(data, "attachments", list, path)
    definitions: dict[str, AttachmentDef] = {}
    for index, raw in enumerate(items):
        where = f"{path}: attachments[{index}]"
        if not isinstance(raw, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = AttachmentDef.from_dict(raw, item_defs, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


def attachment_modifiers(weapon: Weapon, defs: dict[str, AttachmentDef]) -> dict[str, float]:
    """The combined bonus of everything fitted to the weapon (empty slots add nothing)."""
    totals = {key: 0.0 for key in MODIFIER_KEYS}
    for item_id in weapon.attachments.values():
        definition = defs.get(item_id) if item_id else None
        if definition is None:
            continue
        for key, value in definition.modifiers().items():
            totals[key] += value
    return totals


def attachment_bonus_lines(definition: AttachmentDef) -> list[str]:
    """Readable effects, e.g. ['+10% range', '-15% spread']. Zero values are left out."""
    lines: list[str] = []
    for key, label in (("damage", "damage"), ("range", "range"), ("spread", "spread"),
                       ("fire_rate", "fire rate"), ("reload", "reload speed"), ("recoil", "recoil")):
        value = getattr(definition, key)
        if value:
            lines.append(f"{value:+.0%} {label}")
    if definition.magazine:
        lines.append(f"+{int(definition.magazine)} rounds")
    return lines


@dataclass
class AttachResult:
    success: bool
    message: str


def attach(weapon: Weapon, item_id: str, inventory: Inventory,
           defs: dict[str, AttachmentDef]) -> AttachResult:
    """Fit an attachment from the pack. Whatever was in that slot goes back to the pack."""
    definition = defs.get(item_id)
    if definition is None:
        return AttachResult(False, "That isn't a weapon attachment")
    if not inventory.has(item_id):
        return AttachResult(False, "You don't have that")
    if not definition.fits_weapon(weapon.definition.id):
        return AttachResult(False, f"That doesn't fit the {weapon.definition.name}")
    previous = weapon.attachments[definition.slot]
    inventory.remove(item_id, 1)
    if previous is not None:
        inventory.add(previous, 1)               # always fits: one slot was just freed
    weapon.attachments[definition.slot] = item_id
    return AttachResult(True, f"Attached {inventory.definitions[item_id].name}")


def detach(weapon: Weapon, slot: str, inventory: Inventory,
           defs: Sequence | dict) -> AttachResult:
    """Take an attachment off and put it back in the pack."""
    item_id = weapon.attachments.get(slot)
    if item_id is None:
        return AttachResult(False, "Nothing attached")
    if inventory.can_add(item_id, 1) < 1:
        return AttachResult(False, "Not enough room in your pack")
    inventory.add(item_id, 1)
    weapon.attachments[slot] = None
    return AttachResult(True, f"Removed {inventory.definitions[item_id].name}")