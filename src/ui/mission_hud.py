"""HUD tracker for active missions, plus the blinking radio alert."""
from __future__ import annotations

import pygame

from src.core import settings
from src.systems.mission_system import MissionManager
from src.systems.story import StoryState


class MissionHUD:
    def __init__(self) -> None:
        self.title_font = pygame.font.SysFont("arial", 18, bold=True)
        self.font = pygame.font.SysFont("arial", 16, bold=True)

    def draw(self, surface: pygame.Surface, missions: MissionManager, story: StoryState) -> None:
        right = settings.SCREEN_WIDTH - 20
        y = 150
        header = self.font.render("MISSIONS (M)", True, settings.COLOR_MUTED)
        surface.blit(header, header.get_rect(topright=(right, y)))
        y += 24

        for mission in missions.active():
            title = self.title_font.render(mission.title.upper(), True, settings.COLOR_AMBER)
            surface.blit(title, title.get_rect(topright=(right, y)))
            y += 22
            for index, objective in enumerate(mission.objectives):
                done = missions.is_objective_done(mission.id, index)
                count = ""
                if objective.quantity > 1:
                    count = f" ({missions.progress_of(mission.id, index)}/{objective.quantity})"
                mark = "[X]" if done else "[  ]"
                color = settings.COLOR_SAFE if done else settings.COLOR_TEXT
                line = self.font.render(f"{mark} {objective.description}{count}", True, color)
                surface.blit(line, line.get_rect(topright=(right, y)))
                y += 20
            y += 8

        unread = story.unread_count
        if unread and (pygame.time.get_ticks() // 500) % 2 == 0:       # blink twice a second
            plural = "S" if unread != 1 else ""
            alert = self.font.render(
                f"RADIO: {unread} NEW TRANSMISSION{plural} - USE THE SAFEHOUSE RADIO",
                True, settings.COLOR_AMBER)
            surface.blit(alert, (20, 176))