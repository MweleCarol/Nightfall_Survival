"""Hub page: an overhead map of the district with markers and the tracked mission."""
from __future__ import annotations

import math

import pygame

from src.core import settings
from src.ui import theme
from src.ui.hub import HubContext, HubPage
from src.ui.hub_missions import pick_tracked_mission
from src.ui.hub_widgets import get_font
from src.ui.kit import cut_panel, draw_checkbox, fit_text

BUILDING_FILL, SAFEHOUSE_FILL = (34, 50, 76), (96, 70, 28)


# ---------------------------------------------------------------- pure logic
def fit_scale(world_size: tuple[int, int], available: tuple[int, int]) -> float:
    """The largest scale at which the whole world fits in the available space."""
    return min(available[0] / world_size[0], available[1] / world_size[1])


def world_to_map(point: tuple[float, float], origin: tuple[int, int], scale: float) -> tuple[int, int]:
    """Where a world position lands on the screen."""
    return (round(origin[0] + point[0] * scale), round(origin[1] + point[1] * scale))


def render_base_map(game_map, scale: float, size: tuple[int, int], font: pygame.font.Font) -> pygame.Surface:
    """The district drawn once: buildings with names, obstacles, safe zone and stations."""
    def scaled(rect: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(round(rect.x * scale), round(rect.y * scale),
                           max(2, round(rect.width * scale)), max(2, round(rect.height * scale)))

    surface = pygame.Surface(size)
    surface.fill((11, 18, 30))
    for building in game_map.buildings:
        rect = scaled(building.rect)
        is_home = building.type == "safehouse"
        pygame.draw.rect(surface, SAFEHOUSE_FILL if is_home else BUILDING_FILL, rect)
        pygame.draw.rect(surface, theme.AMBER if is_home else (60, 84, 120), rect, 2 if is_home else 1)
        label = font.render(building.name.upper(), True, theme.AMBER if is_home else theme.MUTED)
        if label.get_width() <= rect.width - 4:
            surface.blit(label, label.get_rect(center=rect.center))
    for obstacle in game_map.obstacles:
        pygame.draw.rect(surface, (30, 42, 62), scaled(obstacle.rect))
    pygame.draw.rect(surface, (60, 130, 80), scaled(game_map.safe_zone), 1)
    for station in game_map.interactables:
        pygame.draw.rect(surface, theme.AMBER, scaled(station.rect).inflate(2, 2), 1)
    pygame.draw.rect(surface, (60, 84, 120), (0, 0, size[0], size[1]), 1)
    return surface


class MapPage(HubPage):
    def __init__(self) -> None:
        self._panels: dict[tuple[int, int], pygame.Surface] = {}
        self._base: pygame.Surface | None = None
        self._base_key: tuple | None = None

    def hints(self) -> list[tuple[str, str]]:
        return []

    def _panel(self, size: tuple[int, int]) -> pygame.Surface:
        panel = self._panels.get(size)
        if panel is None:
            panel = cut_panel(*size)
            self._panels[size] = panel
        return panel

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        title, small = get_font(ctx.assets, 18), get_font(ctx.assets, 15)
        left = pygame.Rect(area.x, area.y, area.width - 362, area.height)
        right = pygame.Rect(left.right + 12, area.y, area.right - left.right - 12, area.height)
        surface.blit(self._panel(left.size), left.topleft)
        surface.blit(self._panel(right.size), right.topleft)
        surface.blit(title.render("DISTRICT MAP", True, theme.TEXT), (left.x + 16, left.y + 12))
        game_map = ctx.game_map
        if game_map is None:
            surface.blit(small.render("No map available.", True, theme.MUTED), (left.x + 16, left.y + 52))
            return
        name = small.render(game_map.name.upper(), True, theme.MUTED)
        surface.blit(name, name.get_rect(topright=(left.right - 16, left.y + 14)))

        inner = pygame.Rect(left.x + 12, left.y + 44, left.width - 24, left.height - 56)
        scale = fit_scale((game_map.width, game_map.height), inner.size)
        size = (int(game_map.width * scale), int(game_map.height * scale))
        origin = (inner.centerx - size[0] // 2, inner.centery - size[1] // 2)
        key = (id(game_map), size)
        if self._base_key != key:                                    # rebuilt only when the size changes
            self._base = render_base_map(game_map, scale, size, get_font(ctx.assets, 11))
            self._base_key = key
        surface.blit(self._base, origin)

        for location in ctx.locations:                               # places the player has found
            if location.id in ctx.discovered:
                point = world_to_map(location.rect.center, origin, scale)
                pygame.draw.circle(surface, theme.CYAN_BRIGHT, point, 4)
                pygame.draw.circle(surface, theme.PANEL_DARK, point, 4, 1)
                text = get_font(ctx.assets, 12).render(location.name, True, theme.CYAN_BRIGHT)
                surface.blit(text, (point[0] + 8, point[1] - text.get_height() // 2))

        if ctx.objective_marker is not None:                         # the tracked objective, pulsing
            point = world_to_map(ctx.objective_marker, origin, scale)
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 250)
            pygame.draw.circle(surface, theme.AMBER, point, int(9 + 5 * pulse), 1)
            diamond = [(point[0], point[1] - 7), (point[0] + 7, point[1]),
                       (point[0], point[1] + 7), (point[0] - 7, point[1])]
            pygame.draw.polygon(surface, theme.AMBER, diamond)
            pygame.draw.polygon(surface, (20, 14, 4), diamond, 1)

        position = world_to_map(ctx.player.position, origin, scale)  # the player, facing the way they aim
        heading = pygame.Vector2(ctx.player.aim_direction)
        heading = heading.normalize() if heading.length_squared() > 0 else pygame.Vector2(1, 0)
        side = pygame.Vector2(-heading.y, heading.x)
        centre = pygame.Vector2(position)
        pygame.draw.polygon(surface, theme.TEXT, [centre + heading * 9, centre - heading * 6 + side * 6,
                                                  centre - heading * 6 - side * 6])
        pygame.draw.polygon(surface, theme.BORDER, [centre + heading * 9, centre - heading * 6 + side * 6,
                                                    centre - heading * 6 - side * 6], 1)
        self._draw_side(surface, right, ctx, title, small)

    def _draw_side(self, surface, rect, ctx, title, small) -> None:
        tiny = get_font(ctx.assets, 13)
        surface.blit(title.render("TRACKED MISSION", True, theme.TEXT), (rect.x + 16, rect.y + 12))
        y = rect.y + 44
        mission = pick_tracked_mission(ctx.missions, ctx.tracked_id) if ctx.missions is not None else None
        if mission is None:
            surface.blit(tiny.render("No active mission. Accept one at the board.", True, theme.MUTED),
                         (rect.x + 16, y))
            y += 28
        else:
            surface.blit(small.render(fit_text(mission.title, 30), True, theme.AMBER), (rect.x + 16, y))
            y += 28
            for index, objective in enumerate(mission.objectives):
                done = ctx.missions.is_objective_done(mission.id, index)
                draw_checkbox(surface, pygame.Rect(rect.x + 16, y + 2, 14, 14), done)
                surface.blit(tiny.render(fit_text(objective.description, 34), True,
                                         settings.COLOR_SAFE if done else theme.TEXT), (rect.x + 38, y))
                y += 22
        y += 14
        surface.blit(title.render("LOCATIONS", True, theme.TEXT), (rect.x + 16, y))
        y += 30
        for location in ctx.locations:
            found = location.id in ctx.discovered
            pygame.draw.circle(surface, theme.CYAN_BRIGHT if found else theme.DISABLED, (rect.x + 24, y + 8), 4,
                               0 if found else 1)
            text = location.name if found else "???"
            surface.blit(tiny.render(fit_text(text, 34), True, theme.TEXT if found else theme.MUTED),
                         (rect.x + 38, y))
            y += 22

        y = rect.bottom - 120                                        # legend
        surface.blit(title.render("LEGEND", True, theme.TEXT), (rect.x + 16, y))
        entries = (("YOU", theme.TEXT), ("OBJECTIVE", theme.AMBER),
                   ("DISCOVERED PLACE", theme.CYAN_BRIGHT), ("SAFE ZONE", (60, 130, 80)))
        for number, (label, color) in enumerate(entries):
            row_y = y + 28 + number * 20
            pygame.draw.rect(surface, color, (rect.x + 18, row_y + 3, 10, 10))
            surface.blit(tiny.render(label, True, theme.TEXT), (rect.x + 38, row_y))