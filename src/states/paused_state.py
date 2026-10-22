"""The pause menu: drawn on top of the frozen game (a transparent state on the stack)."""
from __future__ import annotations

import pygame

from src.core import settings
from src.core.game_state import GameState
from src.ui import theme
from src.ui.widgets import (
    MenuButton, MenuModel, draw_panel, handle_menu_input, make_dim, render_tracked,
)

ENTRIES = (
    ("RESUME", "play", True, "resume"),
    ("INVENTORY", "bag", True, "hub:inventory"),
    ("MAP", "map", True, "hub:map"),
    ("MISSIONS", "flag", True, "hub:missions"),
    ("CONTROLS", "book", True, "controls"),
    ("SETTINGS", "gear", False, "settings"),
    ("SAVE GAME", "disk", False, "save"),
    ("MAIN MENU", "door", True, "menu"),
)
BUTTON_W, BUTTON_H, BUTTON_STEP = 312, 46, 52

CONTROLS = (
    ("W A S D", "Move"), ("SHIFT", "Sprint"), ("MOUSE", "Aim"), ("LEFT CLICK", "Shoot"),
    ("R", "Reload"), ("E", "Interact / search"), ("Q", "Quick heal"), ("G", "Throw grenade"),
    ("TAB", "Inventory and hub"), ("K", "Skills"), ("M", "Missions"), ("L", "Map"),
)


class PausedState(GameState):
    transparent = True                       # the game stays visible (dimmed) underneath

    def enter(self) -> None:
        pygame.mouse.set_visible(True)
        self.game.audio.duck(True)                           # music dips while paused
        assets = self.game.assets
        w = settings.SCREEN_WIDTH
        self.dim = make_dim()
        self.title_font = assets.font(54, bold=True)
        self.font = assets.font(22, bold=True)
        self.small_font = assets.font(18)

        x = (w - BUTTON_W) // 2
        self.buttons = [
            MenuButton(label, icon, pygame.Rect(x, 214 + i * BUTTON_STEP, BUTTON_W, BUTTON_H),
                       self.font, enabled)
            for i, (label, icon, enabled, _action) in enumerate(ENTRIES)]
        self.model = MenuModel([entry[2] for entry in ENTRIES])

        self.confirm_buttons = [
            MenuButton("STAY", "play", pygame.Rect(w // 2 - BUTTON_W - 12, 400, BUTTON_W, BUTTON_H),
                       self.font),
            MenuButton("LEAVE", "door", pygame.Rect(w // 2 + 12, 400, BUTTON_W, BUTTON_H), self.font),
        ]
        self.confirm_model = MenuModel([True, True])         # starts on STAY: the safe choice
        self.mode = "menu"                                   # "menu", "controls" or "confirm"

    def exit(self) -> None:
        pygame.mouse.set_visible(False)      # back to the in-game crosshair
        self.game.audio.duck(False)      # back to the in-game crosshair

    # ---- input ----
    def handle_event(self, event: pygame.event.Event) -> None:
        if self.mode == "controls":
            if event.type == pygame.KEYDOWN or (
                    event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self.mode = "menu"
        elif self.mode == "confirm":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.mode = "menu"
                return
            index = handle_menu_input(event, self.confirm_buttons, self.confirm_model, sound=self.game.audio.play)
            if index == 0:
                self.mode = "menu"
            elif index == 1:
                from src.states.main_menu_state import MainMenuState  # avoid circular import
                self.game.state_manager.change_state(MainMenuState(self.game))
        else:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.game.state_manager.pop_state()
                return
            index = handle_menu_input(event, self.buttons, self.model, sound=self.game.audio.play)
            if index is not None:
                self._activate(ENTRIES[index][3])

    def _activate(self, action: str) -> None:
        if action == "resume":
            self.game.state_manager.pop_state()
        elif action.startswith("hub:"):
            self.game.state_manager.pop_state()                      # back to the game ...
            self.game.event_bus.emit("HUB_REQUESTED", {"tab": action[4:]})   # ... which opens the hub
        elif action == "controls":
            self.mode = "controls"
        elif action == "menu":
            self.mode = "confirm"
            self.confirm_model.selected = 0

    # ---- update and drawing ----
    def update(self, dt: float) -> None:
        for index, button in enumerate(self.buttons):
            button.update(dt, self.mode == "menu" and index == self.model.selected)
        for index, button in enumerate(self.confirm_buttons):
            button.update(dt, self.mode == "confirm" and index == self.confirm_model.selected)

    def render(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        w = settings.SCREEN_WIDTH
        if self.mode == "controls":
            self._draw_controls(surface)
            return
        title = render_tracked("PAUSED", self.title_font, theme.TEXT, 8)
        surface.blit(title, title.get_rect(center=(w // 2, 132)))

        if self.mode == "confirm":
            question = self.font.render("LEAVE TO THE MAIN MENU?", True, theme.TEXT)
            surface.blit(question, question.get_rect(center=(w // 2, 330)))
            warning = self.small_font.render("Your progress in this run will be lost.", True, theme.MUTED)
            surface.blit(warning, warning.get_rect(center=(w // 2, 362)))
            for button in self.confirm_buttons:
                button.draw(surface)
            return

        for button in self.buttons:
            button.draw(surface)
        hover = self.model.hover
        if hover is not None and not self.buttons[hover].enabled:
            note = self.small_font.render("COMING SOON", True, theme.AMBER)
            surface.blit(note, (self.buttons[hover].rect.right + 16,
                                self.buttons[hover].rect.centery - note.get_height() // 2))

    def _draw_controls(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(0, 0, 820, 440)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        draw_panel(surface, panel, "CONTROLS", self.title_font)
        for index, (key, action) in enumerate(CONTROLS):
            column, row = divmod(index, 6)
            x = panel.x + 40 + column * 390
            y = panel.y + 100 + row * 44
            surface.blit(self.font.render(key, True, theme.AMBER), (x, y))
            surface.blit(self.small_font.render(action, True, theme.TEXT), (x + 160, y + 3))
        hint = self.small_font.render("Press any key to go back", True, theme.MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))