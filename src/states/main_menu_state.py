"""The main menu, built from the design: night city, rain, fog, embers and glowing buttons."""
from __future__ import annotations

import math

import pygame

from src.core import settings
from src.core.game_state import GameState
from src.ui import theme
from src.ui.effects import EmberField, FogLayer, LightningFlash, RainField
from src.ui.menu_art import build_logo, build_menu_background, cover_scale, fire_points
from src.ui.widgets import MenuButton, MenuModel, handle_menu_input, render_tracked

# (label, icon, enabled, action). Disabled entries are built in later milestones.
ENTRIES = (
    ("NEW GAME", "play", True, "new_game"),
    ("CONTINUE", "loop", False, "continue"),
    ("SETTINGS", "gear", False, "settings"),
    ("ACHIEVEMENTS", "trophy", False, "achievements"),
    ("EXIT", "door", True, "exit"),
)
BUTTON_X, BUTTON_Y, BUTTON_W, BUTTON_H, BUTTON_STEP = 107, 321, 312, 48, 54
PAD = 12            # extra background around the screen so the slow "camera drift" shows no edges
FADE_IN = 0.9
FADE_OUT = 0.6


class MainMenuState(GameState):
    def enter(self) -> None:
        pygame.mouse.set_visible(True)
        assets = self.game.assets
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT

        size = (w + 2 * PAD, h + 2 * PAD)
        photo = assets.image("ui/menu_background.png")
        self.background = cover_scale(photo, size) if photo is not None else build_menu_background(*size)
        self.logo = build_logo(assets)

        self.rain = RainField(w, h, count=240)
        self.embers = EmberField(fire_points(w, h), rate=16.0)
        self.clouds = FogLayer(w, h, speed=7.0, alpha=70, band=(0.0, 0.38), color=(70, 90, 130),
                               size=((300, 640), (70, 150)), seed=11)
        self.fog = FogLayer(w, h, speed=14.0, alpha=34, band=(0.62, 1.0), seed=3)
        self.lightning = LightningFlash(w, h)

        self.shade = self._build_shade(w, h)
        self.fade_surface = pygame.Surface((w, h))
        self.fade_surface.fill((0, 0, 0))

        font = assets.font(22, bold=True)
        self.buttons = [
            MenuButton(label, icon,
                       pygame.Rect(BUTTON_X, BUTTON_Y + i * BUTTON_STEP, BUTTON_W, BUTTON_H),
                       font, enabled)
            for i, (label, icon, enabled, _action) in enumerate(ENTRIES)]
        self.model = MenuModel([entry[2] for entry in ENTRIES])
        self.tagline = render_tracked("EXPLORE  /  SURVIVE  /  UNCOVER THE TRUTH",
                                      assets.font(15), theme.MUTED, 3)
        self.hint_font = assets.font(16, bold=True)

        self.time = 0.0
        self.fade = 1.0                      # 1 = fully black
        self.leaving: str | None = None
        self.leave_timer = 0.0

    @staticmethod
    def _build_shade(width: int, height: int) -> pygame.Surface:
        """A dark gradient on the left so the logo and buttons stay readable."""
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        reach = int(width * 0.65)
        for x in range(reach):
            alpha = int(205 * (1 - x / reach) ** 1.5)
            pygame.draw.line(shade, (4, 7, 14, alpha), (x, 0), (x, height))
        return shade

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.leaving is not None:
            return
        index = handle_menu_input(event, self.buttons, self.model)
        if index is not None:
            self._activate(ENTRIES[index][3])

    def _activate(self, action: str) -> None:
        if action == "new_game":
            self.leaving = action
            self.leave_timer = FADE_OUT
        elif action == "exit":
            self.game.quit()

    def update(self, dt: float) -> None:
        self.time += dt
        if self.leaving is None:
            self.fade = max(0.0, self.fade - dt / FADE_IN)
        else:
            self.leave_timer -= dt
            self.fade = min(1.0, 1.0 - max(0.0, self.leave_timer) / FADE_OUT)
            if self.leave_timer <= 0:
                from src.states.playing_state import PlayingState  # avoid circular import
                self.game.state_manager.change_state(PlayingState(self.game))
                return
        self.rain.update(dt)
        self.embers.update(dt)
        self.clouds.update(dt)
        self.fog.update(dt)
        self.lightning.update(dt)
        for index, button in enumerate(self.buttons):
            button.update(dt, index == self.model.selected)

    def render(self, surface: pygame.Surface) -> None:
        # A slow drift of the whole scene gives the "subtle camera movement" of the design.
        drift = (-PAD + 6 * math.sin(self.time * 0.21), -PAD + 4 * math.cos(self.time * 0.17))
        surface.blit(self.background, drift)
        self.clouds.draw(surface)
        self.rain.draw(surface)
        self.fog.draw(surface)
        self.embers.draw(surface)
        self.lightning.draw(surface)
        surface.blit(self.shade, (0, 0))

        surface.blit(self.logo, (90, 50))
        for button in self.buttons:
            button.draw(surface)
        hover = self.model.hover
        if hover is not None and not self.buttons[hover].enabled:
            note = self.hint_font.render("COMING SOON", True, theme.AMBER)
            surface.blit(note, (self.buttons[hover].rect.right + 16,
                                self.buttons[hover].rect.centery - note.get_height() // 2))
        surface.blit(self.tagline, (73, 645))

        if self.fade > 0.0:
            self.fade_surface.set_alpha(int(255 * self.fade))
            surface.blit(self.fade_surface, (0, 0))