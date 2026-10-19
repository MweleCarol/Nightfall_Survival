"""Workshop overlay: craft items, upgrade the weapon and fit attachments."""
from __future__ import annotations

import pygame

from src.combat.attachments import attach, attachment_bonus_lines, detach
from src.combat.weapon import ATTACHMENT_SLOTS, Weapon
from src.core import settings
from src.player.inventory import Inventory
from src.systems.crafting import CraftingSystem
from src.systems.skills import SkillSet
from src.ui.widgets import SelectionList, draw_panel, draw_row_highlight, make_dim, wrap_text

TABS = ("craft", "weapon", "attach")
TAB_NAMES = {"craft": "CRAFTING", "weapon": "UPGRADES", "attach": "ATTACHMENTS"}
SLOT_NAMES = {"optic": "OPTIC", "muzzle": "MUZZLE", "grip": "GRIP"}
VISIBLE_ROWS = 9
ROW_HEIGHT = 36


class WorkshopUI:
    def __init__(self, crafting: CraftingSystem, inventory: Inventory, weapon: Weapon,
                 skills: SkillSet, attachment_defs: dict) -> None:
        self.crafting = crafting
        self.inventory = inventory
        self.weapon = weapon
        self.skills = skills
        self.attachment_defs = attachment_defs
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
        if self.tab == "craft":
            return list(data.recipes.values())
        if self.tab == "weapon":
            return list(data.upgrades.values())
        rows: list = [("slot", slot) for slot in ATTACHMENT_SLOTS]      # what is fitted now
        rows += [("pack", item_id) for item_id, _quantity in self.inventory.items()
                 if item_id in self.attachment_defs]                    # what you could fit
        return rows

    # ---- input ----
    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN:
            return None
        entries = self._entries()
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a):
            self.open_tab(TABS[(TABS.index(self.tab) - 1) % len(TABS)])
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.open_tab(TABS[(TABS.index(self.tab) + 1) % len(TABS)])
        elif key in (pygame.K_UP, pygame.K_w):
            self.nav.move(-1, len(entries))
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.nav.move(1, len(entries))
        elif key == pygame.K_RETURN and entries:
            entry = entries[self.nav.selected]
            if self.tab == "craft":
                return self.crafting.craft(entry.id, self.skills.bonus("free_craft_chance")).message
            if self.tab == "weapon":
                return self.crafting.upgrade_weapon(entry.id, self.weapon).message
            kind, ref = entry
            if kind == "slot":
                result = detach(self.weapon, ref, self.inventory, self.attachment_defs)
            else:
                result = attach(self.weapon, ref, self.inventory, self.attachment_defs)
            self.nav.move(0, len(self._entries()))              # keep the selection in range
            return result.message
        return None

    # ---- drawing ----
    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, "WORKSHOP", self.title_font)

        for index, tab in enumerate(TABS):
            active = tab == self.tab
            color = settings.COLOR_AMBER if active else settings.COLOR_MUTED
            label = self.font.render(TAB_NAMES[tab], True, color)
            pos = (panel.x + 270 + index * 150, panel.y + 24)
            surface.blit(label, pos)
            if active:
                pygame.draw.line(surface, color, (pos[0], pos[1] + 30),
                                 (pos[0] + label.get_width(), pos[1] + 30), 3)

        entries = self._entries()
        selected = min(self.nav.selected, max(0, len(entries) - 1))
        first = max(0, selected - (VISIBLE_ROWS - 1))                 # scroll the list window
        for slot_index, index in enumerate(range(first, min(len(entries), first + VISIBLE_ROWS))):
            row = pygame.Rect(panel.x + 24, panel.y + 80 + slot_index * ROW_HEIGHT, 400, ROW_HEIGHT - 4)
            draw_row_highlight(surface, row, index == selected)
            self._draw_row(surface, row, entries[index])
        if entries:
            self._draw_details(surface, panel, entries[selected])

        self._draw_stats(surface, panel)
        hint = self.small_font.render(
            "A/D switch tab   |   W/S select   |   ENTER confirm   |   E or ESC close",
            True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))

    def _draw_row(self, surface: pygame.Surface, row: pygame.Rect, entry) -> None:
        if self.tab == "attach":
            kind, ref = entry
            if kind == "slot":
                item_id = self.weapon.attachments[ref]
                surface.blit(self.small_font.render(SLOT_NAMES[ref], True, settings.COLOR_MUTED),
                             (row.x + 10, row.y + 7))
                if item_id is not None:
                    definition = self.inventory.definitions[item_id]
                    name, color = definition.name, settings.RARITY_COLORS[definition.rarity]
                else:
                    name, color = "- empty -", settings.COLOR_MUTED
                surface.blit(self.small_font.render(name, True, color), (row.x + 110, row.y + 7))
            else:
                definition = self.inventory.definitions[ref]
                surface.blit(self.font.render(definition.name, True,
                             settings.RARITY_COLORS[definition.rarity]), (row.x + 10, row.y + 4))
                tag = self.small_font.render(SLOT_NAMES[self.attachment_defs[ref].slot],
                                             True, settings.COLOR_MUTED)
                surface.blit(tag, tag.get_rect(topright=(row.right - 10, row.y + 7)))
            return
        surface.blit(self.font.render(entry.name, True, settings.COLOR_TEXT), (row.x + 12, row.y + 4))
        if self.tab == "weapon":
            level = self.weapon.upgrade_levels.get(entry.id, 0)
            text = self.small_font.render(f"Lv {level}/{entry.max_level}", True, settings.COLOR_AMBER)
            surface.blit(text, text.get_rect(topright=(row.right - 12, row.y + 8)))

    def _draw_details(self, surface: pygame.Surface, panel: pygame.Rect, entry) -> None:
        x, y = panel.x + 460, panel.y + 84
        if self.tab == "attach":
            self._draw_attach_details(surface, x, y, entry)
            return
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

    def _draw_attach_details(self, surface: pygame.Surface, x: int, y: int, entry) -> None:
        kind, ref = entry
        if kind == "slot":
            item_id = self.weapon.attachments[ref]
            surface.blit(self.font.render(f"{SLOT_NAMES[ref]} SLOT", True, settings.COLOR_TEXT), (x, y))
            if item_id is None:
                note = "Nothing attached. Select an attachment from your pack and press ENTER."
                for line_number, line in enumerate(wrap_text(note, self.small_font, 400)):
                    surface.blit(self.small_font.render(line, True, settings.COLOR_MUTED),
                                 (x, y + 34 + line_number * 22))
                return
            self._draw_attachment_info(surface, x, y + 34, item_id)
            surface.blit(self.small_font.render("ENTER - take off", True, settings.COLOR_AMBER),
                         (x, y + 250))
        else:
            self._draw_attachment_info(surface, x, y, ref)
            surface.blit(self.small_font.render("ENTER - attach", True, settings.COLOR_AMBER),
                         (x, y + 250))

    def _draw_attachment_info(self, surface: pygame.Surface, x: int, y: int, item_id: str) -> None:
        definition = self.inventory.definitions[item_id]
        attachment = self.attachment_defs[item_id]
        surface.blit(self.font.render(definition.name, True,
                     settings.RARITY_COLORS[definition.rarity]), (x, y))
        info = f"{SLOT_NAMES[attachment.slot]}  -  {definition.rarity.upper()}"
        surface.blit(self.small_font.render(info, True, settings.COLOR_MUTED), (x, y + 28))
        line_y = y + 56
        for line in wrap_text(definition.description, self.small_font, 400)[:3]:
            surface.blit(self.small_font.render(line, True, settings.COLOR_TEXT), (x, line_y))
            line_y += 22
        line_y += 6
        for text in attachment_bonus_lines(attachment):
            surface.blit(self.small_font.render(text, True, settings.COLOR_SAFE), (x, line_y))
            line_y += 22
        fits = "any weapon" if "any" in attachment.fits else ", ".join(attachment.fits)
        surface.blit(self.small_font.render(f"Fits: {fits}", True, settings.COLOR_MUTED), (x, line_y + 4))

    def _draw_cost(self, surface: pygame.Surface, x: int, y: int, title: str,
                   cost: dict[str, int]) -> None:
        surface.blit(self.small_font.render(title, True, settings.COLOR_TEXT), (x, y))
        for line_number, (item_id, needed) in enumerate(cost.items()):
            have = self.inventory.count(item_id)
            color = settings.COLOR_SAFE if have >= needed else settings.COLOR_ACCENT
            name = self.inventory.definitions[item_id].name
            surface.blit(self.small_font.render(f"{name}:  {have} / {needed}", True, color),
                         (x + 12, y + 26 + line_number * 24))

    def _draw_stats(self, surface: pygame.Surface, panel: pygame.Rect) -> None:
        w = self.weapon
        line1 = (f"{w.definition.name}   DAMAGE {w.damage}   RANGE {w.range:.0f}   "
                 f"SPREAD {w.spread:.1f}   FIRE RATE {w.fire_rate:.1f}/s")
        line2 = f"MAGAZINE {w.magazine_size}   RELOAD {w.reload_time:.2f}s   RECOIL x{w.recoil:.2f}"
        surface.blit(self.small_font.render(line1, True, settings.COLOR_MUTED), (panel.x + 24, panel.bottom - 76))
        surface.blit(self.small_font.render(line2, True, settings.COLOR_MUTED), (panel.x + 24, panel.bottom - 54))