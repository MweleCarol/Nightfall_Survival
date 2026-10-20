"""Hub page: the skill tree, laid out like the design (character, skill grid, details)."""
from __future__ import annotations

import pygame

from src.combat.armor import damage_reduction
from src.systems.skills import CATEGORIES
from src.ui import theme
from src.ui.hub import HubContext, HubPage
from src.ui.hub_widgets import (
    draw_button, draw_portrait, draw_skill_icon, format_skill_effect, get_font,
)
from src.ui.kit import cut_panel, draw_bar, draw_hud_icon, fit_text
from src.ui.widgets import wrap_text

CATEGORY_COLORS = {"survivor": (110, 200, 120), "combat": (224, 70, 60), "survival": theme.AMBER}
CARD_W, CARD_H, COLUMN_STEP, ROW_STEP = 186, 112, 196, 122


class SkillsPage(HubPage):
    def __init__(self) -> None:
        self.col = 0
        self.row = 0
        self.card_rects: list[tuple[pygame.Rect, int, int]] = []     # (rect, column, row)
        self.button_rect = pygame.Rect(0, 0, 0, 0)
        self._panels: dict[tuple[int, int], pygame.Surface] = {}

    def hints(self) -> list[tuple[str, str]]:
        return [("W/A/S/D", "MOVE"), ("ENTER", "UPGRADE")]

    # ---- data ----
    @staticmethod
    def _columns(ctx: HubContext) -> list[list[str]]:
        return [[d.id for d in ctx.skills.definitions.values() if d.category == category]
                for category in CATEGORIES]

    def _clamp(self, columns: list[list[str]]) -> None:
        self.col = max(0, min(self.col, len(columns) - 1))
        self.row = max(0, min(self.row, max(0, len(columns[self.col]) - 1)))

    def selected_skill(self, ctx: HubContext):
        columns = self._columns(ctx)
        self._clamp(columns)
        ids = columns[self.col]
        return ctx.skills.definitions[ids[self.row]] if ids else None

    # ---- input ----
    def handle_event(self, event: pygame.event.Event, ctx: HubContext) -> str | None:
        columns = self._columns(ctx)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, col, row in self.card_rects:
                if rect.collidepoint(event.pos):
                    self.col, self.row = col, row
                    return None
            if self.button_rect.collidepoint(event.pos):
                return self._buy(ctx)
            return None
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a):
            self.col -= 1
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.col += 1
        elif key in (pygame.K_UP, pygame.K_w):
            self.row -= 1
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.row += 1
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._buy(ctx)
        self._clamp(columns)
        return None

    def _buy(self, ctx: HubContext) -> str | None:
        skill = self.selected_skill(ctx)
        if skill is None:
            return None
        if ctx.skills.purchase(skill.id, ctx.progression):
            return f"{skill.name} - rank {ctx.skills.rank(skill.id)}"
        if ctx.skills.is_maxed(skill.id):
            return f"{skill.name} is already maxed"
        return "No skill points available"

    # ---- drawing ----
    def _panel(self, size: tuple[int, int]) -> pygame.Surface:
        panel = self._panels.get(size)
        if panel is None:
            panel = cut_panel(*size)
            self._panels[size] = panel
        return panel

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        columns = self._columns(ctx)
        self._clamp(columns)
        left = pygame.Rect(area.x, area.y, 290, area.height)
        right = pygame.Rect(area.right - 330, area.y, 330, area.height)
        center = pygame.Rect(left.right + 12, area.y, right.x - left.right - 24, area.height)
        self._draw_character(surface, left, ctx)
        self._draw_tree(surface, center, ctx, columns)
        self._draw_details(surface, right, ctx)

    def _draw_character(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        heading, small = get_font(ctx.assets, 24), get_font(ctx.assets, 15)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(heading.render("SURVIVOR", True, theme.TEXT), (rect.x + 18, rect.y + 14))
        surface.blit(small.render(f"Level {ctx.progression.level}", True, theme.MUTED), (rect.x + 18, rect.y + 46))
        draw_portrait(surface, ctx.assets, pygame.Rect(rect.x + 70, rect.y + 80, 150, 150))

        stats, armor = ctx.player.stats, ctx.player.armor
        rows = (("heart", "HEALTH", f"{stats.max_health}", theme.RED),
                ("bolt", "STAMINA", f"{stats.max_stamina:.0f}", theme.STAMINA),
                ("diamond", "ARMOR", f"{armor}  ({damage_reduction(armor):.0%})", theme.CYAN_BRIGHT))
        y = rect.y + 262
        for icon, label, value, color in rows:
            draw_hud_icon(surface, icon, (rect.x + 30, y + 9), color, 18)
            surface.blit(small.render(label, True, theme.TEXT), (rect.x + 52, y))
            text = small.render(value, True, theme.TEXT)
            surface.blit(text, text.get_rect(topright=(rect.right - 18, y)))
            y += 34

        badge = pygame.Rect(rect.x + 18, rect.bottom - 70, rect.width - 36, 48)
        pygame.draw.rect(surface, (44, 30, 8), badge)
        pygame.draw.rect(surface, theme.AMBER, badge, 2)
        text = heading.render(f"SKILL POINTS   {ctx.progression.skill_points}", True, theme.AMBER)
        surface.blit(text, text.get_rect(center=badge.center))

    def _draw_tree(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext,
                   columns: list[list[str]]) -> None:
        title, small, tiny = get_font(ctx.assets, 18), get_font(ctx.assets, 15), get_font(ctx.assets, 13)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(title.render("SKILL TREE", True, theme.TEXT), (rect.x + 16, rect.y + 12))
        self.card_rects = []
        for col, category in enumerate(CATEGORIES):
            x = rect.x + 16 + col * COLUMN_STEP
            color = CATEGORY_COLORS[category]
            surface.blit(small.render(category.upper(), True, color), (x, rect.y + 50))
            pygame.draw.line(surface, color, (x, rect.y + 74), (x + CARD_W, rect.y + 74), 2)
            for row, skill_id in enumerate(columns[col]):
                skill = ctx.skills.definitions[skill_id]
                card = pygame.Rect(x, rect.y + 86 + row * ROW_STEP, CARD_W, CARD_H)
                self.card_rects.append((card, col, row))
                chosen = col == self.col and row == self.row
                rank = ctx.skills.rank(skill_id)
                pygame.draw.rect(surface, (10, 18, 30), card)
                pygame.draw.rect(surface, theme.AMBER if chosen else theme.BORDER, card, 3 if chosen else 1)
                draw_skill_icon(surface, skill.stat, (card.x + 30, card.y + 34), color, 30)
                surface.blit(small.render(fit_text(skill.name, 14), True, theme.TEXT), (card.x + 58, card.y + 16))
                surface.blit(tiny.render(f"{rank} / {skill.max_rank}", True, theme.MUTED), (card.x + 58, card.y + 40))
                maxed = ctx.skills.is_maxed(skill_id)
                draw_bar(surface, pygame.Rect(card.x + 12, card.y + 84, CARD_W - 24, 8),
                         rank / skill.max_rank, theme.GREEN if maxed else theme.CYAN)
        note = tiny.render("Earn skill points by levelling up and completing missions.", True, theme.MUTED)
        surface.blit(note, (rect.x + 16, rect.bottom - 30))

    def _draw_details(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, heading = get_font(ctx.assets, 18), get_font(ctx.assets, 24)
        small, tiny = get_font(ctx.assets, 15), get_font(ctx.assets, 13)
        surface.blit(self._panel(rect.size), rect.topleft)
        self.button_rect = pygame.Rect(rect.x + 20, rect.bottom - 64, rect.width - 40, 44)
        skill = self.selected_skill(ctx)
        if skill is None:
            draw_button(surface, self.button_rect, "UPGRADE", title, enabled=False)
            return

        color = CATEGORY_COLORS[skill.category]
        rank = ctx.skills.rank(skill.id)
        draw_skill_icon(surface, skill.stat, (rect.x + 38, rect.y + 40), color, 36)
        surface.blit(heading.render(fit_text(skill.name, 16), True, theme.TEXT), (rect.x + 70, rect.y + 20))
        surface.blit(tiny.render(f"{skill.category.upper()} SKILL", True, color), (rect.x + 70, rect.y + 50))
        y = rect.y + 84
        for line in wrap_text(skill.description, small, rect.width - 40)[:3]:
            surface.blit(small.render(line, True, theme.TEXT), (rect.x + 20, y))
            y += 22

        y += 10
        surface.blit(tiny.render("CURRENT LEVEL", True, theme.MUTED), (rect.x + 20, y))
        surface.blit(heading.render(f"{rank} / {skill.max_rank}", True, theme.TEXT), (rect.x + 20, y + 16))
        surface.blit(small.render(format_skill_effect(skill, rank), True, settings_green()), (rect.x + 20, y + 48))
        y += 82
        if rank < skill.max_rank:
            surface.blit(tiny.render(f"NEXT LEVEL  {rank + 1} / {skill.max_rank}", True, theme.MUTED), (rect.x + 20, y))
            surface.blit(small.render(format_skill_effect(skill, rank + 1), True, theme.CYAN_BRIGHT),
                         (rect.x + 20, y + 18))
        else:
            surface.blit(small.render("MAX RANK REACHED", True, settings_green()), (rect.x + 20, y))

        y = rect.bottom - 128
        surface.blit(tiny.render("REQUIREMENTS", True, theme.MUTED), (rect.x + 20, y))
        points = ctx.progression.skill_points
        met = points >= 1 or rank >= skill.max_rank
        surface.blit(small.render("Skill Points", True, theme.TEXT), (rect.x + 20, y + 20))
        count = small.render(f"{points} / 1", True, theme.GREEN if met else theme.RED)
        surface.blit(count, count.get_rect(topright=(rect.right - 20, y + 20)))

        maxed = rank >= skill.max_rank
        enabled = points > 0 and not maxed
        draw_button(surface, self.button_rect, "MAX RANK" if maxed else "UPGRADE", title, enabled=enabled)


def settings_green() -> tuple[int, int, int]:
    from src.core import settings
    return settings.COLOR_SAFE