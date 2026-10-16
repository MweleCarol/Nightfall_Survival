"""Inventory overlay (TAB): items on the left, details and worn equipment on the right."""
from __future__ import annotations

from typing import Callable

import pygame

from src.combat.armor import damage_reduction
from src.core import settings
from src.player.equipment import SLOTS, Equipment, bonus_lines
from src.player.inventory import Inventory
from src.player.player import Player
from src.ui.widgets import draw_panel, draw_row_highlight, make_dim, wrap_text

SLOT_NAMES = {"head": "HEAD", "face": "FACE", "body": "BODY", "backpack": "BACKPACK",
              "accessory": "ACCESSORY"}
VISIBLE_ROWS = 10


class InventoryUI:
    def __init__(self, equipment: Equipment, base_capacity: Callable[[], int]) -> None:
        self.equipment = equipment
        self.base_capacity = base_capacity       # capacity before gear (base + skills)
        self.selected = 0
        self.slot_selected = 0
        self.focus = "items"                     # "items" or "equipment"
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.heading_font = pygame.font.SysFont("arial", 26, bold=True)
        self.font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    # ---- input ----
    def handle_event(self, event: pygame.event.Event, player: Player) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN or player.inventory is None:
            return None
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a):
            self.focus = "items"
            return None
        if key in (pygame.K_RIGHT, pygame.K_d):
            self.focus = "equipment"
            return None
        if self.focus == "equipment":
            return self._equipment_key(key, player)
        return self._items_key(key, player)

    def _items_key(self, key: int, player: Player) -> str | None:
        inventory = player.inventory
        items = inventory.items()
        message = None
        if key in (pygame.K_UP, pygame.K_w):
            self.selected -= 1
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected += 1
        elif key == pygame.K_RETURN and items:
            item_id, _ = items[min(self.selected, len(items) - 1)]
            definition = inventory.definitions[item_id]
            if definition.type == "equipment":
                message = self.equipment.equip(item_id, inventory, self.base_capacity()).message
            elif player.use_item(item_id):
                message = f"Used {definition.name}"
            elif definition.type == "consumable":
                message = "Health is already full"
        self.selected = max(0, min(self.selected, len(inventory.items()) - 1))
        return message

    def _equipment_key(self, key: int, player: Player) -> str | None:
        if key in (pygame.K_UP, pygame.K_w):
            self.slot_selected = max(0, self.slot_selected - 1)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.slot_selected = min(len(SLOTS) - 1, self.slot_selected + 1)
        elif key == pygame.K_RETURN:
            return self.equipment.unequip(SLOTS[self.slot_selected], player.inventory,
                                          self.base_capacity()).message
        return None

    # ---- drawing ----
    def draw(self, surface: pygame.Surface, player: Player) -> None:
        inventory = player.inventory
        if inventory is None:
            return
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, "INVENTORY", self.title_font,
                   f"SLOTS {inventory.slots_used}/{inventory.capacity}", self.font)

        items = inventory.items()
        selected = min(self.selected, len(items) - 1) if items else 0
        self._draw_items(surface, panel, inventory, items, selected)
        x, y = panel.x + 460, panel.y + 74
        if items:
            self._draw_details(surface, inventory, items[selected][0], x, y)
        self._draw_equipment(surface, inventory, x, panel.y + 284)

        action = "unequip" if self.focus == "equipment" else "use / equip"
        hint = self.small_font.render(
            f"W/S select   |   ENTER {action}   |   A/D switch list   |   TAB or ESC close",
            True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))

    def _draw_items(self, surface: pygame.Surface, panel: pygame.Rect, inventory: Inventory,
                    items: list[tuple[str, int]], selected: int) -> None:
        if not items:
            surface.blit(self.font.render("Your pack is empty.", True, settings.COLOR_MUTED),
                         (panel.x + 34, panel.y + 90))
        first = max(0, selected - (VISIBLE_ROWS - 1))                  # scroll the list window
        for slot, index in enumerate(range(first, min(len(items), first + VISIBLE_ROWS))):
            item_id, quantity = items[index]
            definition = inventory.definitions[item_id]
            row = pygame.Rect(panel.x + 24, panel.y + 74 + slot * 34, 400, 30)
            draw_row_highlight(surface, row, self.focus == "items" and index == selected)
            name = self.font.render(definition.name, True, settings.RARITY_COLORS[definition.rarity])
            surface.blit(name, (row.x + 10, row.y + 3))
            amount = self.font.render(f"x{quantity}", True, settings.COLOR_TEXT)
            surface.blit(amount, amount.get_rect(topright=(row.right - 10, row.y + 3)))

    def _draw_details(self, surface: pygame.Surface, inventory: Inventory, item_id: str,
                      x: int, y: int) -> None:
        definition = inventory.definitions[item_id]
        surface.blit(self.heading_font.render(definition.name, True,
                     settings.RARITY_COLORS[definition.rarity]), (x, y))
        info = f"{definition.rarity.upper()}  -  {definition.type.upper()}"
        surface.blit(self.small_font.render(info, True, settings.COLOR_MUTED), (x, y + 34))
        line_y = y + 62
        for line in wrap_text(definition.description, self.small_font, 400)[:3]:
            surface.blit(self.small_font.render(line, True, settings.COLOR_TEXT), (x, line_y))
            line_y += 22

        effect, action = None, None
        if definition.heal:
            effect, action = f"Restores {definition.heal} HP", "ENTER - use"
        elif definition.type == "equipment":
            piece = self.equipment.definitions.get(item_id)
            if piece is not None:
                effect = f"{SLOT_NAMES[piece.slot]}:  " + ", ".join(bonus_lines(piece.stats()))
            action = "ENTER - equip"
        elif definition.type == "throwable":
            effect = "Throw it with G"
        if effect:
            surface.blit(self.small_font.render(effect, True, settings.COLOR_SAFE), (x, line_y + 6))
        if action:
            surface.blit(self.small_font.render(action, True, settings.COLOR_AMBER), (x, line_y + 30))

    def _draw_equipment(self, surface: pygame.Surface, inventory: Inventory, x: int, y: int) -> None:
        focused = self.focus == "equipment"
        header = self.font.render("EQUIPMENT", True, settings.COLOR_AMBER if focused else settings.COLOR_MUTED)
        surface.blit(header, (x, y))
        for index, slot in enumerate(SLOTS):
            row = pygame.Rect(x, y + 26 + index * 26, 400, 24)
            draw_row_highlight(surface, row, focused and index == self.slot_selected)
            surface.blit(self.small_font.render(SLOT_NAMES[slot], True, settings.COLOR_MUTED),
                         (row.x + 8, row.y + 2))
            item_id = self.equipment.item_in(slot)
            if item_id is not None:
                definition = inventory.definitions[item_id]
                name, color = definition.name, settings.RARITY_COLORS[definition.rarity]
            else:
                name, color = "- empty -", settings.COLOR_MUTED
            surface.blit(self.small_font.render(name, True, color), (row.x + 120, row.y + 2))

        totals = self.equipment.totals()
        armor = int(totals["armor"])
        summary = f"ARMOR {armor}   ({damage_reduction(armor):.0%} less damage)"
        surface.blit(self.font.render(summary, True, settings.COLOR_TEXT), (x, y + 160))
        extra = bonus_lines({**totals, "armor": 0})
        if extra:
            surface.blit(self.small_font.render(", ".join(extra), True, settings.COLOR_SAFE), (x, y + 184))