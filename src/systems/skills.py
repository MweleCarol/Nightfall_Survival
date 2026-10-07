"""Skill definitions (from JSON) and the ranks the player has bought."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core import settings
from src.services.data_loader import DataLoadError, load_json, require_field
from src.systems.progression import Progression

CATEGORIES = ("survivor", "combat", "survival")

# Every stat name the game knows how to apply. A typo in skills.json fails loudly
# at load time instead of silently doing nothing.
KNOWN_STATS = (
    "max_health", "max_stamina", "move_speed", "damage", "reload_time_reduction",
    "crit_chance", "carry_slots", "loot_luck", "free_craft_chance",
)


@dataclass(frozen=True)
class SkillDef:
    id: str
    name: str
    category: str
    stat: str
    per_rank: float
    max_rank: int
    description: str

    @classmethod
    def from_dict(cls, data: dict, where: str) -> SkillDef:
        category = require_field(data, "category", str, where)
        if category not in CATEGORIES:
            raise DataLoadError(f"{where}: field 'category' must be one of {CATEGORIES}")
        stat = require_field(data, "stat", str, where)
        if stat not in KNOWN_STATS:
            raise DataLoadError(f"{where}: field 'stat' must be one of {KNOWN_STATS}")
        per_rank = float(require_field(data, "per_rank", (int, float), where))
        max_rank = require_field(data, "max_rank", int, where)
        if per_rank <= 0 or max_rank < 1:
            raise DataLoadError(f"{where}: per_rank must be > 0 and max_rank >= 1")
        return cls(
            id=require_field(data, "id", str, where),
            name=require_field(data, "name", str, where),
            category=category, stat=stat, per_rank=per_rank, max_rank=max_rank,
            description=require_field(data, "description", str, where),
        )


def load_skill_defs(path: str = settings.SKILLS_FILE) -> dict[str, SkillDef]:
    data = load_json(path)
    items = require_field(data, "skills", list, path)
    definitions: dict[str, SkillDef] = {}
    for index, item in enumerate(items):
        where = f"{path}: skills[{index}]"
        if not isinstance(item, dict):
            raise DataLoadError(f"{where}: must be an object")
        definition = SkillDef.from_dict(item, where)
        if definition.id in definitions:
            raise DataLoadError(f"{where}: duplicate id '{definition.id}'")
        definitions[definition.id] = definition
    return definitions


class SkillSet:
    """The ranks bought so far. `bonus(stat)` is how the rest of the game reads them."""

    def __init__(self, definitions: dict[str, SkillDef],
                 ranks: dict[str, int] | None = None) -> None:
        self.definitions = definitions
        self.ranks: dict[str, int] = {}
        for skill_id, rank in (ranks or {}).items():
            valid = (skill_id in definitions and isinstance(rank, int)
                     and not isinstance(rank, bool) and rank > 0)
            if valid:
                self.ranks[skill_id] = min(rank, definitions[skill_id].max_rank)

    def rank(self, skill_id: str) -> int:
        return self.ranks.get(skill_id, 0)

    def is_maxed(self, skill_id: str) -> bool:
        definition = self.definitions.get(skill_id)
        return definition is not None and self.rank(skill_id) >= definition.max_rank

    def bonus(self, stat: str) -> float:
        """Total bonus for a stat from all skills (rank x per_rank, summed)."""
        return sum(d.per_rank * self.rank(d.id)
                   for d in self.definitions.values() if d.stat == stat)

    def purchase(self, skill_id: str, progression: Progression) -> bool:
        """Spend one skill point to raise a skill by one rank."""
        if skill_id not in self.definitions or self.is_maxed(skill_id):
            return False
        if not progression.spend_skill_point():
            return False
        self.ranks[skill_id] = self.rank(skill_id) + 1
        return True

    def serialize(self) -> dict[str, int]:
        return dict(self.ranks)

    @classmethod
    def deserialize(cls, data: dict[str, Any], definitions: dict[str, SkillDef]) -> SkillSet:
        return cls(definitions, data)