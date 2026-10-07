"""Skills overlay (opened with K): spend skill points."""
from __future__ import annotations

import pygame

from src.core import settings
from src.systems.progression import Progression
from src.systems.skills import SkillSet
from src.ui.widgets import (
    SelectionList, draw_panel, draw_row_highlight, make_dim, wrap_text,
)

CATEGORY_COLORS = {
    "survivor": (110, 200, 120),
    "combat": (224, 34, 27),
    "survival": (245, 165, 36),
}


class SkillsUI:
    def __init__(self, skills: SkillSet, progression: Progression) -> None:
        self.skills = skills
        self.progression = progression
        self.order = list(skills.definitions.values())
        self.nav = SelectionList()
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    def reset(self) -> None:
        self.nav.reset()

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN:
            return None
        if event.key in (pygame.K_UP, pygame.K_w):
            self.nav.move(-1, len(self.order))
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.nav.move(1, len(self.order))
        elif event.key == pygame.K_RETURN and self.order:
            skill = self.order[self.nav.selected]
            if self.skills.purchase(skill.id, self.progression):
                return f"{skill.name} - rank {self.skills.rank(skill.id)}"
            if self.skills.is_maxed(skill.id):
                return f"{skill.name} is already maxed"
            return "No skill points available"
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        progression = self.progression
        draw_panel(surface, panel, "SKILLS", self.title_font,
                   f"LEVEL {progression.level}     SKILL POINTS {progression.skill_points}",
                   self.font)

        for index, skill in enumerate(self.order):
            row = pygame.Rect(panel.x + 24, panel.y + 74 + index * 40, 440, 34)
            draw_row_highlight(surface, row, index == self.nav.selected)
            pygame.draw.rect(surface, CATEGORY_COLORS[skill.category],
                             (row.x, row.y, 5, row.height))
            surface.blit(self.font.render(skill.name, True, settings.COLOR_TEXT),
                         (row.x + 16, row.y + 5))
            rank = self.skills.rank(skill.id)
            for pip in range(skill.max_rank):             # rank pips on the right
                pip_rect = pygame.Rect(row.right - 12 - (skill.max_rank - pip) * 20,
                                       row.y + 10, 14, 14)
                if pip < rank:
                    pygame.draw.rect(surface, settings.COLOR_AMBER, pip_rect)
                else:
                    pygame.draw.rect(surface, (70, 88, 120), pip_rect, 2)

        if self.order:
            skill = self.order[self.nav.selected]
            x, y = panel.x + 500, panel.y + 80
            surface.blit(self.title_font.render(skill.name, True, settings.COLOR_TEXT), (x, y))
            surface.blit(self.small_font.render(skill.category.upper(), True,
                         CATEGORY_COLORS[skill.category]), (x, y + 44))
            for line_number, line in enumerate(wrap_text(skill.description, self.small_font, 360)):
                surface.blit(self.small_font.render(line, True, settings.COLOR_TEXT),
                             (x, y + 80 + line_number * 24))
            rank = self.skills.rank(skill.id)
            surface.blit(self.font.render(f"Rank {rank} / {skill.max_rank}", True,
                         settings.COLOR_AMBER), (x, y + 170))
            if self.skills.is_maxed(skill.id):
                note, color = "MAX RANK", settings.COLOR_SAFE
            elif progression.skill_points > 0:
                note, color = "ENTER - spend 1 skill point", settings.COLOR_AMBER
            else:
                note, color = "No skill points available", settings.COLOR_MUTED
            surface.blit(self.small_font.render(note, True, color), (x, y + 210))

        hint = self.small_font.render("W/S select   |   ENTER upgrade   |   K or ESC close",
                                      True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))