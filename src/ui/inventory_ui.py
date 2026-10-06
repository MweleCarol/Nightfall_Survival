"""Inventory overlay (opened with TAB). Keyboard controlled; pauses the game."""
from __future__ import annotations

import pygame

from src.core import settings
from src.player.player import Player


class InventoryUI:
    def __init__(self) -> None:
        self.open = False
        self.selected = 0
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, 170))

    def toggle(self) -> None:
        self.open = not self.open
        self.selected = 0

    def handle_event(self, event: pygame.event.Event, player: Player) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN or player.inventory is None:
            return None
        items = player.inventory.items()
        message = None
        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected -= 1
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected += 1
        elif event.key == pygame.K_RETURN and items:
            item_id, _ = items[self.selected]
            definition = player.inventory.definitions[item_id]
            if player.use_item(item_id):
                message = f"Used {definition.name}"
            elif definition.type == "consumable":
                message = "Health is already full"
        remaining = len(player.inventory.items())
        self.selected = max(0, min(self.selected, remaining - 1))
        return message

    def draw(self, surface: pygame.Surface, player: Player) -> None:
        inventory = player.inventory
        if inventory is None:
            return
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 820, 480)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        pygame.draw.rect(surface, (12, 18, 30), panel)
        pygame.draw.rect(surface, (70, 88, 120), panel, 2)

        surface.blit(self.title_font.render("INVENTORY", True, settings.COLOR_TEXT),
                     (panel.x + 24, panel.y + 16))
        slots = self.font.render(f"SLOTS {inventory.slots_used}/{inventory.capacity}",
                                 True, settings.COLOR_MUTED)
        surface.blit(slots, slots.get_rect(topright=(panel.right - 24, panel.y + 22)))

        items = inventory.items()
        if not items:
            empty = self.font.render("Your pack is empty.", True, settings.COLOR_MUTED)
            surface.blit(empty, (panel.x + 34, panel.y + 90))

        for index, (item_id, quantity) in enumerate(items):
            definition = inventory.definitions[item_id]
            row = pygame.Rect(panel.x + 24, panel.y + 74 + index * 34, 400, 30)
            if index == self.selected:
                pygame.draw.rect(surface, (30, 44, 70), row)
                pygame.draw.rect(surface, settings.COLOR_AMBER, row, 2)
            name = self.font.render(definition.name, True, settings.RARITY_COLORS[definition.rarity])
            surface.blit(name, (row.x + 10, row.y + 3))
            amount = self.font.render(f"x{quantity}", True, settings.COLOR_TEXT)
            surface.blit(amount, amount.get_rect(topright=(row.right - 10, row.y + 3)))

        if items:
            definition = inventory.definitions[items[self.selected][0]]
            x, y = panel.x + 460, panel.y + 80
            surface.blit(self.title_font.render(definition.name, True,
                         settings.RARITY_COLORS[definition.rarity]), (x, y))
            info = f"{definition.rarity.upper()}  -  {definition.type.upper()}  -  STACK {definition.max_stack}"
            surface.blit(self.small_font.render(info, True, settings.COLOR_MUTED), (x, y + 44))
            surface.blit(self.small_font.render(definition.description, True, settings.COLOR_TEXT),
                         (x, y + 80))
            if definition.heal:
                surface.blit(self.font.render(f"Restores {definition.heal} HP", True,
                             settings.COLOR_SAFE), (x, y + 120))
                surface.blit(self.small_font.render("ENTER - use", True, settings.COLOR_AMBER),
                             (x, y + 154))

        hint = self.small_font.render("W/S select   |   ENTER use   |   TAB or ESC close",
                                      True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))