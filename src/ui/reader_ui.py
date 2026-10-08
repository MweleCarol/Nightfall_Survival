"""Small overlay for reading a found note."""
from __future__ import annotations

import pygame

from src.core import settings
from src.ui.widgets import draw_panel, make_dim, wrap_text


class ReaderUI:
    def __init__(self) -> None:
        self.title = ""
        self.text = ""
        self.title_font = pygame.font.SysFont("arial", 30, bold=True)
        self.font = pygame.font.SysFont("arial", 22)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    def show(self, title: str, text: str) -> None:
        self.title = title
        self.text = text

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 680, 380)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, self.title, self.title_font)
        y = panel.y + 80
        for line in wrap_text(self.text, self.font, panel.width - 64):
            surface.blit(self.font.render(line, True, settings.COLOR_TEXT), (panel.x + 32, y))
            y += 30
        hint = self.small_font.render("E or ENTER - close", True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))