"""Radio overlay (safehouse): read received story transmissions."""
from __future__ import annotations

import pygame

from src.core import settings
from src.systems.story import RadioMessage, StoryState
from src.ui.widgets import SelectionList, draw_panel, draw_row_highlight, make_dim, wrap_text


class RadioUI:
    def __init__(self, story: StoryState) -> None:
        self.story = story
        self.nav = SelectionList()
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.heading_font = pygame.font.SysFont("arial", 26, bold=True)
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    def open(self) -> None:
        self.nav.reset()
        self._mark_selected_read()

    def _rows(self) -> list[RadioMessage]:
        """Newest transmission first."""
        return [self.story.data.messages[i] for i in reversed(self.story.inbox)]

    def _mark_selected_read(self) -> None:
        rows = self._rows()
        if rows:
            self.story.mark_read(rows[self.nav.selected].id)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type != pygame.KEYDOWN:
            return None
        if event.key in (pygame.K_UP, pygame.K_w):
            self.nav.move(-1, len(self._rows()))
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.nav.move(1, len(self._rows()))
        self._mark_selected_read()
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, "RADIO", self.title_font,
                   f"{len(self.story.inbox)} RECEIVED", self.font)

        rows = self._rows()
        if not rows:
            surface.blit(self.small_font.render("Only static. Keep the radio close.", True,
                         settings.COLOR_MUTED), (panel.x + 34, panel.y + 94))
        first = max(0, self.nav.selected - 8)
        for slot, index in enumerate(range(first, min(len(rows), first + 9))):
            message = rows[index]
            row = pygame.Rect(panel.x + 24, panel.y + 84 + slot * 38, 410, 34)
            draw_row_highlight(surface, row, index == self.nav.selected)
            unread = message.id not in self.story.read_messages
            label = self.font.render(message.sender, True,
                                     settings.COLOR_AMBER if unread else settings.COLOR_TEXT)
            surface.blit(label, (row.x + 10, row.y + 4))
            if unread:
                new = self.small_font.render("NEW", True, settings.COLOR_AMBER)
                surface.blit(new, new.get_rect(topright=(row.right - 10, row.y + 8)))

        if rows:
            message = rows[self.nav.selected]
            x, y = panel.x + 470, panel.y + 84
            surface.blit(self.heading_font.render(message.sender, True, settings.COLOR_TEXT), (x, y))
            y += 46
            for line in wrap_text(message.text, self.small_font, 400):
                surface.blit(self.small_font.render(line, True, settings.COLOR_TEXT), (x, y))
                y += 24

        hint = self.small_font.render("W/S select   |   E or ESC close", True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))