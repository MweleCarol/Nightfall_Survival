"""Survival HUD: wave status and quick-heal / pack info."""
from __future__ import annotations

import math

import pygame

from src.core import settings
from src.player.inventory import Inventory
from src.systems.wave_manager import WaveManager, WaveState


class SurvivalHUD:
    def __init__(self) -> None:
        self.font = pygame.font.SysFont("arial", 20, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18, bold=True)

    def draw(self, surface: pygame.Surface, waves: WaveManager, alive: int,
             inventory: Inventory, is_night: bool) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

        status = self._wave_status(waves, alive, is_night)
        if status is not None:
            text, color = status
            label = self.font.render(text, True, color)
            surface.blit(label, label.get_rect(topright=(w - 20, 120)))

        heals = [f"{d.name} x{inventory.count(d.id)}"
                 for d in sorted(inventory.definitions.values(), key=lambda d: d.heal)
                 if d.type == "consumable" and d.heal > 0]
        line = (f"Q HEAL: {'  '.join(heals)}   |   TAB INVENTORY   |   "
                f"PACK {inventory.slots_used}/{inventory.capacity}")
        surface.blit(self.small_font.render(line, True, settings.COLOR_MUTED), (20, h - 84))

    def _wave_status(self, waves: WaveManager, alive: int,
                     is_night: bool) -> tuple[str, tuple[int, int, int]] | None:
        if not is_night:
            return ("DAY - SEARCH CRATES (E), BE SAFE BEFORE DARK", settings.COLOR_MUTED)
        total = waves.config.waves_per_night
        if waves.state is WaveState.INTERMISSION:
            seconds = math.ceil(waves.seconds_until_next_wave)
            return (f"WAVE {waves.wave + 1} / {total} IN {seconds}s", settings.COLOR_AMBER)
        if waves.state in (WaveState.SPAWNING, WaveState.ACTIVE):
            count = alive + waves.remaining_to_spawn
            return (f"WAVE {waves.wave} / {total}   ENEMIES {count}", settings.COLOR_ACCENT)
        if waves.state is WaveState.COMPLETE:
            return ("ALL WAVES CLEARED - SURVIVE UNTIL DAWN", settings.COLOR_SAFE)
        return None