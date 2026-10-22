"""Plays sound effects and music in response to game events."""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Protocol

from src.core import settings
from src.core.event_bus import EventBus

log = logging.getLogger(__name__)

TRACKS = ("menu", "day", "night", "boss")          # each one gets its own mixer channel (its "layer")
FAST_FADE = {"boss": 0.5}                          # the boss track cuts in quickly
DEFAULT_INTERVAL = 0.03
MIN_INTERVAL = {"shot": 0.05, "shot_impact": 0.05, "hit": 0.05, "critical": 0.05, "zombie_death": 0.08,
                "empty_click": 0.25, "ui_move": 0.04, "pickup": 0.06, "search": 0.1, "explosion": 0.1}

# Which sound each game event plays. A key not listed here makes no sound.
EVENT_SOUNDS = {
    "SHOT_FIRED": "shot", "SHOT_IMPACT": "shot_impact", "ENEMY_HIT": "hit", "ENEMY_DIED": "zombie_death",
    "PLAYER_DAMAGED": "player_hurt", "PLAYER_DIED": "player_died", "GRENADE_THROWN": "grenade_throw",
    "GRENADE_EXPLODED": "explosion", "NIGHT_STARTED": "night_start", "DAY_STARTED": "day_start",
    "WAVE_STARTED": "wave_start", "WAVE_COMPLETED": "wave_clear", "LEVEL_UP": "level_up",
    "MISSION_STARTED": "mission_start", "MISSION_COMPLETED": "mission_complete",
    "MISSION_FAILED": "mission_failed", "BOSS_STARTED": "boss_start", "BOSS_PHASE_CHANGED": "boss_phase",
    "BOSS_STUNNED": "boss_stunned", "BOSS_DEFEATED": "boss_defeated", "ITEM_COLLECTED": "pickup",
    "CONTAINER_SEARCHED": "search", "RADIO_MESSAGE": "radio", "TRUCE_BROKEN": "truce_broken",
    "CHAPTER_UNLOCKED": "chapter", "RELOAD_STARTED": "reload", "WEAPON_EMPTY": "empty_click",
    "ITEM_USED": "heal", "ITEM_CRAFTED": "craft", "ITEM_EQUIPPED": "equip", "UI_OPEN": "ui_open",
    "UI_CLOSE": "ui_close", "UI_TAB": "ui_tab", "UI_CONFIRM": "ui_confirm", "UI_DENY": "ui_deny",
}
MUSIC_EVENTS = ("GAME_STARTED", "NIGHT_STARTED", "DAY_STARTED", "BOSS_STARTED", "BOSS_DEFEATED", "PLAYER_DIED")


# ---------------------------------------------------------------- pure helpers
def music_for_phase(is_night: bool, boss_active: bool) -> str:
    """Which track fits the moment: the boss beats the night, which beats the day."""
    if boss_active:
        return "boss"
    return "night" if is_night else "day"


def distance_volume(distance: float, full: float = settings.AUDIO_HEARING_FULL,
                    silent: float = settings.AUDIO_HEARING_RANGE) -> float:
    """1.0 close by, fading in a straight line to 0.0 at the edge of hearing."""
    if distance <= full:
        return 1.0
    return max(0.0, 1.0 - (distance - full) / (silent - full))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------- backends
class SoundBackend(Protocol):
    available: bool

    def load(self, name: str, kind: str) -> Any: ...
    def play(self, handle: Any, volume: float) -> None: ...
    def start_loop(self, layer: int, handle: Any, volume: float) -> None: ...
    def set_layer_volume(self, layer: int, volume: float) -> None: ...
    def stop_layer(self, layer: int) -> None: ...
    def shutdown(self) -> None: ...


class NullBackend:
    """Used when there is no audio device: every call quietly does nothing."""
    available = False

    def load(self, name: str, kind: str) -> Any:
        return None

    def play(self, handle: Any, volume: float) -> None:
        pass

    def start_loop(self, layer: int, handle: Any, volume: float) -> None:
        pass

    def set_layer_volume(self, layer: int, volume: float) -> None:
        pass

    def stop_layer(self, layer: int) -> None:
        pass

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------- music
class MusicPlayer:
    """Crossfades between looping tracks. The AudioManager sets a target; update() does the fading."""

    def __init__(self, backend: SoundBackend, fade: float = settings.AUDIO_MUSIC_FADE) -> None:
        self.backend = backend
        self.fade = fade
        self.target: str | None = None
        self.levels = {track: 0.0 for track in TRACKS}      # how far each track is faded in (0..1)
        self._started: set[str] = set()
        self._handles: dict[str, Any] = {}

    def set_target(self, track: str | None) -> None:
        if track is None or track in TRACKS:
            self.target = track

    def _handle(self, track: str) -> Any:
        if track not in self._handles:                       # loaded once; a missing track is remembered
            self._handles[track] = self.backend.load(track, "music")
        return self._handles[track]

    def update(self, dt: float, gain: float) -> None:
        for layer, track in enumerate(TRACKS):
            goal = 1.0 if track == self.target else 0.0
            level = self.levels[track]
            if level != goal:
                step = dt / FAST_FADE.get(track, self.fade)
                level = min(goal, level + step) if level < goal else max(goal, level - step)
                self.levels[track] = level
            if level > 0.0:
                if track in self._started:
                    self.backend.set_layer_volume(layer, level * gain)
                else:
                    handle = self._handle(track)
                    if handle is not None:
                        self.backend.start_loop(layer, handle, level * gain)
                        self._started.add(track)
            elif track in self._started:
                self.backend.stop_layer(layer)
                self._started.discard(track)


# ---------------------------------------------------------------- the manager
class AudioManager:
    def __init__(self, event_bus: EventBus, backend: SoundBackend,
                 master: float = settings.AUDIO_MASTER_VOLUME, sfx: float = settings.AUDIO_SFX_VOLUME,
                 music: float = settings.AUDIO_MUSIC_VOLUME) -> None:
        self.event_bus = event_bus
        self.backend = backend
        self.master, self.sfx_volume, self.music_volume = _clamp(master), _clamp(sfx), _clamp(music)
        self.listener: tuple[float, float] | None = None     # where the player is, for distance volume
        self.clock = 0.0
        self.music = MusicPlayer(backend)
        self.is_night = False
        self.boss_active = False
        self._ducked = False
        self._last_played: dict[str, float] = {}
        self._handles: dict[str, Any] = {}
        self._subscriptions: list[tuple[str, Any]] = []
        for event in set(EVENT_SOUNDS) | set(MUSIC_EVENTS):
            handler = self._make_handler(event)
            self.event_bus.on(event, handler)
            self._subscriptions.append((event, handler))

    @classmethod
    def create(cls, event_bus: EventBus, assets_root: Path) -> AudioManager:
        """A manager with real audio if the machine has it, else a silent one. Never raises."""
        backend: SoundBackend = NullBackend()
        if settings.AUDIO_ENABLED:
            try:
                from src.audio.pygame_backend import PygameBackend
                backend = PygameBackend(assets_root / "audio")
            except Exception as error:                       # no sound card, bad driver, ...
                log.warning("Audio is off: %s", error)
        return cls(event_bus, backend)

    # ---- volumes and music ----
    def set_volumes(self, master: float | None = None, sfx: float | None = None,
                    music: float | None = None) -> None:
        if master is not None:
            self.master = _clamp(master)
        if sfx is not None:
            self.sfx_volume = _clamp(sfx)
        if music is not None:
            self.music_volume = _clamp(music)

    def set_music(self, track: str | None) -> None:
        self.music.set_target(track)

    def duck(self, on: bool) -> None:
        """Turn the music down (while paused) or back up."""
        self._ducked = on

    # ---- sound effects ----
    def play(self, name: str, gain: float = 1.0) -> None:
        if not self.backend.available or gain <= 0.0:
            return
        last = self._last_played.get(name)
        if last is not None and self.clock - last < MIN_INTERVAL.get(name, DEFAULT_INTERVAL):
            return                                           # too soon after the same sound
        if name not in self._handles:
            self._handles[name] = self.backend.load(name, "sfx")
        handle = self._handles[name]
        if handle is None:
            return
        self._last_played[name] = self.clock
        self.backend.play(handle, _clamp(gain * self.sfx_volume * self.master))

    # ---- events ----
    def _make_handler(self, event: str):
        def handler(data: dict | None = None) -> None:
            self._on_event(event, data or {})
        return handler

    def _on_event(self, event: str, data: dict) -> None:
        self._follow_music(event)
        name = "critical" if (event == "ENEMY_HIT" and data.get("critical")) else EVENT_SOUNDS.get(event)
        if name is not None:
            self.play(name, self._distance_gain(data))

    def _follow_music(self, event: str) -> None:
        if event == "PLAYER_DIED":
            self.music.set_target(None)
            return
        if event == "GAME_STARTED":
            self.is_night = self.boss_active = False
        elif event == "NIGHT_STARTED":
            self.is_night = True
        elif event == "DAY_STARTED":
            self.is_night = False
        elif event == "BOSS_STARTED":
            self.boss_active = True
        elif event == "BOSS_DEFEATED":
            self.boss_active = False
        else:
            return
        self.music.set_target(music_for_phase(self.is_night, self.boss_active))

    def _distance_gain(self, data: dict) -> float:
        position = data.get("position")
        if self.listener is None or position is None:
            return 1.0
        try:
            distance = math.hypot(position[0] - self.listener[0], position[1] - self.listener[1])
        except (TypeError, IndexError):
            return 1.0
        return distance_volume(distance)

    # ---- every frame, and shutting down ----
    def update(self, dt: float) -> None:
        self.clock += dt
        gain = self.master * self.music_volume * (settings.AUDIO_DUCK_FACTOR if self._ducked else 1.0)
        self.music.update(dt, gain)

    def shutdown(self) -> None:
        for event, handler in self._subscriptions:
            self.event_bus.off(event, handler)
        self._subscriptions.clear()
        self.backend.shutdown()