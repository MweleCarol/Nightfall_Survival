"""Creates enemies from their data definitions."""
from __future__ import annotations

from src.enemies.enemy import Enemy, EnemyDef, load_enemy_defs
from src.enemies.walker import Walker
from src.services.data_loader import DataLoadError

# Maps the "type" field in enemies.json to a Python class. New enemies register here.
ENEMY_CLASSES: dict[str, type[Enemy]] = {"walker": Walker}


class EnemyFactory:
    def __init__(self, definitions: dict[str, EnemyDef] | None = None) -> None:
        self.definitions = definitions if definitions is not None else load_enemy_defs()

    def create(self, enemy_id: str, position: tuple[float, float],
               health_multiplier: float = 1.0, damage_multiplier: float = 1.0) -> Enemy:
        if enemy_id not in self.definitions:
            raise DataLoadError(f"Unknown enemy id '{enemy_id}'")
        definition = self.definitions[enemy_id]
        enemy_class = ENEMY_CLASSES.get(definition.type, Enemy)
        return enemy_class(definition, position, health_multiplier, damage_multiplier)