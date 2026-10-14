"""The in-game HUD, built from the design: vitals, objective, minimap, waves, radio, weapon."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame
from pygame import Vector2

from src.combat.weapon import Weapon
from src.core import settings
from src.player.stats import Stats
from src.ui import theme
from src.ui.kit import (
    cut_panel, draw_bar, draw_checkbox, draw_hud_icon, draw_item_icon, draw_keycap,
    fit_text, parse_prompt,
)
from src.ui.minimap import Minimap
from src.ui.widgets import render_tracked
from src.world.camera import Camera


@dataclass
class HudState:
    """Everything the HUD needs for one frame. PlayingState fills it in; the HUD only reads it."""
    stats: Stats
    weapon: Weapon
    camera: Camera
    level: int = 1
    xp: int = 0
    xp_needed: int = 100                  # 0 means max level
    cycle_label: str = "DAY 1"
    clock_text: str = "08:00"
    is_day: bool = True
    night: int = 1
    night_remaining: float = 0.0
    fps: float = 60.0
    mouse_pos: tuple[int, int] = (640, 360)
    player_position: Vector2 = field(default_factory=lambda: Vector2(0, 0))
    aim_direction: Vector2 = field(default_factory=lambda: Vector2(1, 0))
    enemies: list = field(default_factory=list)
    crates: list = field(default_factory=list)             # positions of unopened crates
    objective_marker: Vector2 | None = None
    mission_title: str | None = None
    objectives: list = field(default_factory=list)         # (text, done)
    wave_status: str | None = None                         # None, "countdown", "fighting", "cleared"
    wave_number: int = 0
    wave_total: int = 0
    wave_remaining: int = 0
    wave_countdown: int = 0
    prompt: str | None = None
    protected: bool = False
    truce_broken: bool = False
    quick_items: list = field(default_factory=list)        # (item_id, item_type, count)
    unread_radio: int = 0


class GameHUD:
    def __init__(self, assets=None, game_map=None) -> None:
        self.assets = assets
        self.tiny = self._font(12)
        self.small = self._font(14)
        self.font = self._font(16)
        self.title_font = self._font(18)
        self.clock_font = self._font(22)
        self.banner_font = self._font(26)
        self.ammo_font = self._font(34)
        self.notice_font = self._font(40)
        self.death_font = self._font(64)

        self._vitals_panel = cut_panel(322, 108)
        self._clock_panel = cut_panel(200, 56)
        self._wave_panel = cut_panel(360, 68, border=theme.RED)
        self._radio_panel = cut_panel(390, 58)
        self._prompt_panel = cut_panel(330, 44)
        self._weapon_panel = cut_panel(330, 92)
        self._slot_panel = cut_panel(64, 64)
        self._objective_panels: dict[tuple[int, bool], pygame.Surface] = {}
        self._minimap = Minimap(game_map, self.tiny) if game_map is not None else None

        self._notices: list[list] = []          # [text, seconds_remaining]
        self._radio: list | None = None         # [sender, text, seconds_remaining]
        self._portrait: pygame.Surface | None = None
        self._portrait_loaded = False
        self._gun_images: dict[str, pygame.Surface | None] = {}
        self._label_cache: dict[str, pygame.Surface] = {}

    def _font(self, size: int) -> pygame.font.Font:
        if self.assets is not None:
            return self.assets.font(size, bold=True)
        return pygame.font.SysFont("arial", size, bold=True)

    # ---- messages ----
    def notify(self, text: str, duration: float = 3.0) -> None:
        self._notices.append([text, duration])

    def show_radio(self, sender: str, text: str, duration: float = 7.0) -> None:
        self._radio = [sender, text, duration]

    def update(self, dt: float) -> None:
        for notice in self._notices:
            notice[1] -= dt
        self._notices = [n for n in self._notices if n[1] > 0]
        if self._radio is not None:
            self._radio[2] -= dt
            if self._radio[2] <= 0:
                self._radio = None

    # ---- drawing ----
    def draw(self, surface: pygame.Surface, state: HudState) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        self._draw_vitals(surface, state)
        self._draw_objective(surface, state)
        self._draw_clock(surface, state)
        if self._minimap is not None:
            enemies = [e.position for e in state.enemies if not e.is_dead]
            self._minimap.draw(surface, (w - 82, 94), state.player_position, state.aim_direction,
                               enemies, state.crates, state.objective_marker)
        self._draw_wave_banner(surface, state)
        self._draw_enemy_labels(surface, state)
        self._draw_radio(surface, state)
        self._draw_prompt(surface, state)
        self._draw_weapon(surface, state)
        self._draw_crosshair(surface, state)
        self._draw_notices(surface)

        hint = self.tiny.render("WASD move | SHIFT sprint | E interact | Q heal | TAB inventory | "
                                "K skills | M journal | ESC pause", True, theme.MUTED)
        surface.blit(hint, (14, h - 22))
        if state.stats.is_dead:
            message = self.death_font.render("YOU DIED", True, theme.RED)
            surface.blit(message, message.get_rect(center=(w // 2, h // 2)))

    def _draw_vitals(self, surface: pygame.Surface, state: HudState) -> None:
        stats = state.stats
        surface.blit(self._vitals_panel, (14, 12))
        self._draw_portrait(surface, pygame.Rect(24, 20, 62, 62))
        badge = pygame.Rect(22, 88, 66, 22)
        pygame.draw.rect(surface, theme.PANEL_DARK, badge)
        pygame.draw.rect(surface, theme.CYAN, badge, 1)
        level = self.small.render(f"LV  {state.level}", True, theme.TEXT)
        surface.blit(level, level.get_rect(center=badge.center))

        health_color = theme.RED
        if stats.health / stats.max_health < 0.3:                      # pulses when nearly dead
            pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.008)
            health_color = tuple(int(a + (b - a) * pulse) for a, b in zip(theme.RED, (255, 130, 110)))
        hp = pygame.Rect(124, 26, 200, 20)
        draw_hud_icon(surface, "heart", (108, 36), theme.RED, 16)
        draw_bar(surface, hp, stats.health / stats.max_health, health_color)
        self._bar_text(surface, f"{stats.health} / {stats.max_health}", hp)

        sta = pygame.Rect(124, 52, 200, 18)
        draw_hud_icon(surface, "bolt", (108, 61), theme.STAMINA, 16)
        draw_bar(surface, sta, stats.stamina / stats.max_stamina, theme.STAMINA)
        self._bar_text(surface, f"{stats.stamina:.0f} / {stats.max_stamina:.0f}", sta)

        xp = pygame.Rect(124, 82, 120, 8)
        draw_bar(surface, xp, state.xp / state.xp_needed if state.xp_needed else 1.0, theme.CYAN)
        label = f"{state.xp} / {state.xp_needed} XP" if state.xp_needed else "MAX LEVEL"
        text = self.tiny.render(label, True, theme.TEXT)
        surface.blit(text, text.get_rect(topright=(324, 78)))

    def _bar_text(self, surface: pygame.Surface, label: str, rect: pygame.Rect) -> None:
        text = self.small.render(label, True, theme.TEXT)
        surface.blit(text, (rect.x + 8, rect.y + (rect.height - text.get_height()) // 2))

    def _draw_portrait(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        if not self._portrait_loaded:
            self._portrait_loaded = True
            image = self.assets.image("ui/portrait.png") if self.assets is not None else None
            if image is not None:
                self._portrait = pygame.transform.smoothscale(image, rect.size)
        if self._portrait is not None:
            surface.blit(self._portrait, rect)
        else:                                                           # a simple placeholder bust
            surface.set_clip(rect)
            pygame.draw.rect(surface, (14, 22, 36), rect)
            cx, cy = rect.center
            pygame.draw.ellipse(surface, (40, 52, 70), (rect.x + 8, rect.bottom - 24, rect.width - 16, 34))
            pygame.draw.circle(surface, (176, 138, 108), (cx, cy + 2), 15)
            pygame.draw.rect(surface, (28, 34, 44), (cx - 17, cy - 20, 34, 14))
            pygame.draw.line(surface, (28, 34, 44), (cx - 4, cy - 8), (cx + 20, cy - 8), 4)
            surface.set_clip(None)
        pygame.draw.rect(surface, theme.CYAN, rect, 2)

    def _draw_objective(self, surface: pygame.Surface, state: HudState) -> None:
        night = not state.is_day
        rows = state.objectives[:4]
        key = (len(rows), night)
        panel = self._objective_panels.get(key)
        if panel is None:
            panel = cut_panel(300, 76 + 22 * len(rows), border=theme.RED if night else theme.CYAN)
            self._objective_panels[key] = panel
        x, y = 14, 128
        surface.blit(panel, (x, y))
        if night:
            draw_hud_icon(surface, "warning", (x + 22, y + 18), theme.RED, 18)
            head = f"NIGHT {state.night:02d}"
            if state.wave_status:
                head += f" - WAVE {state.wave_number:02d}"
            surface.blit(self.title_font.render(head, True, theme.RED), (x + 40, y + 8))
            minutes, seconds = divmod(int(state.night_remaining), 60)
            timer = self.title_font.render(f"{minutes:02d}:{seconds:02d}", True, theme.RED)
            surface.blit(timer, timer.get_rect(topright=(x + 288, y + 8)))
        else:
            draw_hud_icon(surface, "diamond", (x + 22, y + 18), theme.AMBER, 18)
            surface.blit(self.title_font.render("CURRENT OBJECTIVE", True, theme.AMBER), (x + 40, y + 8))
        title = state.mission_title or ("Survive the waves" if night else "Explore and scavenge")
        surface.blit(self.font.render(fit_text(title, 30), True, theme.TEXT), (x + 14, y + 40))
        for index, (text, done) in enumerate(rows):
            row_y = y + 70 + index * 22
            draw_checkbox(surface, pygame.Rect(x + 16, row_y + 2, 14, 14), done)
            color = theme.CYAN_BRIGHT if done else theme.TEXT
            surface.blit(self.small.render(fit_text(text, 34), True, color), (x + 40, row_y))

    def _draw_clock(self, surface: pygame.Surface, state: HudState) -> None:
        w = settings.SCREEN_WIDTH
        x, y = w - 372, 14
        surface.blit(self._clock_panel, (x, y))
        color = theme.AMBER if state.is_day else (150, 180, 235)
        draw_hud_icon(surface, "sun" if state.is_day else "moon", (x + 30, y + 28), color, 22)
        surface.blit(self.title_font.render(state.cycle_label, True, color), (x + 58, y + 8))
        surface.blit(self.clock_font.render(state.clock_text, True, theme.TEXT), (x + 58, y + 28))
        if state.truce_broken:
            surface.blit(self.small.render("TRUCE BROKEN", True, theme.RED), (x + 4, y + 62))
        elif state.protected:
            surface.blit(self.small.render("SAFE ZONE", True, settings.COLOR_SAFE), (x + 4, y + 62))
        fps = self.tiny.render(f"{state.fps:.0f} FPS", True, theme.MUTED)
        surface.blit(fps, fps.get_rect(topright=(x + 196, y + 64)))

    def _draw_wave_banner(self, surface: pygame.Surface, state: HudState) -> None:
        if state.wave_status is None:
            return
        x, y = settings.SCREEN_WIDTH // 2 - 180, 12
        surface.blit(self._wave_panel, (x, y))
        draw_hud_icon(surface, "skull", (x + 40, y + 34), theme.RED, 30)
        if state.wave_status == "cleared":
            title, sub = "NIGHT CLEARED", "HOLD UNTIL DAWN"
        elif state.wave_status == "countdown":
            title = f"WAVE {state.wave_number} / {state.wave_total}"
            sub = f"STARTS IN {state.wave_countdown}s"
        else:
            title = f"WAVE {state.wave_number} / {state.wave_total}"
            sub = f"ENEMIES REMAINING: {state.wave_remaining}"
        surface.blit(self.banner_font.render(title, True, theme.AMBER), (x + 78, y + 8))
        surface.blit(self.small.render(sub, True, theme.TEXT), (x + 78, y + 42))

    def _draw_enemy_labels(self, surface: pygame.Surface, state: HudState) -> None:
        width, height = surface.get_size()
        for enemy in state.enemies:
            if enemy.is_dead or enemy.health >= enemy.max_health or enemy.definition.type == "boss":
                continue
            screen = state.camera.world_to_screen(enemy.position)
            if not (0 <= screen.x <= width and 0 <= screen.y <= height):
                continue
            name = enemy.definition.name
            label = self._label_cache.get(name)
            if label is None:
                label = self.small.render(name, True, theme.TEXT)
                self._label_cache[name] = label
            surface.blit(label, label.get_rect(midbottom=(screen.x, screen.y - enemy.radius - 16)))

    def _draw_radio(self, surface: pygame.Surface, state: HudState) -> None:
        h = settings.SCREEN_HEIGHT
        if self._radio is not None:
            sender, text, _remaining = self._radio
            x, y = 14, h - 172
            surface.blit(self._radio_panel, (x, y))
            draw_hud_icon(surface, "radio", (x + 30, y + 29), theme.CYAN_BRIGHT, 24)
            surface.blit(self.tiny.render(sender, True, theme.CYAN_BRIGHT), (x + 60, y + 8))
            surface.blit(self.small.render(fit_text(text, 46), True, theme.TEXT), (x + 60, y + 28))
        elif state.unread_radio and (pygame.time.get_ticks() // 500) % 2 == 0:
            note = f"RADIO: {state.unread_radio} NEW - USE THE SAFEHOUSE RADIO"
            surface.blit(self.small.render(note, True, theme.AMBER), (20, h - 150))

    def _draw_prompt(self, surface: pygame.Surface, state: HudState) -> None:
        if not state.prompt:
            return
        x, y = 14, settings.SCREEN_HEIGHT - 104
        surface.blit(self._prompt_panel, (x, y))
        key, rest = parse_prompt(state.prompt)
        text_x = x + 16
        if key is not None:
            cap = draw_keycap(surface, self.small, key, (x + 14, y + 10))
            text_x = cap.right + 10
        surface.blit(self.font.render(fit_text(rest, 30), True, theme.TEXT), (text_x, y + 12))

    def _draw_weapon(self, surface: pygame.Surface, state: HudState) -> None:
        w, h = settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT
        weapon = state.weapon
        slots = state.quick_items[:4]
        slots_x = w - 14 - len(slots) * 68 + 4
        right_edge = slots_x - 8 if slots else w - 14
        x, y = right_edge - 330, h - 108
        surface.blit(self._weapon_panel, (x, y))

        self._draw_gun(surface, pygame.Rect(x + 12, y + 18, 96, 48), weapon.definition.id)
        surface.blit(self.tiny.render(weapon.definition.name.upper(), True, theme.MUTED), (x + 118, y + 10))
        empty = weapon.loaded == 0
        ammo = self.ammo_font.render(str(weapon.loaded), True, theme.RED if empty else theme.TEXT)
        surface.blit(ammo, (x + 118, y + 28))
        reserve = self.font.render(f"/ {weapon.reserve}", True, theme.MUTED)
        surface.blit(reserve, (x + 126 + ammo.get_width(), y + 44))
        draw_hud_icon(surface, "mag", (x + 304, y + 28), theme.CYAN_BRIGHT, 20)

        if weapon.is_reloading:
            bar = pygame.Rect(x + 12, y + 80, 306, 5)
            draw_bar(surface, bar, weapon.reload_progress, theme.AMBER)
            label, color = "RELOADING", theme.AMBER
        elif empty:
            label, color = ("RELOAD (R)", theme.RED) if weapon.reserve > 0 else ("NO AMMO", theme.RED)
        else:
            label = None
        if label:
            text = self.tiny.render(label, True, color)
            surface.blit(text, text.get_rect(topright=(x + 318, y + 66)))

        if slots:
            cap = draw_keycap(surface, self.tiny, "Q", (slots_x, y - 24))
            surface.blit(self.tiny.render("HEAL", True, theme.MUTED), (cap.right + 6, cap.y + 4))
        for index, (item_id, item_type, count) in enumerate(slots):
            sx = slots_x + index * 68
            surface.blit(self._slot_panel, (sx, y + 14))
            draw_item_icon(surface, self.assets, item_id, item_type, pygame.Rect(sx + 10, y + 20, 44, 44))
            if count == 0:                                              # none left: dim the slot
                dim = pygame.Surface((64, 64), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 140))
                surface.blit(dim, (sx, y + 14))
            text = self.small.render(str(count), True, theme.TEXT if count else theme.MUTED)
            surface.blit(text, text.get_rect(bottomright=(sx + 58, y + 74)))

    def _draw_gun(self, surface: pygame.Surface, rect: pygame.Rect, weapon_id: str) -> None:
        if weapon_id not in self._gun_images:
            image = self.assets.image(f"weapons/{weapon_id}.png") if self.assets is not None else None
            self._gun_images[weapon_id] = (
                pygame.transform.smoothscale(image, rect.size) if image is not None else None)
        image = self._gun_images[weapon_id]
        if image is not None:
            surface.blit(image, rect)
        else:
            draw_hud_icon(surface, "gun", rect.center, theme.ICON, 56)

    def _draw_crosshair(self, surface: pygame.Surface, state: HudState) -> None:
        x, y = state.mouse_pos
        gap, length, color = 6, 10, theme.TEXT
        pygame.draw.line(surface, color, (x - gap - length, y), (x - gap, y), 2)
        pygame.draw.line(surface, color, (x + gap, y), (x + gap + length, y), 2)
        pygame.draw.line(surface, color, (x, y - gap - length), (x, y - gap), 2)
        pygame.draw.line(surface, color, (x, y + gap), (x, y + gap + length), 2)
        pygame.draw.circle(surface, theme.RED, (x, y), 2)
        if state.weapon.is_reloading:                                   # a ring that fills while reloading
            ring = pygame.Rect(0, 0, 44, 44)
            ring.center = (x, y)
            pygame.draw.arc(surface, theme.AMBER, ring, math.pi / 2,
                            math.pi / 2 + 2 * math.pi * max(0.02, state.weapon.reload_progress), 3)

    def _draw_notices(self, surface: pygame.Surface) -> None:
        w = settings.SCREEN_WIDTH
        for index, (message, remaining) in enumerate(self._notices):
            alpha = int(255 * min(1.0, remaining / 0.8))               # fade out at the end
            shadow = render_tracked(message, self.notice_font, (0, 0, 0), 2)
            text = render_tracked(message, self.notice_font, theme.TEXT, 2)
            shadow.set_alpha(int(alpha * 0.7))
            text.set_alpha(alpha)
            center = (w // 2, 190 + index * 52)
            surface.blit(shadow, shadow.get_rect(center=(center[0] + 2, center[1] + 2)))
            surface.blit(text, text.get_rect(center=center))