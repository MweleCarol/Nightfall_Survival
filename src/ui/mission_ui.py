"""Journal (key M) and mission board (safehouse): missions, story chapters and notes."""
from __future__ import annotations

import pygame

from src.core import settings
from src.player.inventory import ItemDef
from src.systems.mission_system import MissionDef, MissionManager, MissionStatus
from src.systems.story import StoryState
from src.ui.widgets import SelectionList, draw_panel, draw_row_highlight, make_dim, wrap_text

TABS = ("missions", "story", "notes")
TAB_NAMES = {"missions": "MISSIONS", "story": "STORY", "notes": "NOTES"}
STATUS_ORDER = {MissionStatus.ACTIVE: 0, MissionStatus.AVAILABLE: 1,
                MissionStatus.COMPLETED: 2, MissionStatus.FAILED: 3}   # LOCKED is hidden
STATUS_COLORS = {
    MissionStatus.ACTIVE: settings.COLOR_AMBER,
    MissionStatus.AVAILABLE: settings.COLOR_SAFE,
    MissionStatus.COMPLETED: settings.COLOR_MUTED,
    MissionStatus.FAILED: settings.COLOR_ACCENT,
}
VISIBLE_ROWS = 9
ROW_HEIGHT = 38


class MissionUI:
    def __init__(self, missions: MissionManager, story: StoryState,
                 item_defs: dict[str, ItemDef]) -> None:
        self.missions = missions
        self.story = story
        self.item_defs = item_defs
        self.board_mode = False              # True at the safehouse board: missions can be accepted
        self.tab = "missions"
        self.nav = SelectionList()
        self.title_font = pygame.font.SysFont("arial", 34, bold=True)
        self.heading_font = pygame.font.SysFont("arial", 26, bold=True)
        self.font = pygame.font.SysFont("arial", 22, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18)
        self.dim = make_dim()

    def open(self, board_mode: bool) -> None:
        self.board_mode = board_mode
        self.tab = "missions"
        self.nav.reset()

    # ---- rows for the current tab ----
    def _rows(self) -> list:
        if self.tab == "missions":
            shown = [m for m in self.missions.missions.values()
                     if self.missions.status[m.id] in STATUS_ORDER]
            return sorted(shown, key=lambda m: STATUS_ORDER[self.missions.status[m.id]])
        if self.tab == "story":
            return list(self.story.data.chapters.values())
        return [self.story.data.notes[note_id] for note_id in self.story.found_notes]

    def _switch_tab(self, step: int) -> None:
        self.tab = TABS[(TABS.index(self.tab) + step) % len(TABS)]
        self.nav.reset()

    # ---- input ----
    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle a key press while open. Returns a message to show, if any."""
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key
        if key in (pygame.K_LEFT, pygame.K_a):
            self._switch_tab(-1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._switch_tab(1)
        elif key in (pygame.K_UP, pygame.K_w):
            self.nav.move(-1, len(self._rows()))
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.nav.move(1, len(self._rows()))
        elif key == pygame.K_RETURN and self.board_mode and self.tab == "missions":
            return self._accept_selected()
        return None

    def _accept_selected(self) -> str | None:
        rows = self._rows()
        if not rows:
            return None
        mission = rows[self.nav.selected]
        if self.missions.status[mission.id] is not MissionStatus.AVAILABLE:
            return None
        if self.missions.start(mission.id):
            self.nav.selected = self._rows().index(mission)      # keep the highlight on it
            return f"Mission accepted: {mission.title}"
        return "Mission log is full"

    # ---- drawing ----
    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 520)
        panel.center = (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2)
        title = "MISSION BOARD" if self.board_mode else "JOURNAL"
        active = f"ACTIVE {len(self.missions.active())}/{settings.MAX_ACTIVE_MISSIONS}"
        draw_panel(surface, panel, title, self.title_font, active, self.font)

        for index, tab in enumerate(TABS):
            on = tab == self.tab
            color = settings.COLOR_AMBER if on else settings.COLOR_MUTED
            label = self.font.render(TAB_NAMES[tab], True, color)
            pos = (panel.x + 360 + index * 140, panel.y + 24)
            surface.blit(label, pos)
            if on:
                pygame.draw.line(surface, color, (pos[0], pos[1] + 30),
                                 (pos[0] + label.get_width(), pos[1] + 30), 3)

        rows = self._rows()
        if not rows:
            empty = {"missions": "No missions yet.", "story": "Nothing here yet.",
                     "notes": "No notes found yet. Explore the city."}[self.tab]
            surface.blit(self.small_font.render(empty, True, settings.COLOR_MUTED),
                         (panel.x + 34, panel.y + 94))
        first = max(0, self.nav.selected - (VISIBLE_ROWS - 1))     # scroll the list window
        for slot, index in enumerate(range(first, min(len(rows), first + VISIBLE_ROWS))):
            row = pygame.Rect(panel.x + 24, panel.y + 84 + slot * ROW_HEIGHT, 410, ROW_HEIGHT - 4)
            draw_row_highlight(surface, row, index == self.nav.selected)
            self._draw_row(surface, row, rows[index])
        if rows:
            self._draw_details(surface, panel, rows[self.nav.selected])

        hint = self.small_font.render(
            "A/D switch tab   |   W/S select   |   "
            + ("ENTER accept   |   E or ESC close" if self.board_mode else "M or ESC close"),
            True, settings.COLOR_MUTED)
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))

    def _draw_row(self, surface: pygame.Surface, row: pygame.Rect, entry) -> None:
        if self.tab == "missions":
            status = self.missions.status[entry.id]
            surface.blit(self.font.render(entry.title, True, settings.COLOR_TEXT),
                         (row.x + 10, row.y + 4))
            tag = self.small_font.render(status.value, True, STATUS_COLORS[status])
            surface.blit(tag, tag.get_rect(topright=(row.right - 10, row.y + 8)))
        elif self.tab == "story":
            unlocked = entry.id in self.story.unlocked_chapters
            text = f"CHAPTER {entry.id}  -  {entry.title}" if unlocked else f"CHAPTER {entry.id}  -  LOCKED"
            color = settings.COLOR_TEXT if unlocked else settings.COLOR_MUTED
            surface.blit(self.font.render(text, True, color), (row.x + 10, row.y + 4))
        else:
            surface.blit(self.font.render(entry.title, True, settings.COLOR_TEXT),
                         (row.x + 10, row.y + 4))

    def _draw_details(self, surface: pygame.Surface, panel: pygame.Rect, entry) -> None:
        x, y = panel.x + 470, panel.y + 84
        if self.tab == "missions":
            self._draw_mission(surface, entry, x, y)
        elif self.tab == "story":
            unlocked = entry.id in self.story.unlocked_chapters
            surface.blit(self.heading_font.render(entry.title if unlocked else "???", True,
                         settings.COLOR_TEXT), (x, y))
            text = entry.summary if unlocked else "Locked. Keep moving through the story to unlock it."
            self._draw_wrapped(surface, text, x, y + 44, settings.COLOR_TEXT)
        else:
            surface.blit(self.heading_font.render(entry.title, True, settings.COLOR_TEXT), (x, y))
            self._draw_wrapped(surface, entry.text, x, y + 44, settings.COLOR_TEXT)

    def _draw_wrapped(self, surface: pygame.Surface, text: str, x: int, y: int,
                      color: tuple[int, int, int]) -> int:
        """Draw wrapped text and return the y position below it."""
        for line in wrap_text(text, self.small_font, 400):
            surface.blit(self.small_font.render(line, True, color), (x, y))
            y += 22
        return y

    def _draw_mission(self, surface: pygame.Surface, mission: MissionDef, x: int, y: int) -> None:
        status = self.missions.status[mission.id]
        surface.blit(self.heading_font.render(mission.title, True, settings.COLOR_TEXT), (x, y))
        meta = f"{status.value}   |   " + ("MAIN STORY" if mission.category == "story" else "SIDE MISSION")
        if mission.chapter:
            meta += f"   |   CHAPTER {mission.chapter}"
        surface.blit(self.small_font.render(meta, True, STATUS_COLORS[status]), (x, y + 34))
        y = self._draw_wrapped(surface, mission.description, x, y + 62, settings.COLOR_TEXT) + 8

        surface.blit(self.small_font.render("OBJECTIVES", True, settings.COLOR_MUTED), (x, y))
        y += 24
        for index, objective in enumerate(mission.objectives):
            done = self.missions.is_objective_done(mission.id, index)
            progress = self.missions.progress_of(mission.id, index)
            count = f"  ({progress}/{objective.quantity})" if objective.quantity > 1 else ""
            color = settings.COLOR_SAFE if done else settings.COLOR_TEXT
            surface.blit(self.small_font.render(
                f"{'[X]' if done else '[  ]'} {objective.description}{count}", True, color), (x, y))
            y += 22

        parts = []
        if mission.rewards.xp:
            parts.append(f"{mission.rewards.xp} XP")
        parts += [f"{qty} {self.item_defs[item_id].name}"
                  for item_id, qty in mission.rewards.items.items()]
        y += 8
        surface.blit(self.small_font.render("REWARD: " + ", ".join(parts), True,
                     settings.COLOR_AMBER), (x, y))
        y += 30

        if status is MissionStatus.AVAILABLE:
            if not self.board_mode:
                note, color = "Accept missions at the safehouse mission board", settings.COLOR_MUTED
            elif len(self.missions.active()) >= settings.MAX_ACTIVE_MISSIONS:
                note, color = "Mission log is full", settings.COLOR_ACCENT
            else:
                note, color = "ENTER - accept mission", settings.COLOR_AMBER
            surface.blit(self.small_font.render(note, True, color), (x, y))
        elif mission.deadline_day is not None and status is MissionStatus.ACTIVE:
            surface.blit(self.small_font.render(
                f"Expires after day {mission.deadline_day}", True, settings.COLOR_ACCENT), (x, y))