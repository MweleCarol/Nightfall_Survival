from unittest.mock import MagicMock

import pytest

from core.game_state import GameState, StateId
from core.state_manager import StateManager


class RecordingState(GameState):
    """A fake state that records every call made to it."""

    def __init__(self, name: str, log: list[str]) -> None:
        super().__init__(game=None)  # type: ignore[arg-type]
        self.name = name
        self.log = log

    def enter(self) -> None:
        self.log.append(f"{self.name}:enter")

    def exit(self) -> None:
        self.log.append(f"{self.name}:exit")

    def handle_event(self, event) -> None:
        self.log.append(f"{self.name}:event")

    def update(self, dt: float) -> None:
        self.log.append(f"{self.name}:update:{dt}")

    def render(self, surface) -> None:
        self.log.append(f"{self.name}:render")


def make_manager() -> tuple[StateManager, list[str]]:
    log: list[str] = []
    manager = StateManager()
    manager.register(StateId.BOOT, RecordingState("boot", log))
    manager.register(StateId.MAIN_MENU, RecordingState("menu", log))
    return manager, log


def test_change_state_calls_enter():
    manager, log = make_manager()
    manager.change_state(StateId.BOOT)
    assert log == ["boot:enter"]


def test_change_state_exits_previous_state_first():
    manager, log = make_manager()
    manager.change_state(StateId.BOOT)
    manager.change_state(StateId.MAIN_MENU)
    assert log == ["boot:enter", "boot:exit", "menu:enter"]


def test_change_to_unknown_state_raises():
    manager, _ = make_manager()
    with pytest.raises(KeyError):
        manager.change_state(StateId.PLAYING)


def test_update_is_forwarded_to_current_state_only():
    manager, log = make_manager()
    manager.change_state(StateId.BOOT)
    log.clear()
    manager.update(0.5)
    assert log == ["boot:update:0.5"]


def test_events_are_forwarded_to_current_state():
    manager, log = make_manager()
    manager.change_state(StateId.BOOT)
    log.clear()
    manager.handle_events([MagicMock(), MagicMock()])
    assert log == ["boot:event", "boot:event"]


def test_update_and_render_without_state_are_safe():
    manager = StateManager()
    manager.update(0.016)
    manager.render(MagicMock())
    manager.handle_events([MagicMock()])


def test_current_id_tracks_active_state():
    manager, _ = make_manager()
    assert manager.current_id is None
    manager.change_state(StateId.MAIN_MENU)
    assert manager.current_id == StateId.MAIN_MENU