"""The hub: one shell (top bar, bottom bar, tabs) that hosts the Inventory, Skills, ... pages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pygame

from src.core import settings
from src.ui import theme
from src.ui.hub_widgets import draw_portrait, draw_tab_icon
from src.ui.kit import cut_panel, draw_bar, draw_hud_icon, draw_keycap
from src.ui.menu_art import cover_scale

TABS = ("map", "inventory", "crafting", "skills", "missions", "settings")
TAB_NAMES = {"map": "MAP", "inventory": "INVENTORY", "crafting": "CRAFTING",
             "skills": "SKILLS", "missions": "MISSIONS", "settings": "SETTINGS"}
TOP_BAR = 100
BOTTOM_BAR = 44
TAB_X = 352
TAB_W = 112


@dataclass
class HubContext:
    """Everything a hub page may need, handed over each frame by the game."""
    assets: Any
    item_defs: dict
    player: Any
    inventory: Any
    equipment: Any
    skills: Any
    progression: Any
    base_capacity: Callable[[], int]
    attachment_defs: dict
    cycle_label: str = "DAY 1"
    clock_text: str = "08:00"
    is_day: bool = True
    location: str = "DISTRICT"
    crafting: Any = None                      # the CraftingSystem
    missions: Any = None                      # the MissionManager
    story: Any = None                         # the StoryState
    game_map: Any = None                      # the GameMap
    locations: Any = ()                       # the named places (Location objects)
    discovered: Any = ()                      # ids of the places the player has found
    objective_marker: Any = None              # world position of the tracked objective
    tracked_id: str | None = None             # the mission the HUD follows
    set_tracked: Any = None                   # callback: set_tracked(mission_id)
    can_accept: bool = False                  # True when opened at the mission board
    can_craft: bool = True                    # False away from the safehouse


class HubPage:
    """One tab of the hub. Subclasses draw into the content area and handle their own keys."""

    def on_open(self, ctx: HubContext) -> None:
        """Called when the page becomes the visible tab."""

    def handle_event(self, event: pygame.event.Event, ctx: HubContext) -> str | None:
        """Handle an input event. Returns a short message to show the player, if any."""
        return None

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        """Draw the page inside `area`."""

    def hints(self) -> list[tuple[str, str]]:
        """Key hints for the bottom bar, as (key, label) pairs."""
        return []


class HubUI:
    def __init__(self, assets: Any, context_provider: Callable[[], HubContext]) -> None:
        self.assets = assets
        self.context_provider = context_provider
        self.pages: dict[str, HubPage] = {}
        self.tab = "inventory"
        self.close_requested = False
        self.small_font = self._font(13)
        self.label_font = self._font(14)
        self.clock_font = self._font(22)

        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        photo = assets.image("ui/hub_background.png") if assets is not None else None
        self._background = cover_scale(photo, (w, h)) if photo is not None else None
        self._dim = pygame.Surface((w, h), pygame.SRCALPHA)
        self._dim.fill((4, 8, 14, 150 if photo is not None else 232))
        self._vitals_panel = cut_panel(342, 88)
        self._active_tab = cut_panel(TAB_W - 4, 84, border=theme.AMBER, fill=(44, 30, 8, 220))
        self._clock_panel = cut_panel(134, 84)
        self._place_panel = cut_panel(96, 84)
        self._tab_rects: dict[str, pygame.Rect] = {}

    def _font(self, size: int) -> pygame.font.Font:
        if self.assets is not None:
            return self.assets.font(size, bold=True)
        return pygame.font.SysFont("arial", size, bold=True)

    @staticmethod
    def content_rect() -> pygame.Rect:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        return pygame.Rect(14, TOP_BAR + 8, w - 28, h - TOP_BAR - BOTTOM_BAR - 16)

    # ---- pages and tabs ----
    def set_page(self, tab: str, page: HubPage) -> None:
        self.pages[tab] = page

    def available(self) -> list[str]:
        return [tab for tab in TABS if tab in self.pages]

    def open(self, tab: str) -> None:
        available = self.available()
        self.tab = tab if tab in self.pages else (available[0] if available else tab)
        self.close_requested = False
        page = self.pages.get(self.tab)
        if page is not None:
            page.on_open(self.context_provider())

    def switch(self, tab: str) -> None:
        if tab in self.pages and tab != self.tab:
            self.tab = tab
            self.pages[tab].on_open(self.context_provider())

    def cycle(self, step: int) -> None:
        tabs = self.available()
        if len(tabs) < 2 or self.tab not in tabs:
            return
        self.switch(tabs[(tabs.index(self.tab) + step) % len(tabs)])

    # ---- input ----
    def handle_event(self, event: pygame.event.Event) -> str | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for tab, rect in self._tab_rects.items():
                if rect.collidepoint(event.pos):
                    self.switch(tab)
                    return None
        elif event.type == pygame.KEYDOWN:
            key = event.key
            if key == pygame.K_ESCAPE:
                self.close_requested = True
                return None
            if key == pygame.K_TAB:
                self.cycle(-1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1)
                return None
            if pygame.K_1 <= key <= pygame.K_6:
                self.switch(TABS[key - pygame.K_1])
                return None
        page = self.pages.get(self.tab)
        if page is None:
            return None
        return page.handle_event(event, self.context_provider())

    # ---- drawing ----
    def draw(self, surface: pygame.Surface) -> None:
        ctx = self.context_provider()
        if self._background is not None:
            surface.blit(self._background, (0, 0))
        surface.blit(self._dim, (0, 0))
        self._draw_top(surface, ctx)
        page = self.pages.get(self.tab)
        if page is not None:
            page.draw(surface, self.content_rect(), ctx)
        self._draw_bottom(surface, page)

    def _draw_top(self, surface: pygame.Surface, ctx: HubContext) -> None:
        w = settings.SCREEN_WIDTH
        pygame.draw.rect(surface, (6, 12, 22), (0, 0, w, TOP_BAR))
        pygame.draw.line(surface, theme.CYAN, (0, TOP_BAR - 1), (w, TOP_BAR - 1), 1)
        self._draw_vitals(surface, ctx)
        self._draw_tabs(surface)
        self._draw_clock(surface, ctx)

    def _draw_vitals(self, surface: pygame.Surface, ctx: HubContext) -> None:
        stats, progression = ctx.player.stats, ctx.progression
        surface.blit(self._vitals_panel, (10, 6))
        draw_portrait(surface, ctx.assets, pygame.Rect(20, 14, 62, 62))
        badge = pygame.Rect(20, 74, 62, 18)
        pygame.draw.rect(surface, theme.PANEL_DARK, badge)
        pygame.draw.rect(surface, theme.CYAN, badge, 1)
        level = self.small_font.render(f"LV  {progression.level}", True, theme.TEXT)
        surface.blit(level, level.get_rect(center=badge.center))

        hp = pygame.Rect(120, 18, 210, 18)
        draw_hud_icon(surface, "heart", (104, 27), theme.RED, 16)
        draw_bar(surface, hp, stats.health / stats.max_health, theme.RED)
        text = self.small_font.render(f"{stats.health} / {stats.max_health}", True, theme.TEXT)
        surface.blit(text, (hp.x + 8, hp.y + (hp.height - text.get_height()) // 2))

        sta = pygame.Rect(120, 44, 210, 14)
        draw_hud_icon(surface, "bolt", (104, 51), theme.STAMINA, 16)
        draw_bar(surface, sta, stats.stamina / stats.max_stamina, theme.STAMINA)

        needed = 0 if progression.is_max_level else progression.xp_required()
        draw_bar(surface, pygame.Rect(120, 68, 130, 8), progression.xp / needed if needed else 1.0, theme.CYAN)
        label = f"{progression.xp} / {needed} XP" if needed else "MAX LEVEL"
        xp_text = self.small_font.render(label, True, theme.TEXT)
        surface.blit(xp_text, xp_text.get_rect(topright=(330, 64)))

    def _draw_tabs(self, surface: pygame.Surface) -> None:
        for index, tab in enumerate(TABS):
            rect = pygame.Rect(TAB_X + index * TAB_W, 8, TAB_W - 4, 84)
            self._tab_rects[tab] = rect
            if tab == self.tab:
                surface.blit(self._active_tab, rect.topleft)
                color = theme.AMBER
            else:
                color = theme.TEXT if tab in self.pages else theme.DISABLED
            draw_tab_icon(surface, tab, (rect.centerx, rect.y + 32), color, 28)
            label = self.label_font.render(TAB_NAMES[tab], True, color)
            surface.blit(label, label.get_rect(center=(rect.centerx, rect.y + 64)))

    def _draw_clock(self, surface: pygame.Surface, ctx: HubContext) -> None:
        x = 1038
        surface.blit(self._clock_panel, (x, 8))
        color = theme.AMBER if ctx.is_day else (150, 180, 235)
        draw_hud_icon(surface, "sun" if ctx.is_day else "moon", (x + 28, 50), color, 24)
        surface.blit(self.label_font.render(ctx.cycle_label, True, color), (x + 54, 24))
        surface.blit(self.clock_font.render(ctx.clock_text, True, theme.TEXT), (x + 54, 46))

        px = x + 140
        surface.blit(self._place_panel, (px, 8))
        hx, hy = px + 48, 38                                   # a little house
        pygame.draw.polygon(surface, theme.TEXT, [(hx - 12, hy), (hx, hy - 11), (hx + 12, hy)], 2)
        pygame.draw.rect(surface, theme.TEXT, (hx - 8, hy, 16, 12), 2)
        place = self.small_font.render(ctx.location, True, theme.TEXT)
        surface.blit(place, place.get_rect(center=(px + 48, 72)))

    def _draw_bottom(self, surface: pygame.Surface, page: HubPage | None) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        y = h - BOTTOM_BAR
        pygame.draw.rect(surface, (6, 12, 22), (0, y, w, BOTTOM_BAR))
        pygame.draw.line(surface, theme.CYAN, (0, y), (w, y), 1)
        x = 20
        for key, label in (("ESC", "BACK"), ("TAB", "NEXT TAB")):
            cap = draw_keycap(surface, self.small_font, key, (x, y + 10))
            text = self.small_font.render(label, True, theme.TEXT)
            surface.blit(text, (cap.right + 8, y + 12))
            x = cap.right + 8 + text.get_width() + 28
        right = w - 20
        for key, label in reversed(page.hints() if page is not None else []):
            text = self.small_font.render(label, True, theme.TEXT)
            cap_width = max(22, self.small_font.size(key)[0] + 12)
            left = right - text.get_width() - 8 - cap_width
            draw_keycap(surface, self.small_font, key, (left, y + 10))
            surface.blit(text, (left + cap_width + 8, y + 12))
            right = left - 28