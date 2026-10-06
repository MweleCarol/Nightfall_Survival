"""A tiny publish/subscribe event bus.

Systems announce *what happened* ("ENEMY_DIED") without knowing who cares.
Other systems (UI, XP, missions, audio) subscribe and react. This keeps
the modules decoupled.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.logger import get_logger

logger = get_logger(__name__)

Payload = dict[str, Any]
Handler = Callable[[Payload], None]


class Events:
    """Names of all game events (constants avoid typos in strings)."""

    PLAYER_DAMAGED = "PLAYER_DAMAGED"
    PLAYER_DIED = "PLAYER_DIED"
    ENEMY_DIED = "ENEMY_DIED"
    ITEM_PICKED = "ITEM_PICKED"
    XP_GAINED = "XP_GAINED"
    LEVEL_UP = "LEVEL_UP"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    NIGHT_STARTED = "NIGHT_STARTED"
    NIGHT_COMPLETED = "NIGHT_COMPLETED"
    WAVE_STARTED = "WAVE_STARTED"
    WAVE_COMPLETED = "WAVE_COMPLETED"
    BOSS_STARTED = "BOSS_STARTED"


class EventBus:
    """Register handlers with on(), announce events with emit()."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, event_name: str, handler: Handler) -> None:
        """Subscribe a handler to an event."""
        self._handlers.setdefault(event_name, []).append(handler)

    def off(self, event_name: str, handler: Handler) -> None:
        """Unsubscribe a handler (does nothing if it was never subscribed)."""
        handlers = self._handlers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event_name: str, payload: Payload | None = None) -> None:
        """Call every handler subscribed to event_name.

        A crashing handler is logged but never stops the other handlers.
        """
        data: Payload = payload if payload is not None else {}
        for handler in list(self._handlers.get(event_name, [])):
            try:
                handler(data)
            except Exception:
                logger.exception("Handler failed for event %s", event_name)