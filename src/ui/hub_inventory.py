"""Hub page: the inventory, laid out like the design (character, item grid, details)."""
from __future__ import annotations

import pygame

from src.combat.armor import damage_reduction
from src.combat.attachments import attach, attachment_bonus_lines
from src.core import settings
from src.player.equipment import SLOTS, bonus_lines
from src.ui import theme
from src.ui.hub import HubContext, HubPage
from src.ui.hub_widgets import (
    FILTER_NAMES, ITEM_FILTERS, SORT_MODES, draw_button, filter_items, get_font,
    move_in_grid, sort_items,
)
from src.ui.kit import cut_panel, draw_item_icon, fit_text
from src.ui.widgets import wrap_text

SLOT_NAMES = {"head": "HEAD", "face": "FACE", "body": "BODY", "backpack": "BACKPACK",
              "accessory": "ACCESSORY"}
COLUMNS, CELL, GAP, VISIBLE_ROWS = 5, 84, 8, 4


class InventoryPage(HubPage):
    def __init__(self) -> None:
        self.filter_index = 0
        self.sort_index = 0
        self.selected = 0
        self.scroll = 0
        self.focus = "grid"                  # "grid" or "equipment"
        self.slot_selected = 0
        self.cell_rects: list[tuple[pygame.Rect, int]] = []      # recorded while drawing, for the mouse
        self.filter_rects: list[tuple[pygame.Rect, int]] = []
        self.slot_rects: list[tuple[pygame.Rect, int]] = []
        self.button_rect = pygame.Rect(0, 0, 0, 0)
        self._panels: dict[tuple[int, int], pygame.Surface] = {}

    def hints(self) -> list[tuple[str, str]]:
        return [("W/A/S/D", "MOVE"), ("ENTER", "USE / EQUIP"), ("Q/E", "FILTER"), ("R", "SORT")]

    # ---- data ----
    def items(self, ctx: HubContext) -> list[tuple[str, int]]:
        shown = filter_items(ctx.inventory.items(), ctx.inventory.definitions,
                             ITEM_FILTERS[self.filter_index])
        return sort_items(shown, ctx.inventory.definitions, SORT_MODES[self.sort_index])

    def _clamp(self, ctx: HubContext) -> None:
        count = len(self.items(ctx))
        self.selected = max(0, min(self.selected, count - 1)) if count else 0

    def _set_filter(self, index: int) -> None:
        self.filter_index = index % len(ITEM_FILTERS)
        self.selected = 0
        self.scroll = 0

    # ---- input ----
    def handle_event(self, event: pygame.event.Event, ctx: HubContext) -> str | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._click(event.pos, ctx)
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        if key == pygame.K_q:
            self._set_filter(self.filter_index - 1)
            return None
        if key == pygame.K_e:
            self._set_filter(self.filter_index + 1)
            return None
        if key == pygame.K_r:
            self.sort_index = (self.sort_index + 1) % len(SORT_MODES)
            return None
        if self.focus == "equipment":
            return self._equipment_key(key, ctx)
        return self._grid_key(key, ctx)

    def _grid_key(self, key: int, ctx: HubContext) -> str | None:
        directions = {pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0),
                      pygame.K_d: (1, 0), pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
                      pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1)}
        if key in directions:
            dx, dy = directions[key]
            if dx < 0 and self.selected % COLUMNS == 0:         # off the left edge: the equipment slots
                self.focus = "equipment"
                return None
            self.selected = move_in_grid(self.selected, dx, dy, len(self.items(ctx)), COLUMNS)
            return None
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._activate(ctx)
        return None

    def _equipment_key(self, key: int, ctx: HubContext) -> str | None:
        if key in (pygame.K_UP, pygame.K_w):
            self.slot_selected = max(0, self.slot_selected - 1)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.slot_selected = min(len(SLOTS) - 1, self.slot_selected + 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self.focus = "grid"
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return ctx.equipment.unequip(SLOTS[self.slot_selected], ctx.inventory,
                                         ctx.base_capacity()).message
        return None

    def _click(self, pos: tuple[int, int], ctx: HubContext) -> str | None:
        for rect, index in self.filter_rects:
            if rect.collidepoint(pos):
                self._set_filter(index)
                return None
        for rect, index in self.slot_rects:
            if rect.collidepoint(pos):
                self.focus, self.slot_selected = "equipment", index
                return None
        for rect, index in self.cell_rects:
            if rect.collidepoint(pos):
                if index < len(self.items(ctx)):
                    self.focus, self.selected = "grid", index
                return None
        if self.button_rect.collidepoint(pos):
            self.focus = "grid"
            return self._activate(ctx)
        return None

    def _activate(self, ctx: HubContext) -> str | None:
        """Use, equip or attach the selected item."""
        items = self.items(ctx)
        if not items:
            return None
        item_id, _quantity = items[min(self.selected, len(items) - 1)]
        definition = ctx.inventory.definitions[item_id]
        if definition.type == "equipment":
            return ctx.equipment.equip(item_id, ctx.inventory, ctx.base_capacity()).message
        if definition.type == "attachment":
            return attach(ctx.player.weapon, item_id, ctx.inventory, ctx.attachment_defs).message
        if ctx.player.use_item(item_id):
            return f"Used {definition.name}"
        if definition.type == "consumable":
            return "Health is already full"
        if definition.type == "throwable":
            return "Throw it with G"
        return None

    # ---- drawing ----
    def _panel(self, size: tuple[int, int]) -> pygame.Surface:
        panel = self._panels.get(size)
        if panel is None:
            panel = cut_panel(*size)
            self._panels[size] = panel
        return panel

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        self._clamp(ctx)
        left = pygame.Rect(area.x, area.y, 290, area.height)
        center = pygame.Rect(left.right + 12, area.y, 480, area.height)
        right = pygame.Rect(center.right + 12, area.y, area.right - center.right - 12, area.height)
        self._draw_character(surface, left, ctx)
        self._draw_grid(surface, center, ctx)
        self._draw_details(surface, right, ctx)

    def _draw_character(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, small, tiny = get_font(ctx.assets, 18), get_font(ctx.assets, 15), get_font(ctx.assets, 13)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(title.render("CHARACTER", True, theme.TEXT), (rect.x + 16, rect.y + 12))

        self.slot_rects = []
        for index, slot in enumerate(SLOTS):
            cell = pygame.Rect(rect.x + 16, rect.y + 44 + index * 62, 54, 54)
            self.slot_rects.append((cell, index))
            focused = self.focus == "equipment" and index == self.slot_selected
            pygame.draw.rect(surface, (10, 18, 30), cell)
            pygame.draw.rect(surface, theme.AMBER if focused else theme.BORDER, cell, 3 if focused else 1)
            surface.blit(tiny.render(SLOT_NAMES[slot], True, theme.MUTED), (cell.right + 10, cell.y + 4))
            item_id = ctx.equipment.item_in(slot)
            if item_id is not None:
                definition = ctx.inventory.definitions[item_id]
                draw_item_icon(surface, ctx.assets, item_id, definition.type, cell.inflate(-10, -10))
                name, color = definition.name, settings.RARITY_COLORS[definition.rarity]
                detail = ", ".join(bonus_lines(ctx.equipment.definitions[item_id].stats()))
                surface.blit(tiny.render(fit_text(detail, 26), True, theme.CYAN_BRIGHT),
                             (cell.right + 10, cell.y + 34))
            else:
                name, color = "- empty -", theme.DISABLED
            surface.blit(small.render(fit_text(name, 20), True, color), (cell.right + 10, cell.y + 17))

        y = rect.y + 44 + len(SLOTS) * 62 + 4
        stats, armor = ctx.player.stats, ctx.player.armor
        rows = (("HEALTH", f"{stats.health} / {stats.max_health}"),
                ("STAMINA", f"{stats.stamina:.0f} / {stats.max_stamina:.0f}"),
                ("ARMOR", f"{armor}  ({damage_reduction(armor):.0%} less damage)"))
        for label, value in rows:
            surface.blit(small.render(label, True, theme.MUTED), (rect.x + 16, y))
            text = small.render(value, True, theme.TEXT)
            surface.blit(text, text.get_rect(topright=(rect.right - 16, y)))
            y += 22

        weapon = ctx.player.weapon
        if weapon is not None:
            y += 8
            pygame.draw.line(surface, theme.BORDER, (rect.x + 16, y), (rect.right - 16, y), 1)
            surface.blit(small.render(weapon.definition.name.upper(), True, theme.AMBER), (rect.x + 16, y + 8))
            surface.blit(tiny.render(f"DAMAGE {weapon.damage}   RANGE {weapon.range:.0f}",
                                     True, theme.TEXT), (rect.x + 16, y + 30))
            surface.blit(tiny.render(f"SPREAD {weapon.spread:.1f}   FIRE {weapon.fire_rate:.1f}/s",
                                     True, theme.TEXT), (rect.x + 16, y + 48))
            fitted = sum(1 for value in weapon.attachments.values() if value)
            surface.blit(tiny.render(f"ATTACHMENTS {fitted} / {len(weapon.attachments)}",
                                     True, theme.MUTED), (rect.x + 16, y + 66))

    def _draw_grid(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, small, tiny = get_font(ctx.assets, 18), get_font(ctx.assets, 15), get_font(ctx.assets, 12)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(title.render("INVENTORY", True, theme.TEXT), (rect.x + 16, rect.y + 12))
        slots = small.render(f"SLOTS {ctx.inventory.slots_used}/{ctx.inventory.capacity}", True, theme.MUTED)
        surface.blit(slots, slots.get_rect(topright=(rect.right - 16, rect.y + 14)))

        self.filter_rects = []
        tab_width = (rect.width - 32) // len(ITEM_FILTERS)
        for index, name in enumerate(ITEM_FILTERS):
            tab = pygame.Rect(rect.x + 16 + index * tab_width, rect.y + 44, tab_width - 4, 28)
            self.filter_rects.append((tab, index))
            active = index == self.filter_index
            pygame.draw.rect(surface, (40, 28, 8) if active else (10, 18, 30), tab)
            pygame.draw.rect(surface, theme.AMBER if active else theme.BORDER, tab, 1)
            label = tiny.render(FILTER_NAMES[name], True, theme.AMBER if active else theme.MUTED)
            surface.blit(label, label.get_rect(center=tab.center))

        items = self.items(ctx)
        row = self.selected // COLUMNS                           # keep the selected row in view
        if row < self.scroll:
            self.scroll = row
        if row >= self.scroll + VISIBLE_ROWS:
            self.scroll = row - VISIBLE_ROWS + 1
        self.cell_rects = []
        origin_x, origin_y = rect.x + 14, rect.y + 84
        for r in range(VISIBLE_ROWS):
            for c in range(COLUMNS):
                index = (self.scroll + r) * COLUMNS + c
                cell = pygame.Rect(origin_x + c * (CELL + GAP), origin_y + r * (CELL + GAP), CELL, CELL)
                self.cell_rects.append((cell, index))
                chosen = self.focus == "grid" and index == self.selected and index < len(items)
                pygame.draw.rect(surface, (10, 18, 30), cell)
                pygame.draw.rect(surface, theme.AMBER if chosen else theme.BORDER, cell, 3 if chosen else 1)
                if index < len(items):
                    item_id, quantity = items[index]
                    definition = ctx.inventory.definitions[item_id]
                    draw_item_icon(surface, ctx.assets, item_id, definition.type, cell.inflate(-28, -28))
                    pygame.draw.rect(surface, settings.RARITY_COLORS[definition.rarity],
                                     (cell.x + 1, cell.bottom - 4, cell.width - 2, 3))
                    if quantity > 1:
                        text = small.render(str(quantity), True, theme.TEXT)
                        surface.blit(text, text.get_rect(bottomright=(cell.right - 6, cell.bottom - 8)))

        y = origin_y + VISIBLE_ROWS * (CELL + GAP) + 8
        surface.blit(small.render("QUICK SLOTS", True, theme.MUTED), (origin_x, y))
        for index, (definition, key) in enumerate(self._quick_slots(ctx)):
            cell = pygame.Rect(origin_x + index * 78, y + 24, 70, 70)
            count = ctx.inventory.count(definition.id)
            pygame.draw.rect(surface, (10, 18, 30), cell)
            pygame.draw.rect(surface, theme.BORDER, cell, 1)
            draw_item_icon(surface, ctx.assets, definition.id, definition.type, cell.inflate(-22, -22))
            if count == 0:
                dim = pygame.Surface(cell.size, pygame.SRCALPHA)
                dim.fill((0, 0, 0, 140))
                surface.blit(dim, cell.topleft)
            surface.blit(tiny.render(key, True, theme.CYAN_BRIGHT), (cell.x + 6, cell.y + 4))
            text = small.render(str(count), True, theme.TEXT if count else theme.MUTED)
            surface.blit(text, text.get_rect(bottomright=(cell.right - 6, cell.bottom - 4)))

    @staticmethod
    def _quick_slots(ctx: HubContext) -> list:
        healing = sorted((d for d in ctx.item_defs.values() if d.type == "consumable" and d.heal > 0),
                         key=lambda d: d.heal)
        throwables = [d for d in ctx.item_defs.values() if d.type == "throwable"]
        return ([(d, "Q") for d in healing] + [(d, "G") for d in throwables])[:5]

    def _draw_details(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, heading = get_font(ctx.assets, 18), get_font(ctx.assets, 26)
        small, big = get_font(ctx.assets, 15), get_font(ctx.assets, 32)
        surface.blit(self._panel(rect.size), rect.topleft)
        surface.blit(title.render("DETAILS", True, theme.TEXT), (rect.x + 16, rect.y + 12))
        self.button_rect = pygame.Rect(rect.x + 20, rect.bottom - 64, rect.width - 40, 44)

        items = self.items(ctx)
        if not items:
            surface.blit(small.render("Nothing here. Search crates and zombies for supplies.", True,
                                      theme.MUTED), (rect.x + 20, rect.y + 56))
            draw_button(surface, self.button_rect, "NO ACTION", title, enabled=False)
            return
        item_id, quantity = items[min(self.selected, len(items) - 1)]
        definition = ctx.inventory.definitions[item_id]
        color = settings.RARITY_COLORS[definition.rarity]
        surface.blit(heading.render(fit_text(definition.name, 22), True, color), (rect.x + 20, rect.y + 40))
        surface.blit(small.render(f"{definition.type.upper()}  |  {definition.rarity.upper()}", True,
                                  theme.MUTED), (rect.x + 20, rect.y + 72))

        icon_cell = pygame.Rect(rect.x + 20, rect.y + 100, 104, 104)
        pygame.draw.rect(surface, (10, 18, 30), icon_cell)
        pygame.draw.rect(surface, color, icon_cell, 2)
        draw_item_icon(surface, ctx.assets, item_id, definition.type, icon_cell.inflate(-24, -24))
        surface.blit(big.render(f"x{quantity}", True, theme.TEXT), (rect.x + 144, rect.y + 116))

        y = rect.y + 222
        for line in wrap_text(definition.description, small, rect.width - 40)[:4]:
            surface.blit(small.render(line, True, theme.TEXT), (rect.x + 20, y))
            y += 22
        y += 8
        for line in self._effect_lines(ctx, item_id):
            surface.blit(small.render(line, True, settings.COLOR_SAFE), (rect.x + 20, y))
            y += 22

        label, enabled = self._action(definition)
        draw_button(surface, self.button_rect, label, title, enabled=enabled)

    @staticmethod
    def _action(definition) -> tuple[str, bool]:
        if definition.type == "equipment":
            return "EQUIP", True
        if definition.type == "attachment":
            return "ATTACH TO WEAPON", True
        if definition.type == "consumable":
            return "USE", True
        if definition.type == "throwable":
            return "THROW WITH G", False
        return "NO ACTION", False

    @staticmethod
    def _effect_lines(ctx: HubContext, item_id: str) -> list[str]:
        definition = ctx.inventory.definitions[item_id]
        lines: list[str] = []
        if definition.heal:
            lines.append(f"Restores {definition.heal} HP")
        if definition.type == "equipment":
            piece = ctx.equipment.definitions.get(item_id)
            if piece is not None:
                lines.append(f"{SLOT_NAMES[piece.slot]}: " + ", ".join(bonus_lines(piece.stats())))
        elif definition.type == "attachment":
            part = ctx.attachment_defs.get(item_id)
            if part is not None:
                lines.append(f"{part.slot.upper()}: " + ", ".join(attachment_bonus_lines(part)))
        elif definition.type == "throwable":
            lines.append("Thrown with G. It hurts you too if you are close.")
        elif definition.type == "ammo":
            weapon = ctx.player.weapon
            if weapon is not None and weapon.ammo_item_id == item_id:
                lines.append(f"Ammunition for the {weapon.definition.name}")
        return lines