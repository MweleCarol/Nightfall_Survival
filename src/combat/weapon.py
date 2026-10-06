"""Weapon definitions (loaded from JSON) and the runtime Weapon state."""
from __future__ import annotations

from dataclasses import dataclass

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


class Weapon:
    """A weapon being carried: ammo, cooldown and reload state.

    `reserve` is spare ammo for now; Milestone 5 moves it into the Inventory.
    """

    def __init__(self, definition: WeaponDef, loaded: int | None = None,
                 reserve: int = 0) -> None:
        self.definition = definition
        start = definition.magazine_size if loaded is None else loaded
        self.loaded = max(0, min(definition.magazine_size, start))
        self.reserve = max(0, reserve)
        self.cooldown = 0.0
        self.reload_remaining = 0.0
        self.is_reloading = False

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
        if (self.is_reloading or self.loaded >= self.definition.magazine_size
                or self.reserve <= 0):
            return False
        self.is_reloading = True
        self.reload_remaining = self.definition.reload_time
        return True

    @property
    def reload_progress(self) -> float:
        """0.0 -> 1.0 while reloading (for the HUD bar)."""
        if not self.is_reloading or self.definition.reload_time <= 0:
            return 0.0
        return 1.0 - self.reload_remaining / self.definition.reload_time

    def update(self, dt: float) -> None:
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.is_reloading:
            self.reload_remaining -= dt
            if self.reload_remaining <= 0:
                self._finish_reload()

    def _finish_reload(self) -> None:
        needed = self.definition.magazine_size - self.loaded
        moved = min(needed, self.reserve)
        self.loaded += moved
        self.reserve -= moved
        self.is_reloading = False
        self.reload_remaining = 0.0