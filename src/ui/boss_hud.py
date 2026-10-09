"""Boss health bar with phase markers, attack warnings and the intro title."""
from __future__ import annotations

import pygame

from src.core import settings
from src.enemies.boss import Boss, BossMode


class BossHUD:
    def __init__(self) -> None:
        self.title_font = pygame.font.SysFont("arial", 78, bold=True)
        self.name_font = pygame.font.SysFont("arial", 26, bold=True)
        self.font = pygame.font.SysFont("arial", 20, bold=True)

    def draw(self, surface: pygame.Surface, boss: Boss) -> None:
        if boss.is_dead:
            return
        w = settings.SCREEN_WIDTH
        bar = pygame.Rect(0, 0, 560, 22)
        bar.midtop = (w // 2, 50)

        reveal = min(1.0, boss.intro_progress / 0.6)         # the bar fills while the name appears
        pygame.draw.rect(surface, (20, 26, 40), bar)
        fill = int(bar.width * boss.health_fraction * reveal)
        pygame.draw.rect(surface, settings.COLOR_ACCENT, (bar.x, bar.y, fill, bar.height))
        pygame.draw.rect(surface, (70, 88, 120), bar, 2)
        for phase in boss.boss_def.phases[1:]:                # a tick where each new phase begins
            x = bar.x + int(bar.width * phase.starts_at)
            pygame.draw.line(surface, settings.COLOR_TEXT, (x, bar.y - 3), (x, bar.bottom + 3), 2)

        name = self.name_font.render(boss.boss_def.name.upper(), True, settings.COLOR_TEXT)
        surface.blit(name, name.get_rect(midbottom=(w // 2, bar.y - 4)))
        phase_text = f"PHASE {boss.phase_index + 1}  -  {boss.phase.name.upper()}"
        phase = self.font.render(phase_text, True, settings.COLOR_MUTED)
        surface.blit(phase, phase.get_rect(midtop=(w // 2, bar.bottom + 6)))

        status = self._status(boss)
        if status is not None:
            text, color = status
            label = self.font.render(text, True, color)
            surface.blit(label, label.get_rect(midtop=(w // 2, bar.bottom + 30)))

        if boss.mode is BossMode.INTRO:
            title = self.title_font.render(boss.boss_def.name.upper(), True, settings.COLOR_ACCENT)
            fade = min(1.0, boss.intro_progress * 3.0) * min(1.0, (1.0 - boss.intro_progress) * 4.0)
            title.set_alpha(int(255 * max(0.0, fade)))
            surface.blit(title, title.get_rect(center=(w // 2, 260)))

    @staticmethod
    def _status(boss: Boss) -> tuple[str, tuple[int, int, int]] | None:
        if boss.mode is BossMode.TRANSITION:
            return ("ENRAGED!", settings.COLOR_ACCENT)
        if boss.vulnerable:
            return ("EXPOSED - STRIKE NOW!", settings.COLOR_AMBER)
        if boss.mode is BossMode.TELEGRAPH and boss.current_attack:
            return (f"{boss.current_attack.upper()}!", settings.COLOR_ACCENT)
        if boss.mode is BossMode.CHARGE:
            return ("CHARGING!", settings.COLOR_ACCENT)
        return None