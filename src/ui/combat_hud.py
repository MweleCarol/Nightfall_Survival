"""Combat HUD: crosshair, weapon name, ammo counter, reload bar."""
from __future__ import annotations

import pygame

from src.combat.weapon import Weapon
from src.core import settings


class CombatHUD:
    def __init__(self) -> None:
        self.ammo_font = pygame.font.SysFont("arial", 46, bold=True)
        self.reserve_font = pygame.font.SysFont("arial", 24, bold=True)
        self.name_font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18, bold=True)

    def draw(self, surface: pygame.Surface, weapon: Weapon, mouse_pos: tuple[int, int],
             enemy_count: int) -> None:
        self._crosshair(surface, mouse_pos)
        self._weapon_panel(surface, weapon)
        hint = self.small_font.render(
            f"CLICK shoot | R reload | T spawn walker (debug) | Enemies: {enemy_count}",
            True, settings.COLOR_MUTED)
        surface.blit(hint, (20, settings.SCREEN_HEIGHT - 56))

    def _crosshair(self, surface: pygame.Surface, pos: tuple[int, int]) -> None:
        x, y = pos
        gap, length, color = 6, 10, settings.COLOR_TEXT
        pygame.draw.line(surface, color, (x - gap - length, y), (x - gap, y), 2)
        pygame.draw.line(surface, color, (x + gap, y), (x + gap + length, y), 2)
        pygame.draw.line(surface, color, (x, y - gap - length), (x, y - gap), 2)
        pygame.draw.line(surface, color, (x, y + gap), (x, y + gap + length), 2)
        pygame.draw.circle(surface, settings.COLOR_ACCENT, pos, 2)

    def _weapon_panel(self, surface: pygame.Surface, weapon: Weapon) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        right, bottom = w - 30, h - 40

        name = f"{weapon.definition.name.upper()}  -  {weapon.definition.ammo_type}"
        name_surf = self.name_font.render(name, True, settings.COLOR_MUTED)
        surface.blit(name_surf, name_surf.get_rect(bottomright=(right, bottom - 60)))

        empty = weapon.loaded == 0
        ammo = self.ammo_font.render(
            str(weapon.loaded), True, settings.COLOR_ACCENT if empty else settings.COLOR_TEXT)
        reserve = self.reserve_font.render(f"/ {weapon.reserve}", True, settings.COLOR_MUTED)
        reserve_rect = reserve.get_rect(bottomright=(right, bottom - 6))
        surface.blit(reserve, reserve_rect)
        surface.blit(ammo, ammo.get_rect(bottomright=(reserve_rect.left - 10, bottom)))

        if weapon.is_reloading:
            bar = pygame.Rect(right - 220, bottom + 6, 220, 8)
            pygame.draw.rect(surface, (20, 26, 40), bar)
            pygame.draw.rect(surface, settings.COLOR_AMBER,
                             (bar.x, bar.y, int(bar.width * weapon.reload_progress), bar.height))
            label = self.small_font.render("RELOADING", True, settings.COLOR_AMBER)
            surface.blit(label, label.get_rect(bottomright=(right, bar.y - 4)))
        elif empty:
            text = "PRESS R TO RELOAD" if weapon.reserve > 0 else "NO AMMO"
            label = self.small_font.render(text, True, settings.COLOR_ACCENT)
            surface.blit(label, label.get_rect(topright=(right, bottom + 6)))