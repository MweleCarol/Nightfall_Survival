"""Combat HUD: crosshair with reload ring, weapon panel with ammo."""
from __future__ import annotations

import math

import pygame

from src.combat.weapon import Weapon
from src.core import settings
from src.ui import theme
from src.ui.hud import make_panel


class CombatHUD:
    def __init__(self, assets=None) -> None:
        self.assets = assets
        self.ammo_font = self._font(46)
        self.reserve_font = self._font(24)
        self.name_font = self._font(16)
        self.small_font = self._font(16)
        self._panel = make_panel(300, 92)

    def _font(self, size: int) -> pygame.font.Font:
        if self.assets is not None:
            return self.assets.font(size, bold=True)
        return pygame.font.SysFont("arial", size, bold=True)

    def draw(self, surface: pygame.Surface, weapon: Weapon, mouse_pos: tuple[int, int],
             enemy_count: int) -> None:
        self._crosshair(surface, mouse_pos, weapon)
        self._weapon_panel(surface, weapon)
        hint = self.small_font.render(
            f"CLICK shoot | R reload | T spawn walker (debug) | Enemies: {enemy_count}",
            True, theme.MUTED)
        surface.blit(hint, (20, settings.SCREEN_HEIGHT - 52))

    def _crosshair(self, surface: pygame.Surface, pos: tuple[int, int], weapon: Weapon) -> None:
        x, y = pos
        gap, length, color = 6, 10, theme.TEXT
        pygame.draw.line(surface, color, (x - gap - length, y), (x - gap, y), 2)
        pygame.draw.line(surface, color, (x + gap, y), (x + gap + length, y), 2)
        pygame.draw.line(surface, color, (x, y - gap - length), (x, y - gap), 2)
        pygame.draw.line(surface, color, (x, y + gap), (x, y + gap + length), 2)
        pygame.draw.circle(surface, theme.RED, pos, 2)
        if weapon.is_reloading:                         # a ring that fills while reloading
            ring = pygame.Rect(0, 0, 44, 44)
            ring.center = pos
            pygame.draw.arc(surface, theme.AMBER, ring, math.pi / 2,
                            math.pi / 2 + 2 * math.pi * max(0.02, weapon.reload_progress), 3)

    def _weapon_panel(self, surface: pygame.Surface, weapon: Weapon) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        x, y = w - 322, h - 124
        surface.blit(self._panel, (x, y))

        name = f"{weapon.definition.name.upper()}   /   {weapon.definition.ammo_type}"
        surface.blit(self.name_font.render(name, True, theme.MUTED), (x + 24, y + 12))

        empty = weapon.loaded == 0
        ammo = self.ammo_font.render(str(weapon.loaded), True, theme.RED if empty else theme.TEXT)
        surface.blit(ammo, (x + 24, y + 28))
        reserve = self.reserve_font.render(f"/ {weapon.reserve}", True, theme.MUTED)
        surface.blit(reserve, (x + 34 + ammo.get_width(), y + 48))

        if weapon.is_reloading:
            bar = pygame.Rect(x + 24, y + 80, 230, 6)
            pygame.draw.rect(surface, (14, 20, 32), bar)
            pygame.draw.rect(surface, theme.AMBER,
                             (bar.x, bar.y, int(bar.width * weapon.reload_progress), bar.height))
            label, color = "RELOADING", theme.AMBER
        elif empty:
            label, color = ("RELOAD (R)", theme.RED) if weapon.reserve > 0 else ("NO AMMO", theme.RED)
        else:
            return
        text = self.small_font.render(label, True, color)
        surface.blit(text, text.get_rect(topright=(x + 270, y + 36)))