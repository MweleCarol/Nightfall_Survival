"""Weapon definitions (loaded from JSON) and the runtime Weapon state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core import settings
from src.services.data_loader import DataLoadError, load_json, require_field

_NUMBER = (int, float)


@dataclass(frozen=True)
class WeaponDef:
    """Static weapon stats: one per entry in weapons.json."""
    id: str
    name: str
    damage: int
    fire_rate: float        # shots per second
    magazine_size: int
    ammo_type: str
    reload_time: float      # seconds
    range: float            # pixels
    spread: float           # degrees of random aim error to either side
    rarity: str
    automatic: bool         # True = hold the button to keep firing

    @classmethod
    def from_dict(cls, data: dict, where: str) -> WeaponDef:
        definition = cls(
            id=require_field(data, "id", str, where),
            name=require_field(data, "name", str, where),
            damage=require_field(data, "damage", int, where),
            fire_rate=float(require_field(data, "fire_rate", _NUMBER, where)),
            magazine_size=require_field(data, "magazine_size", int, where),
            ammo_type=require_field(data, "ammo_type", str, where),
            reload_time=float(require_field(data, "reload_time", _NUMBER, where)),
            range=float(require_field(data, "range", _NUMBER, where)),
            spread=float(require_field(data, "spread", _NUMBER, where)),
            rarity=require_field(data, "rarity", str, where),
            automatic=require_field(data, "automatic", bool, where),
        )
        if (definition.damage <= 0 or definition.fire_rate <= 0
                or definition.magazine_size <= 0 or definition.range <= 0):
            raise DataLoadError(
                f"{where}: damage, fire_rate, magazine_size and range must be > 0")
        if definition.reload_time < 0 or definition.spread < 0:
            raise DataLoadError(f"{where}: reload_time and spread must be >= 0")
        return definition


def load_weapon_defs(path: str = settings.WEAPONS_FILE) -> dict[str, WeaponDef]:
    data = load_json(path)
    items = require_field(data, "weapons", list, path)
    definitions: dict[str, WeaponDef] = {}
    for index, item in enumerate(items):
        where = f"{path}: weapons[{index}]"
        if not isinstance(item, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = WeaponDef.from_dict(item, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


class AmmoSource(Protocol):
    """Anything that can hold ammo (the player's Inventory satisfies this)."""

    def count(self, item_id: str) -> int: ...
    def remove(self, item_id: str, quantity: int) -> int: ...


class Weapon:
    """A weapon being carried: ammo, cooldown, reload state and upgrades.

    Spare ammo comes from `ammo_source` (the Inventory) when one is given,
    otherwise from a plain `reserve` number (handy for tests).

    `modifiers` holds the combined bonus from skills and weapon upgrades:
        "damage"   - fraction, 0.2 means +20% damage
        "reload"   - fraction, 0.2 means reloads take 20% less time
        "magazine" - extra rounds in the magazine
    """

    def __init__(self, definition: WeaponDef, loaded: int | None = None,
                 reserve: int = 0, ammo_source: AmmoSource | None = None) -> None:
        self.definition = definition
        start = definition.magazine_size if loaded is None else loaded
        self.loaded = max(0, min(definition.magazine_size, start))
        self._reserve = max(0, reserve)
        self.ammo_source = ammo_source
        self.modifiers: dict[str, float] = {}
        self.upgrade_levels: dict[str, int] = {}   # which upgrades were bought, and how far
        self.cooldown = 0.0
        self.reload_remaining = 0.0
        self.is_reloading = False

    # ---- stats with modifiers applied ----
    @property
    def damage(self) -> int:
        return max(1, round(self.definition.damage * (1.0 + self.modifiers.get("damage", 0.0))))

    @property
    def magazine_size(self) -> int:
        return self.definition.magazine_size + round(self.modifiers.get("magazine", 0.0))

    @property
    def reload_time(self) -> float:
        factor = max(0.25, 1.0 - self.modifiers.get("reload", 0.0))   # never faster than 25%
        return self.definition.reload_time * factor

    # ---- ammo ----
    @property
    def ammo_item_id(self) -> str:
        return f"ammo_{self.definition.ammo_type}"

    @property
    def reserve(self) -> int:
        if self.ammo_source is not None:
            return self.ammo_source.count(self.ammo_item_id)
        return self._reserve

    def _take_reserve(self, amount: int) -> int:
        if self.ammo_source is not None:
            return self.ammo_source.remove(self.ammo_item_id, amount)
        taken = min(amount, self._reserve)
        self._reserve -= taken
        return taken

    # ---- firing and reloading ----
    def can_fire(self) -> bool:
        return not self.is_reloading and self.loaded > 0 and self.cooldown <= 0

    def fire(self) -> bool:
        """Spend one round if allowed. Returns True if a shot was fired."""
        if not self.can_fire():
            return False
        self.loaded -= 1
        self.cooldown = 1.0 / self.definition.fire_rate
        return True

    def start_reload(self) -> bool:
        """Begin reloading. False if pointless (full magazine / no spare ammo)."""
        if (self.is_reloading or self.loaded >= self.magazine_size
                or self.reserve <= 0):
            return False
        self.is_reloading = True
        self.reload_remaining = self.reload_time
        return True

    @property
    def reload_progress(self) -> float:
        """0.0 -> 1.0 while reloading (for the HUD bar)."""
        if not self.is_reloading or self.reload_time <= 0:
            return 0.0
        return 1.0 - self.reload_remaining / self.reload_time

    def update(self, dt: float) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.is_reloading:
            self.reload_remaining -= dt
            if self.reload_remaining <= 0:
                self._finish_reload()

    def _finish_reload(self) -> None:
        needed = self.magazine_size - self.loaded
        self.loaded += self._take_reserve(needed)
        self.is_reloading = False
        self.reload_remaining = 0.0