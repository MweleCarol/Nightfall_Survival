"""HUD pieces for progression: level, XP bar and the skill-point reminder."""
from __future__ import annotations

import pygame

from src.core import settings
from src.systems.progression import Progression

XP_COLOR = (90, 150, 235)


class ProgressionHUD:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("arial", 16, bold=True)

    def draw(self, surface: pygame.Surface, progression: Progression) -> None:
        x, y, width, height = 20, 110, 260, 10
        pygame.draw.rect(surface, (20, 26, 40), (x, y, width, height))
        pygame.draw.rect(surface, XP_COLOR, (x, y, int(width * progression.progress), height))
        pygame.draw.rect(surface, (70, 88, 120), (x, y, width, height), 1)

        if progression.is_max_level:
            text = f"LEVEL {progression.level}  (MAX)"
        else:
            text = (f"LEVEL {progression.level}   "
                    f"XP {progression.xp}/{progression.xp_required()}")
        surface.blit(self.font.render(text, True, settings.COLOR_TEXT), (x, y + 14))

        if progression.skill_points > 0:
            points = progression.skill_points
            note = f"K - {points} SKILL POINT{'S' if points != 1 else ''} AVAILABLE"
            surface.blit(self.font.render(note, True, settings.COLOR_AMBER), (x, y + 36))