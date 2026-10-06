from src.core.game_state import GameState
from src.core.state_manager import StateManager


class DummyState(GameState):
    """A fake screen that records which methods were called."""

    def __init__(self, name: str, log: list[str]) -> None:
        super().__init__(game=None)
        self.name = name
        self.log = log

    def enter(self) -> None:
        self.log.append(f"enter:{self.name}")

    def exit(self) -> None:
        self.log.append(f"exit:{self.name}")

    def handle_event(self, event) -> None:
        self.log.append(f"event:{self.name}")

    def update(self, dt: float) -> None:
        self.log.append(f"update:{self.name}")

    def render(self, surface) -> None:
        self.log.append(f"render:{self.name}")


def test_change_state_exits_old_then_enters_new():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.change_state(DummyState("B", log))
    assert log == ["enter:A", "exit:A", "enter:B"]


def test_only_current_state_is_updated_and_rendered():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.change_state(DummyState("B", log))
    log.clear()
    manager.update(0.016)
    manager.render(None)
    manager.handle_events([object()])
    assert log == ["update:B", "render:B", "event:B"]


def test_manager_with_no_state_does_not_crash():
    manager = StateManager()
    manager.update(0.016)
    manager.render(None)
    manager.handle_events([object()])