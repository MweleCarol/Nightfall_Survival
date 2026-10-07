"""Small shared UI helpers. Full button widgets and polish arrive in Milestone 9."""
from __future__ import annotations

import pygame

from src.core import settings


class SelectionList:
    """Tracks which row of a vertical list is highlighted."""

    def __init__(self) -> None:
        self.selected = 0

    def reset(self) -> None:
        self.selected = 0

    def move(self, delta: int, count: int) -> None:
        if count <= 0:
            self.selected = 0
        else:
            self.selected = max(0, min(self.selected + delta, count - 1))


def make_dim() -> pygame.Surface:
    """A translucent black layer drawn behind overlay panels."""
    dim = pygame.Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 170))
    return dim


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Split text into lines that fit inside max_width pixels."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or font.size(trial)[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, title: str,
               title_font: pygame.font.Font, right_text: str | None = None,
               right_font: pygame.font.Font | None = None) -> None:
    pygame.draw.rect(surface, (12, 18, 30), rect)
    pygame.draw.rect(surface, (70, 88, 120), rect, 2)
    surface.blit(title_font.render(title, True, settings.COLOR_TEXT), (rect.x + 24, rect.y + 16))
    if right_text and right_font:
        text = right_font.render(right_text, True, settings.COLOR_MUTED)
        surface.blit(text, text.get_rect(topright=(rect.right - 24, rect.y + 22)))


def draw_row_highlight(surface: pygame.Surface, rect: pygame.Rect, selected: bool) -> None:
    if selected:
        pygame.draw.rect(surface, (30, 44, 70), rect)
        pygame.draw.rect(surface, settings.COLOR_AMBER, rect, 2)