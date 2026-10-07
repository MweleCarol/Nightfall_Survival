"""Workshop overlay (workbench + weapon station): craft items and upgrade the weapon."""
from __future__ import annotations

import pygame

from src.combat.weapon import Weapon
from src.core import settings
from src.player.inventory import Inventory
from src.systems.crafting import CraftingSystem
from src.systems.skills import SkillSet
from src.ui.widgets import (
    SelectionList, draw_panel, draw_row_highlight, make_dim, wrap_text,
)

TAB_NAMES = {"craft": "CRAFTING", "weapon": "WEAPON UPGRADES"}


class WorkshopUI:
    def __init__(self, crafting: CraftingSystem, inventory: Inventory,
                 weapon: Weapon, skills: SkillSet) -> None:
        self.crafting = crafting
        self.inventory = inventory
        self.weapon = weapon
        self.skills = skills
        self.tab = "craft"
        self.nav = SelectionList()
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    def open_tab(self, tab: str) -> None:
        self.tab = tab
        self.nav.reset()

    def _entries(self) -> list:
        data = self.crafting.data
        return list(data.recipes.values()) if self.tab == "craft" else list(data.upgrades.values())

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN:
            return None
        entries = self._entries()
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.open_tab("craft")
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.open_tab("weapon")
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.nav.move(-1, len(entries))
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.nav.move(1, len(entries))
        elif event.key == pygame.K_RETURN and entries:
            entry = entries[self.nav.selected]
            if self.tab == "craft":
                free_chance = self.skills.bonus("free_craft_chance")
                return self.crafting.craft(entry.id, free_chance).message
            return self.crafting.upgrade_weapon(entry.id, self.weapon).message
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, "WORKSHOP", self.title_font)

        for index, tab in enumerate(("craft", "weapon")):    # tab headers
            active = tab == self.tab
            color = settings.COLOR_AMBER if active else settings.COLOR_MUTED
            label = self.font.render(TAB_NAMES[tab], True, color)
            pos = (panel.x + 300 + index * 220, panel.y + 24)
            surface.blit(label, pos)
            if active:
                pygame.draw.line(surface, color, (pos[0], pos[1] + 30),
                                 (pos[0] + label.get_width(), pos[1] + 30), 3)

        entries = self._entries()
        for index, entry in enumerate(entries):
            row = pygame.Rect(panel.x + 24, panel.y + 80 + index * 40, 400, 34)
            draw_row_highlight(surface, row, index == self.nav.selected)
            surface.blit(self.font.render(entry.name, True, settings.COLOR_TEXT),
                         (row.x + 12, row.y + 5))
            if self.tab == "weapon":
                level = self.weapon.upgrade_levels.get(entry.id, 0)
                text = self.small_font.render(f"Lv {level}/{entry.max_level}", True,
                                              settings.COLOR_AMBER)
                surface.blit(text, text.get_rect(topright=(row.right - 12, row.y + 8)))

        if entries:
            self._draw_details(surface, panel, entries[self.nav.selected])

        stats = (f"{self.weapon.definition.name}:  DAMAGE {self.weapon.damage}   "
                 f"MAGAZINE {self.weapon.magazine_size}   RELOAD {self.weapon.reload_time:.2f}s")
        surface.blit(self.small_font.render(stats, True, settings.COLOR_MUTED),
                     (panel.x + 24, panel.bottom - 70))
        hint = self.small_font.render("A/D switch tab   |   W/S select   |   ENTER confirm   |   E or ESC close",
                                      True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))

    def _draw_details(self, surface: pygame.Surface, panel: pygame.Rect, entry) -> None:
        x, y = panel.x + 460, panel.y + 84
        surface.blit(self.font.render(entry.name, True, settings.COLOR_TEXT), (x, y))
        for line_number, line in enumerate(wrap_text(entry.description, self.small_font, 400)):
            surface.blit(self.small_font.render(line, True, settings.COLOR_MUTED),
                         (x, y + 34 + line_number * 22))
        y += 100

        if self.tab == "craft":
            output = self.inventory.definitions[entry.output_item].name
            surface.blit(self.small_font.render(f"Makes: {output} x{entry.output_quantity}", True,
                         settings.COLOR_TEXT), (x, y))
            self._draw_cost(surface, x, y + 30, "Requires:", entry.cost)
            chance = self.skills.bonus("free_craft_chance")
            if chance > 0:
                surface.blit(self.small_font.render(f"Waste Not: {chance:.0%} chance this is free",
                             True, settings.COLOR_SAFE), (x, y + 190))
        else:
            level = self.weapon.upgrade_levels.get(entry.id, 0)
            cost = self.crafting.next_upgrade_cost(entry.id, self.weapon)
            if cost is None:
                surface.blit(self.font.render("MAX LEVEL", True, settings.COLOR_SAFE), (x, y))
            else:
                self._draw_cost(surface, x, y, f"Level {level + 1} requires:", cost)

    def _draw_cost(self, surface: pygame.Surface, x: int, y: int, title: str,
                   cost: dict[str, int]) -> None:
        surface.blit(self.small_font.render(title, True, settings.COLOR_TEXT), (x, y))
        for line_number, (item_id, needed) in enumerate(cost.items()):
            have = self.inventory.count(item_id)
            color = settings.COLOR_SAFE if have >= needed else settings.COLOR_ACCENT
            name = self.inventory.definitions[item_id].name
            surface.blit(self.small_font.render(f"{name}:  {have} / {needed}", True, color),
                         (x + 12, y + 26 + line_number * 24))