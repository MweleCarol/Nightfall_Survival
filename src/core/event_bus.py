"""Tiny publish/subscribe bus so systems stay decoupled."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    """Systems `emit` events by name; interested systems `on` (subscribe)."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> None:
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Handler) -> None:
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        payload = data or {}
        for handler in list(self._handlers[event]):  # copy: handlers may unsubscribe
            try:
                handler(payload)
            except Exception:  # one bad subscriber must not break the others
                log.exception("Handler failed for event %s", event)