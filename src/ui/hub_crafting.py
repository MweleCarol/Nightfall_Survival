"""Hub page: crafting, weapon upgrades and weapon attachments (workbench and weapon station)."""
from __future__ import annotations

from typing import Callable

import pygame

from src.combat.attachments import attachment_bonus_lines, detach
from src.combat.weapon import ATTACHMENT_SLOTS
from src.core import settings
from src.player.equipment import bonus_lines
from src.ui import theme
from src.ui.hub import HubContext, HubPage
from src.ui.hub_widgets import draw_button, get_font
from src.ui.kit import cut_panel, draw_item_icon, fit_text
from src.ui.widgets import wrap_text

CATEGORIES = ("all", "supplies", "gear", "attachments", "weapon")
CATEGORY_NAMES = {"all": "ALL", "supplies": "SUPPLIES", "gear": "GEAR",
                  "attachments": "ATTACHMENTS", "weapon": "WEAPON"}
SLOT_NAMES = {"optic": "OPTIC", "muzzle": "MUZZLE", "grip": "GRIP"}
VISIBLE_ROWS, ROW_H, MAX_QUANTITY = 10, 44, 9
NEEDS_BENCH = "Crafting needs the safehouse workbench"


# ---------------------------------------------------------------- pure logic
def recipe_category(recipe, item_defs: dict) -> str:
    """Which category a recipe belongs to, from the type of item it makes."""
    kind = item_defs[recipe.output_item].type
    if kind == "equipment":
        return "gear"
    if kind == "attachment":
        return "attachments"
    return "supplies"


def max_craftable(cost: dict[str, int], count: Callable[[str], int],
                  limit: int = MAX_QUANTITY) -> int:
    """How many times a recipe can be made with what is in the pack (capped at `limit`)."""
    if not cost:
        return 0
    return min(limit, min(count(item_id) // quantity for item_id, quantity in cost.items()))


class CraftingPage(HubPage):
    def __init__(self) -> None:
        self.category = 0
        self.selected = 0
        self.scroll = 0
        self.quantity = 1
        self.category_rects: list[tuple[pygame.Rect, int]] = []
        self.row_rects: list[tuple[pygame.Rect, int]] = []
        self.button_rect = pygame.Rect(0, 0, 0, 0)
        self._panels: dict[tuple[int, int], pygame.Surface] = {}

    def hints(self) -> list[tuple[str, str]]:
        return [("A/D", "CATEGORY"), ("W/S", "SELECT"), ("Q/E", "QUANTITY"), ("ENTER", "CRAFT")]

    # ---- data ----
    def set_category(self, name: str) -> None:
        self._go(CATEGORIES.index(name) if name in CATEGORIES else 0)

    def _go(self, index: int) -> None:
        self.category = index % len(CATEGORIES)
        self.selected = self.scroll = 0
        self.quantity = 1

    def entries(self, ctx: HubContext) -> list[tuple[str, object]]:
        """Rows of the current category as (kind, thing): recipe, slot or upgrade."""
        if ctx.crafting is None:
            return []
        data = ctx.crafting.data
        name = CATEGORIES[self.category]
        if name == "weapon":
            return ([("slot", slot) for slot in ATTACHMENT_SLOTS]
                    + [("upgrade", upgrade) for upgrade in data.upgrades.values()])
        return [("recipe", recipe) for recipe in data.recipes.values()
                if name == "all" or recipe_category(recipe, ctx.item_defs) == name]

    def selected_entry(self, ctx: HubContext):
        entries = self.entries(ctx)
        if not entries:
            return None
        return entries[max(0, min(self.selected, len(entries) - 1))]

    @staticmethod
    def _limit(ctx: HubContext, entry) -> int:
        kind, ref = entry
        if kind != "recipe":
            return 1
        return max(1, max_craftable(ref.cost, ctx.inventory.count))

    def _clamp(self, ctx: HubContext) -> None:
        count = len(self.entries(ctx))
        self.selected = max(0, min(self.selected, count - 1)) if count else 0
        entry = self.selected_entry(ctx)
        self.quantity = max(1, min(self.quantity, self._limit(ctx, entry))) if entry else 1

    def on_open(self, ctx: HubContext) -> None:
        self._clamp(ctx)

    # ---- input ----
    def handle_event(self, event: pygame.event.Event, ctx: HubContext) -> str | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._click(event.pos, ctx)
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        count = len(self.entries(ctx))
        if key in (pygame.K_LEFT, pygame.K_a):
            self._go(self.category - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._go(self.category + 1)
        elif key in (pygame.K_UP, pygame.K_w):
            self.selected, self.quantity = max(0, self.selected - 1), 1
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected, self.quantity = min(max(0, count - 1), self.selected + 1), 1
        elif key == pygame.K_q:
            self.quantity = max(1, self.quantity - 1)
        elif key == pygame.K_e:
            entry = self.selected_entry(ctx)
            if entry is not None:
                self.quantity = min(self._limit(ctx, entry), self.quantity + 1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._activate(ctx)
        self._clamp(ctx)
        return None

    def _click(self, pos: tuple[int, int], ctx: HubContext) -> str | None:
        for rect, index in self.category_rects:
            if rect.collidepoint(pos):
                self._go(index)
                return None
        for rect, index in self.row_rects:
            if rect.collidepoint(pos):
                if index < len(self.entries(ctx)):
                    self.selected, self.quantity = index, 1
                return None
        if self.button_rect.collidepoint(pos):
            return self._activate(ctx)
        return None

    def _activate(self, ctx: HubContext) -> str | None:
        entry = self.selected_entry(ctx)
        if entry is None:
            return None
        kind, ref = entry
        if kind == "slot":                                   # taking a part off works anywhere
            return detach(ctx.player.weapon, ref, ctx.inventory, ctx.attachment_defs).message
        if not ctx.can_craft:
            return NEEDS_BENCH
        if kind == "upgrade":
            message = ctx.crafting.upgrade_weapon(ref.id, ctx.player.weapon).message
        else:
            message = self._craft(ctx, ref)
        self._clamp(ctx)
        return message

    def _craft(self, ctx: HubContext, recipe) -> str:
        free = ctx.skills.bonus("free_craft_chance") if ctx.skills is not None else 0.0
        made, message = 0, ""
        for _ in range(self.quantity):
            result = ctx.crafting.craft(recipe.id, free)
            if not result.success:
                if made == 0:
                    return result.message
                break
            made, message = made + 1, result.message
        if made == 1:
            return message
        name = ctx.item_defs[recipe.output_item].name
        return f"Crafted {name} x{made * recipe.output_quantity}"

    # ---- drawing ----
    def _panel(self, size: tuple[int, int]) -> pygame.Surface:
        panel = self._panels.get(size)
        if panel is None:
            panel = cut_panel(*size)
            self._panels[size] = panel
        return panel

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        self._clamp(ctx)
        left = pygame.Rect(area.x, area.y, 230, area.height)
        center = pygame.Rect(left.right + 12, area.y, 480, area.height)
        right = pygame.Rect(center.right + 12, area.y, area.right - center.right - 12, area.height)
        self._draw_categories(surface, left, ctx)
        self._draw_list(surface, center, ctx)
        self._draw_details(surface, right, ctx)

    def _draw_categories(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, small = get_font(ctx.assets, 18), get_font(ctx.assets, 15)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(title.render("CATEGORIES", True, theme.TEXT), (rect.x + 16, rect.y + 12))
        self.category_rects = []
        for index, name in enumerate(CATEGORIES):
            row = pygame.Rect(rect.x + 12, rect.y + 44 + index * 40, rect.width - 24, 34)
            self.category_rects.append((row, index))
            active = index == self.category
            pygame.draw.rect(surface, (40, 28, 8) if active else (10, 18, 30), row)
            pygame.draw.rect(surface, theme.AMBER if active else theme.BORDER, row, 2 if active else 1)
            label = small.render(CATEGORY_NAMES[name], True, theme.AMBER if active else theme.TEXT)
            surface.blit(label, (row.x + 12, row.centery - label.get_height() // 2))

        y = rect.y + 44 + len(CATEGORIES) * 40 + 14
        surface.blit(title.render("MATERIALS", True, theme.TEXT), (rect.x + 16, y))
        y += 30
        for definition in sorted((d for d in ctx.item_defs.values() if d.type == "resource"),
                                 key=lambda d: d.name):
            surface.blit(small.render(definition.name, True, theme.MUTED), (rect.x + 16, y))
            count = small.render(str(ctx.inventory.count(definition.id)), True, theme.TEXT)
            surface.blit(count, count.get_rect(topright=(rect.right - 16, y)))
            y += 24

    def _draw_list(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, small = get_font(ctx.assets, 18), get_font(ctx.assets, 15)
        surface.blit(self._panel(rect.size), rect.topleft)
        entries = self.entries(ctx)
        surface.blit(title.render(CATEGORY_NAMES[CATEGORIES[self.category]], True, theme.TEXT),
                     (rect.x + 16, rect.y + 12))
        count = small.render(f"{len(entries)} ENTRIES", True, theme.MUTED)
        surface.blit(count, count.get_rect(topright=(rect.right - 16, rect.y + 14)))

        row_index = max(0, min(self.selected, len(entries) - 1)) if entries else 0
        if row_index < self.scroll:
            self.scroll = row_index
        if row_index >= self.scroll + VISIBLE_ROWS:
            self.scroll = row_index - VISIBLE_ROWS + 1
        self.row_rects = []
        for slot in range(VISIBLE_ROWS):
            index = self.scroll + slot
            row = pygame.Rect(rect.x + 12, rect.y + 48 + slot * ROW_H, rect.width - 24, ROW_H - 4)
            self.row_rects.append((row, index))
            if index >= len(entries):
                continue
            chosen = index == self.selected
            pygame.draw.rect(surface, (30, 44, 70) if chosen else (10, 18, 30), row)
            pygame.draw.rect(surface, theme.AMBER if chosen else theme.BORDER, row, 2 if chosen else 1)
            self._draw_row(surface, row, entries[index], ctx, title, small)

        if CATEGORIES[self.category] == "weapon" and ctx.player.weapon is not None:
            w = ctx.player.weapon
            lines = (f"DAMAGE {w.damage}   RANGE {w.range:.0f}   SPREAD {w.spread:.1f}   FIRE {w.fire_rate:.1f}/s",
                     f"MAGAZINE {w.magazine_size}   RELOAD {w.reload_time:.2f}s   RECOIL x{w.recoil:.2f}")
            for number, line in enumerate(lines):
                surface.blit(small.render(line, True, theme.MUTED),
                             (rect.x + 16, rect.bottom - 50 + number * 22))

    def _draw_row(self, surface, row, entry, ctx, title, small) -> None:
        kind, ref = entry
        if kind == "recipe":
            definition = ctx.item_defs[ref.output_item]
            draw_item_icon(surface, ctx.assets, ref.output_item, definition.type,
                           pygame.Rect(row.x + 6, row.y + 4, 32, 32))
            surface.blit(title.render(fit_text(ref.name, 26), True, theme.TEXT), (row.x + 48, row.y + 9))
            ok = ctx.crafting.has_materials(ref.cost)
            pygame.draw.circle(surface, theme.GREEN if ok else theme.RED, (row.right - 18, row.centery), 6,
                               0 if ok else 2)
        elif kind == "slot":
            surface.blit(small.render(SLOT_NAMES[ref], True, theme.MUTED), (row.x + 12, row.y + 12))
            item_id = ctx.player.weapon.attachments[ref]
            if item_id is None:
                surface.blit(small.render("- empty -", True, theme.DISABLED), (row.x + 110, row.y + 12))
            else:
                definition = ctx.inventory.definitions[item_id]
                surface.blit(small.render(definition.name, True, settings.RARITY_COLORS[definition.rarity]),
                             (row.x + 110, row.y + 12))
        else:
            surface.blit(title.render(fit_text(ref.name, 24), True, theme.TEXT), (row.x + 12, row.y + 9))
            level = ctx.player.weapon.upgrade_levels.get(ref.id, 0)
            tag = small.render(f"Lv {level}/{ref.max_level}", True, theme.AMBER)
            surface.blit(tag, tag.get_rect(topright=(row.right - 12, row.y + 12)))

    def _draw_details(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, heading = get_font(ctx.assets, 18), get_font(ctx.assets, 24)
        small = get_font(ctx.assets, 15)
        surface.blit(self._panel(rect.size), rect.topleft)
        self.button_rect = pygame.Rect(rect.x + 20, rect.bottom - 64, rect.width - 40, 44)
        entry = self.selected_entry(ctx)
        if entry is None:
            draw_button(surface, self.button_rect, "NOTHING TO CRAFT", title, enabled=False)
            return
        kind, ref = entry
        x, y = rect.x + 20, rect.y + 18
        if not ctx.can_craft and kind != "slot":
            surface.blit(small.render(NEEDS_BENCH, True, theme.RED), (x, rect.bottom - 92))

        if kind == "recipe":
            definition = ctx.item_defs[ref.output_item]
            color = settings.RARITY_COLORS[definition.rarity]
            surface.blit(heading.render(fit_text(ref.name, 22), True, theme.TEXT), (x, y))
            icon = pygame.Rect(x, y + 40, 72, 72)
            pygame.draw.rect(surface, (10, 18, 30), icon)
            pygame.draw.rect(surface, color, icon, 2)
            draw_item_icon(surface, ctx.assets, ref.output_item, definition.type, icon.inflate(-16, -16))
            surface.blit(heading.render(f"x{ref.output_quantity}", True, theme.TEXT), (x + 88, y + 52))
            ty = y + 124
            for line in wrap_text(ref.description, small, rect.width - 40)[:3]:
                surface.blit(small.render(line, True, theme.TEXT), (x, ty))
                ty += 22
            for line in self._output_lines(ctx, ref.output_item):
                surface.blit(small.render(line, True, settings.COLOR_SAFE), (x, ty))
                ty += 22
            self._draw_cost(surface, x, ty + 10, "REQUIREMENTS", ref.cost, ctx, small)
            qy = rect.bottom - 136
            surface.blit(small.render("QUANTITY", True, theme.MUTED), (x, qy))
            surface.blit(heading.render(f"-  {self.quantity}  +", True, theme.AMBER), (x + 110, qy - 4))
            chance = ctx.skills.bonus("free_craft_chance") if ctx.skills is not None else 0.0
            if chance > 0:
                surface.blit(small.render(f"Waste Not: {chance:.0%} chance of free", True, settings.COLOR_SAFE),
                             (x, qy + 30))
            can_afford = ctx.crafting.has_materials(ref.cost)
            label = "CRAFT" if self.quantity == 1 else f"CRAFT x{self.quantity}"
            draw_button(surface, self.button_rect, label, title, enabled=can_afford and ctx.can_craft)
        elif kind == "upgrade":
            weapon = ctx.player.weapon
            level = weapon.upgrade_levels.get(ref.id, 0)
            surface.blit(heading.render(fit_text(ref.name, 22), True, theme.TEXT), (x, y))
            surface.blit(small.render(f"LEVEL {level} / {ref.max_level}", True, theme.AMBER), (x, y + 36))
            ty = y + 70
            for line in wrap_text(ref.description, small, rect.width - 40)[:3]:
                surface.blit(small.render(line, True, theme.TEXT), (x, ty))
                ty += 22
            cost = ctx.crafting.next_upgrade_cost(ref.id, weapon)
            if cost is None:
                surface.blit(heading.render("MAX LEVEL", True, settings.COLOR_SAFE), (x, ty + 20))
                draw_button(surface, self.button_rect, "MAX LEVEL", title, enabled=False)
            else:
                self._draw_cost(surface, x, ty + 10, f"LEVEL {level + 1} REQUIRES", cost, ctx, small)
                draw_button(surface, self.button_rect, "UPGRADE", title,
                            enabled=ctx.crafting.has_materials(cost) and ctx.can_craft)
        else:
            item_id = ctx.player.weapon.attachments[ref]
            surface.blit(heading.render(f"{SLOT_NAMES[ref]} SLOT", True, theme.TEXT), (x, y))
            if item_id is None:
                note = "Nothing attached. Select a part in the inventory and press ENTER to fit it."
                for number, line in enumerate(wrap_text(note, small, rect.width - 40)):
                    surface.blit(small.render(line, True, theme.MUTED), (x, y + 44 + number * 22))
                draw_button(surface, self.button_rect, "REMOVE", title, enabled=False)
            else:
                definition = ctx.inventory.definitions[item_id]
                surface.blit(heading.render(definition.name, True, settings.RARITY_COLORS[definition.rarity]),
                             (x, y + 44))
                ty = y + 84
                for line in wrap_text(definition.description, small, rect.width - 40)[:3]:
                    surface.blit(small.render(line, True, theme.TEXT), (x, ty))
                    ty += 22
                for line in attachment_bonus_lines(ctx.attachment_defs[item_id]):
                    surface.blit(small.render(line, True, settings.COLOR_SAFE), (x, ty + 6))
                    ty += 22
                draw_button(surface, self.button_rect, "REMOVE", title, enabled=True)

    @staticmethod
    def _draw_cost(surface, x, y, label, cost, ctx, small) -> None:
        surface.blit(small.render(label, True, theme.MUTED), (x, y))
        for number, (item_id, needed) in enumerate(cost.items()):
            have = ctx.inventory.count(item_id)
            color = settings.COLOR_SAFE if have >= needed else settings.COLOR_ACCENT
            surface.blit(small.render(ctx.inventory.definitions[item_id].name, True, theme.TEXT),
                         (x + 10, y + 24 + number * 24))
            value = small.render(f"{have} / {needed}", True, color)
            surface.blit(value, value.get_rect(topright=(x + 300, y + 24 + number * 24)))

    @staticmethod
    def _output_lines(ctx: HubContext, item_id: str) -> list[str]:
        definition = ctx.item_defs[item_id]
        if definition.heal:
            return [f"Restores {definition.heal} HP"]
        if definition.type == "equipment" and item_id in ctx.equipment.definitions:
            return [", ".join(bonus_lines(ctx.equipment.definitions[item_id].stats()))]
        if definition.type == "attachment" and item_id in ctx.attachment_defs:
            return [", ".join(attachment_bonus_lines(ctx.attachment_defs[item_id]))]
        return []