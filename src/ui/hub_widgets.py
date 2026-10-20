"""Drawing helpers and small pure functions shared by the hub screens."""
from __future__ import annotations

import pygame
from pygame import Vector2

from src.player.inventory import ITEM_TYPES, RARITIES, ItemDef
from src.systems.skills import SkillDef
from src.ui import theme
from src.ui.kit import draw_hud_icon
from src.ui.widgets import draw_icon

ITEM_FILTERS = ("all", "ammo", "gear", "consumables", "materials")
FILTER_NAMES = {"all": "ALL", "ammo": "AMMO", "gear": "GEAR",
                "consumables": "CONSUMABLES", "materials": "MATERIALS"}
SORT_MODES = ("type", "name", "rarity", "amount")

_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}
_PORTRAIT_CACHE: dict[tuple[int, int], pygame.Surface | None] = {}


def get_font(assets, size: int) -> pygame.font.Font:
    """A cached bold UI font: from the asset manager if there is one, else a system font."""
    key = (size, assets is None)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = assets.font(size, bold=True) if assets is not None \
            else pygame.font.SysFont("arial", size, bold=True)
        _FONT_CACHE[key] = font
    return font


# ---------------------------------------------------------------- pure logic
def item_category(definition: ItemDef) -> str:
    """Which inventory filter an item belongs to."""
    if definition.type == "ammo":
        return "ammo"
    if definition.type in ("equipment", "attachment"):
        return "gear"
    if definition.type in ("consumable", "throwable"):
        return "consumables"
    return "materials"                                   # resources and quest items


def filter_items(items: list[tuple[str, int]], definitions: dict[str, ItemDef],
                 category: str) -> list[tuple[str, int]]:
    if category == "all":
        return list(items)
    return [entry for entry in items if item_category(definitions[entry[0]]) == category]


def sort_items(items: list[tuple[str, int]], definitions: dict[str, ItemDef],
               mode: str) -> list[tuple[str, int]]:
    def key(entry: tuple[str, int]):
        item_id, quantity = entry
        definition = definitions[item_id]
        if mode == "name":
            return (definition.name,)
        if mode == "rarity":                              # rarest first
            return (-RARITIES.index(definition.rarity), definition.name)
        if mode == "amount":                              # biggest stacks first
            return (-quantity, definition.name)
        return (ITEM_TYPES.index(definition.type), definition.name)
    return sorted(items, key=key)


def move_in_grid(index: int, dx: int, dy: int, count: int, columns: int) -> int:
    """Move a selection around a grid. It never leaves the items that exist."""
    if count <= 0:
        return 0
    row, col = divmod(index, columns)
    new_col = max(0, min(columns - 1, col + dx))
    new_row = max(0, row + dy)
    candidate = new_row * columns + new_col
    if candidate < count:
        return candidate
    if dy > 0 and new_row == (count - 1) // columns:      # moving down into a half-empty last row
        return count - 1
    return index


_PERCENT_EFFECTS = {
    "move_speed": "movement speed", "damage": "weapon damage",
    "reload_time_reduction": "faster reloads", "crit_chance": "critical hit chance",
    "loot_luck": "fewer empty searches", "free_craft_chance": "chance of a free craft",
}
_FLAT_EFFECTS = {"max_health": "maximum health", "max_stamina": "maximum stamina",
                 "carry_slots": "inventory slots"}


def format_skill_effect(definition: SkillDef, rank: int) -> str:
    """The total bonus a skill gives at a rank, in words (e.g. '+30 maximum health')."""
    if rank <= 0:
        return "No bonus yet"
    total = definition.per_rank * rank
    if definition.stat in _FLAT_EFFECTS:
        return f"+{round(total)} {_FLAT_EFFECTS[definition.stat]}"
    if definition.stat in _PERCENT_EFFECTS:
        return f"+{total:.0%} {_PERCENT_EFFECTS[definition.stat]}"
    return f"+{total:g} {definition.stat}"


# ---------------------------------------------------------------- drawing
def draw_button(surface: pygame.Surface, rect: pygame.Rect, label: str,
                font: pygame.font.Font, enabled: bool = True, primary: bool = True) -> None:
    if enabled and primary:
        fill, border, text = (52, 36, 8), theme.AMBER, theme.AMBER
    elif enabled:
        fill, border, text = (12, 22, 38), theme.CYAN, theme.TEXT
    else:
        fill, border, text = (12, 18, 28), theme.BORDER, theme.DISABLED
    pygame.draw.rect(surface, fill, rect)
    pygame.draw.rect(surface, border, rect, 2)
    rendered = font.render(label, True, text)
    surface.blit(rendered, rendered.get_rect(center=rect.center))


def draw_portrait(surface: pygame.Surface, assets, rect: pygame.Rect) -> None:
    """The player's portrait: assets/images/ui/portrait.png if it exists, else a simple bust."""
    key = rect.size
    if key not in _PORTRAIT_CACHE:
        image = assets.image("ui/portrait.png") if assets is not None else None
        _PORTRAIT_CACHE[key] = pygame.transform.smoothscale(image, rect.size) if image is not None else None
    image = _PORTRAIT_CACHE[key]
    if image is not None:
        surface.blit(image, rect)
    else:
        surface.set_clip(rect)
        pygame.draw.rect(surface, (14, 22, 36), rect)
        w, h, cx = rect.width, rect.height, rect.centerx
        pygame.draw.ellipse(surface, (40, 52, 70), (rect.x + int(w * 0.12), rect.bottom - int(h * 0.36),
                                                    int(w * 0.76), int(h * 0.55)))
        pygame.draw.circle(surface, (176, 138, 108), (cx, rect.centery + int(h * 0.02)), int(h * 0.24))
        pygame.draw.rect(surface, (28, 34, 44), (cx - int(w * 0.28), rect.centery - int(h * 0.30),
                                                 int(w * 0.56), int(h * 0.20)))
        pygame.draw.line(surface, (28, 34, 44), (cx - int(w * 0.06), rect.centery - int(h * 0.14)),
                         (cx + int(w * 0.32), rect.centery - int(h * 0.14)), max(2, int(h * 0.07)))
        surface.set_clip(None)
    pygame.draw.rect(surface, theme.CYAN, rect, 2)


def draw_tab_icon(surface: pygame.Surface, tab: str, center: tuple[float, float],
                  color: tuple[int, int, int], size: int = 26) -> None:
    cx, cy = center
    r = size / 2

    def box(x: float, y: float, w: float, h: float) -> pygame.Rect:
        return pygame.Rect(int(x), int(y), max(1, int(w)), max(1, int(h)))

    if tab == "map":                                      # a folded map
        for i in range(3):
            x0 = cx - r + i * (size / 3)
            x1 = x0 + size / 3
            top0, top1 = (-0.6, -0.85) if i % 2 == 0 else (-0.85, -0.6)
            bot0, bot1 = (0.85, 0.6) if i % 2 == 0 else (0.6, 0.85)
            pygame.draw.polygon(surface, color, [(x0, cy + r * top0), (x1, cy + r * top1),
                                                 (x1, cy + r * bot1), (x0, cy + r * bot0)], 2)
    elif tab == "inventory":                              # a backpack
        pygame.draw.rect(surface, color, box(cx - r * 0.6, cy - r * 0.35, r * 1.2, r * 1.3), 2, border_radius=4)
        pygame.draw.arc(surface, color, box(cx - r * 0.35, cy - r * 0.95, r * 0.7, r * 0.9), 0, 3.14159, 2)
        pygame.draw.line(surface, color, (cx - r * 0.6, cy + r * 0.25), (cx + r * 0.6, cy + r * 0.25), 2)
    elif tab == "crafting":                               # a hammer and a wrench
        pygame.draw.line(surface, color, (cx - r * 0.8, cy + r * 0.8), (cx + r * 0.5, cy - r * 0.5), 4)
        pygame.draw.circle(surface, color, (int(cx + r * 0.6), int(cy - r * 0.6)), max(2, int(r * 0.38)), 2)
        pygame.draw.line(surface, color, (cx + r * 0.8, cy + r * 0.8), (cx - r * 0.5, cy - r * 0.5), 4)
        pygame.draw.rect(surface, color, box(cx - r * 0.85, cy - r * 0.85, r * 0.5, r * 0.3))
    elif tab == "skills":                                 # a star
        points = []
        for i in range(10):
            radius = r if i % 2 == 0 else r * 0.45
            direction = Vector2(0, -1).rotate(i * 36)
            points.append((cx + direction.x * radius, cy + direction.y * radius))
        pygame.draw.polygon(surface, color, points, 2)
    elif tab == "missions":
        draw_hud_icon(surface, "diamond", center, color, size)
    elif tab == "settings":
        draw_icon(surface, "gear", (int(cx), int(cy)), color, size)


def draw_skill_icon(surface: pygame.Surface, stat: str, center: tuple[float, float],
                    color: tuple[int, int, int], size: int = 28) -> None:
    """An icon for a skill, chosen from the stat it improves."""
    cx, cy = center
    r = size / 2
    if stat == "max_health":
        draw_hud_icon(surface, "heart", center, color, size)
    elif stat == "max_stamina":
        draw_hud_icon(surface, "bolt", center, color, size)
    elif stat == "reload_time_reduction":
        draw_hud_icon(surface, "mag", center, color, size)
    elif stat == "move_speed":                            # two forward chevrons
        for dx in (-r * 0.5, r * 0.2):
            pygame.draw.lines(surface, color, False, [(cx + dx, cy - r * 0.7), (cx + dx + r * 0.5, cy),
                                                      (cx + dx, cy + r * 0.7)], 3)
    elif stat == "damage":                                # a crosshair
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(r * 0.7), 2)
        pygame.draw.circle(surface, color, (int(cx), int(cy)), 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(surface, color, (cx + dx * r * 0.4, cy + dy * r * 0.4),
                             (cx + dx * r * 1.05, cy + dy * r * 1.05), 2)
    elif stat == "crit_chance":                           # a starburst
        for step in range(8):
            ray = Vector2(1, 0).rotate(step * 45)
            pygame.draw.line(surface, color, (cx + ray.x * r * 0.3, cy + ray.y * r * 0.3),
                             (cx + ray.x * r, cy + ray.y * r), 2)
    elif stat == "carry_slots":                           # a pack
        pygame.draw.rect(surface, color, pygame.Rect(int(cx - r * 0.6), int(cy - r * 0.4),
                                                     int(r * 1.2), int(r * 1.3)), 2, border_radius=4)
        pygame.draw.line(surface, color, (cx - r * 0.3, cy - r * 0.4), (cx - r * 0.3, cy - r * 0.8), 2)
        pygame.draw.line(surface, color, (cx + r * 0.3, cy - r * 0.4), (cx + r * 0.3, cy - r * 0.8), 2)
    elif stat == "free_craft_chance":
        draw_icon(surface, "gear", (int(cx), int(cy)), color, size)
    else:
        draw_hud_icon(surface, "diamond", center, color, size)