"""Hub page: missions (active, available, completed), story chapters and found notes."""
from __future__ import annotations

import pygame

from src.core import settings
from src.systems.mission_system import MissionStatus
from src.ui import theme
from src.ui.hub import HubContext, HubPage
from src.ui.hub_widgets import draw_button, get_font
from src.ui.kit import cut_panel, draw_checkbox, draw_hud_icon, fit_text
from src.ui.widgets import wrap_text

TABS = ("active", "available", "completed", "story", "notes")
TAB_NAMES = {"active": "ACTIVE", "available": "AVAILABLE", "completed": "DONE",
             "story": "STORY", "notes": "NOTES"}
VISIBLE_ROWS, ROW_H = 9, 46
STATUS_COLORS = {MissionStatus.ACTIVE: theme.AMBER, MissionStatus.AVAILABLE: theme.GREEN,
                 MissionStatus.COMPLETED: theme.MUTED, MissionStatus.FAILED: theme.RED}


# ---------------------------------------------------------------- pure logic
def missions_for_tab(manager, tab: str) -> list:
    """The missions shown under a tab. Story missions come before side missions."""
    status = manager.status
    missions = list(manager.missions.values())
    if tab == "active":
        chosen = [m for m in missions if status[m.id] is MissionStatus.ACTIVE]
        return sorted(chosen, key=lambda m: 0 if m.category == "story" else 1)
    if tab == "available":
        chosen = [m for m in missions if status[m.id] is MissionStatus.AVAILABLE]
        return sorted(chosen, key=lambda m: 0 if m.category == "story" else 1)
    if tab == "completed":
        chosen = [m for m in missions if status[m.id] in (MissionStatus.COMPLETED, MissionStatus.FAILED)]
        return sorted(chosen, key=lambda m: 0 if status[m.id] is MissionStatus.COMPLETED else 1)
    return []


def pick_tracked_mission(manager, tracked_id: str | None):
    """The mission the HUD follows: the chosen one if still active, else the first story mission."""
    active = manager.active()
    chosen = next((m for m in active if m.id == tracked_id), None)
    if chosen is not None:
        return chosen
    story = [m for m in active if m.category == "story"]
    return (story or active or [None])[0]


def reward_lines(mission, item_defs: dict) -> list[str]:
    lines: list[str] = []
    if mission.rewards.xp:
        lines.append(f"{mission.rewards.xp} XP")
    lines += [f"{quantity} {item_defs[item_id].name}" for item_id, quantity in mission.rewards.items.items()]
    if mission.rewards.unlock_chapter is not None:
        lines.append(f"Unlocks chapter {mission.rewards.unlock_chapter}")
    return lines


class MissionsPage(HubPage):
    def __init__(self) -> None:
        self.tab_index = 0
        self.selected = 0
        self.scroll = 0
        self.tab_rects: list[tuple[pygame.Rect, int]] = []
        self.row_rects: list[tuple[pygame.Rect, int]] = []
        self.button_rect = pygame.Rect(0, 0, 0, 0)
        self._panels: dict[tuple[int, int], pygame.Surface] = {}

    @property
    def tab(self) -> str:
        return TABS[self.tab_index]

    def hints(self) -> list[tuple[str, str]]:
        return [("A/D", "TAB"), ("W/S", "SELECT"), ("ENTER", "TRACK / ACCEPT")]

    # ---- data ----
    def rows(self, ctx: HubContext) -> list:
        if ctx.missions is None:
            return []
        if self.tab == "story":
            return list(ctx.story.data.chapters.values()) if ctx.story is not None else []
        if self.tab == "notes":
            if ctx.story is None:
                return []
            return [ctx.story.data.notes[note_id] for note_id in ctx.story.found_notes]
        return missions_for_tab(ctx.missions, self.tab)

    def _clamp(self, ctx: HubContext) -> None:
        count = len(self.rows(ctx))
        self.selected = max(0, min(self.selected, count - 1)) if count else 0

    def _set_tab(self, index: int) -> None:
        self.tab_index = index % len(TABS)
        self.selected = self.scroll = 0

    def on_open(self, ctx: HubContext) -> None:
        if ctx.can_accept:                       # opened at the mission board: show what can be accepted
            self._set_tab(TABS.index("available"))
        self._clamp(ctx)

    # ---- input ----
    def handle_event(self, event: pygame.event.Event, ctx: HubContext) -> str | None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._click(event.pos, ctx)
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        count = len(self.rows(ctx))
        if key in (pygame.K_LEFT, pygame.K_a):
            self._set_tab(self.tab_index - 1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._set_tab(self.tab_index + 1)
        elif key in (pygame.K_UP, pygame.K_w):
            self.selected = max(0, self.selected - 1)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.selected = min(max(0, count - 1), self.selected + 1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._activate(ctx)
        self._clamp(ctx)
        return None

    def _click(self, pos: tuple[int, int], ctx: HubContext) -> str | None:
        for rect, index in self.tab_rects:
            if rect.collidepoint(pos):
                self._set_tab(index)
                return None
        for rect, index in self.row_rects:
            if rect.collidepoint(pos):
                if index < len(self.rows(ctx)):
                    self.selected = index
                return None
        if self.button_rect.collidepoint(pos):
            return self._activate(ctx)
        return None

    def _activate(self, ctx: HubContext) -> str | None:
        rows = self.rows(ctx)
        if not rows or self.tab not in ("active", "available"):
            return None
        mission = rows[min(self.selected, len(rows) - 1)]
        if self.tab == "active":
            if ctx.tracked_id == mission.id:
                return "Already tracking this mission"
            if ctx.set_tracked is not None:
                ctx.set_tracked(mission.id)
            return f"Tracking: {mission.title}"
        if not ctx.can_accept:
            return "Accept missions at the safehouse mission board"
        if len(ctx.missions.active()) >= settings.MAX_ACTIVE_MISSIONS:
            return "Mission log is full"
        message = f"Mission accepted: {mission.title}" if ctx.missions.start(mission.id) else None
        self._clamp(ctx)
        return message

    # ---- drawing ----
    def _panel(self, size: tuple[int, int]) -> pygame.Surface:
        panel = self._panels.get(size)
        if panel is None:
            panel = cut_panel(*size)
            self._panels[size] = panel
        return panel

    def draw(self, surface: pygame.Surface, area: pygame.Rect, ctx: HubContext) -> None:
        self._clamp(ctx)
        left = pygame.Rect(area.x, area.y, 500, area.height)
        right = pygame.Rect(left.right + 12, area.y, area.right - left.right - 12, area.height)
        self._draw_list(surface, left, ctx)
        self._draw_details(surface, right, ctx)

    def _draw_list(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        small, tiny = get_font(ctx.assets, 17), get_font(ctx.assets, 13)
        surface.blit(self._panel(rect.size), rect.topleft)
        self.tab_rects = []
        tab_width = (rect.width - 24) // len(TABS)
        for index, name in enumerate(TABS):
            tab = pygame.Rect(rect.x + 12 + index * tab_width, rect.y + 12, tab_width - 4, 30)
            self.tab_rects.append((tab, index))
            active = index == self.tab_index
            pygame.draw.rect(surface, (40, 28, 8) if active else (10, 18, 30), tab)
            pygame.draw.rect(surface, theme.AMBER if active else theme.BORDER, tab, 2 if active else 1)
            label = tiny.render(TAB_NAMES[name], True, theme.AMBER if active else theme.MUTED)
            surface.blit(label, label.get_rect(center=tab.center))

        rows = self.rows(ctx)
        if not rows:
            empty = {"active": "No active missions. Accept one at the mission board.",
                     "available": "Nothing new to accept right now.",
                     "completed": "No finished missions yet.",
                     "story": "Nothing here yet.", "notes": "No notes found yet. Explore the city."}[self.tab]
            surface.blit(tiny.render(empty, True, theme.MUTED), (rect.x + 20, rect.y + 62))
        if self.selected < self.scroll:
            self.scroll = self.selected
        if self.selected >= self.scroll + VISIBLE_ROWS:
            self.scroll = self.selected - VISIBLE_ROWS + 1
        self.row_rects = []
        for slot in range(VISIBLE_ROWS):
            index = self.scroll + slot
            row = pygame.Rect(rect.x + 12, rect.y + 54 + slot * ROW_H, rect.width - 24, ROW_H - 4)
            self.row_rects.append((row, index))
            if index >= len(rows):
                continue
            chosen = index == self.selected
            pygame.draw.rect(surface, (30, 44, 70) if chosen else (10, 18, 30), row)
            pygame.draw.rect(surface, theme.AMBER if chosen else theme.BORDER, row, 2 if chosen else 1)
            self._draw_row(surface, row, rows[index], ctx, small, tiny)

    def _draw_row(self, surface, row, entry, ctx, small, tiny) -> None:
        if self.tab in ("active", "available", "completed"):
            status = ctx.missions.status[entry.id]
            color = STATUS_COLORS[status]
            draw_hud_icon(surface, "diamond" if entry.category == "story" else "radio",
                          (row.x + 20, row.centery), color, 16)
            surface.blit(small.render(fit_text(entry.title, 28), True, theme.TEXT), (row.x + 40, row.y + 11))
            tag = "TRACKED" if (status is MissionStatus.ACTIVE and ctx.tracked_id == entry.id) else status.value
            text = tiny.render(tag, True, color)
            surface.blit(text, text.get_rect(topright=(row.right - 10, row.y + 14)))
        elif self.tab == "story":
            unlocked = ctx.story is not None and entry.id in ctx.story.unlocked_chapters
            text = f"CHAPTER {entry.id}  -  {entry.title}" if unlocked else f"CHAPTER {entry.id}  -  LOCKED"
            surface.blit(small.render(fit_text(text, 38), True, theme.TEXT if unlocked else theme.MUTED),
                         (row.x + 14, row.y + 11))
        else:
            surface.blit(small.render(fit_text(entry.title, 38), True, theme.TEXT), (row.x + 14, row.y + 11))

    def _draw_details(self, surface: pygame.Surface, rect: pygame.Rect, ctx: HubContext) -> None:
        title, heading = get_font(ctx.assets, 18), get_font(ctx.assets, 26)
        small, tiny = get_font(ctx.assets, 15), get_font(ctx.assets, 13)
        surface.blit(self._panel(rect.size), rect.topleft)
        self.button_rect = pygame.Rect(rect.x + 20, rect.bottom - 64, rect.width - 40, 44)
        rows = self.rows(ctx)
        x, y = rect.x + 22, rect.y + 20
        if not rows:
            draw_button(surface, self.button_rect, "NOTHING SELECTED", title, enabled=False)
            return
        entry = rows[min(self.selected, len(rows) - 1)]

        if self.tab in ("story", "notes"):
            if self.tab == "story":
                unlocked = ctx.story is not None and entry.id in ctx.story.unlocked_chapters
                name = entry.title if unlocked else "???"
                text = entry.summary if unlocked else "Locked. Keep moving through the story to unlock it."
            else:
                name, text = entry.title, entry.text
            surface.blit(heading.render(fit_text(name, 30), True, theme.TEXT), (x, y))
            ty = y + 50
            for line in wrap_text(text, small, rect.width - 44):
                surface.blit(small.render(line, True, theme.TEXT), (x, ty))
                ty += 24
            draw_button(surface, self.button_rect, "READ ONLY", title, enabled=False)
            return

        status = ctx.missions.status[entry.id]
        color = STATUS_COLORS[status]
        surface.blit(heading.render(fit_text(entry.title, 30), True, theme.TEXT), (x, y))
        meta = f"{status.value}  |  " + ("MAIN STORY" if entry.category == "story" else "SIDE MISSION")
        if entry.chapter:
            meta += f"  |  CHAPTER {entry.chapter}"
        surface.blit(tiny.render(meta, True, color), (x, y + 36))
        ty = y + 64
        for line in wrap_text(entry.description, small, rect.width - 44)[:4]:
            surface.blit(small.render(line, True, theme.TEXT), (x, ty))
            ty += 22

        ty += 12
        surface.blit(tiny.render("OBJECTIVES", True, theme.MUTED), (x, ty))
        ty += 22
        for index, objective in enumerate(entry.objectives):
            done = ctx.missions.is_objective_done(entry.id, index)
            draw_checkbox(surface, pygame.Rect(x, ty + 2, 14, 14), done)
            count = ""
            if objective.quantity > 1:
                count = f"  ({ctx.missions.progress_of(entry.id, index)}/{objective.quantity})"
            surface.blit(small.render(fit_text(objective.description + count, 46), True,
                                      settings.COLOR_SAFE if done else theme.TEXT), (x + 24, ty))
            ty += 24

        ty += 10
        surface.blit(tiny.render("REWARDS", True, theme.MUTED), (x, ty))
        surface.blit(small.render(fit_text(", ".join(reward_lines(entry, ctx.item_defs)), 52), True,
                                  theme.AMBER), (x, ty + 20))
        if entry.deadline_day is not None and status is MissionStatus.ACTIVE:
            surface.blit(tiny.render(f"Expires after day {entry.deadline_day}", True, theme.RED), (x, ty + 48))

        if status is MissionStatus.ACTIVE:
            tracked = ctx.tracked_id == entry.id
            draw_button(surface, self.button_rect, "TRACKED" if tracked else "TRACK MISSION", title,
                        enabled=not tracked)
        elif status is MissionStatus.AVAILABLE:
            full = len(ctx.missions.active()) >= settings.MAX_ACTIVE_MISSIONS
            draw_button(surface, self.button_rect, "ACCEPT MISSION", title, enabled=ctx.can_accept and not full)
            note = ("Mission log is full" if full and ctx.can_accept
                    else None if ctx.can_accept else "Accept missions at the safehouse mission board")
            if note:
                surface.blit(tiny.render(note, True, theme.MUTED), (x, rect.bottom - 90))
        else:
            draw_button(surface, self.button_rect, status.value, title, enabled=False)