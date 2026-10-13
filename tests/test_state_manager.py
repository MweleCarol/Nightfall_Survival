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



class TransparentState(DummyState):
    transparent = True


def test_push_keeps_the_state_below_alive():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.push_state(DummyState("B", log))
    assert log == ["enter:A", "enter:B"]            # A was never exited
    log.clear()
    manager.update(0.1)
    assert log == ["update:B"]


def test_pop_returns_to_the_state_below():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.push_state(DummyState("B", log))
    manager.pop_state()
    assert log[-1] == "exit:B"
    log.clear()
    manager.update(0.1)
    assert log == ["update:A"]


def test_transparent_top_state_is_drawn_over_the_one_below():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.push_state(TransparentState("T", log))
    log.clear()
    manager.render(None)
    assert log == ["render:A", "render:T"]


def test_opaque_state_hides_the_ones_below_it():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.push_state(DummyState("B", log))
    manager.push_state(TransparentState("T", log))
    log.clear()
    manager.render(None)
    assert log == ["render:B", "render:T"]


def test_change_state_leaves_every_stacked_state():
    log: list[str] = []
    manager = StateManager()
    manager.change_state(DummyState("A", log))
    manager.push_state(DummyState("B", log))
    log.clear()
    manager.change_state(DummyState("C", log))
    assert log == ["exit:B", "exit:A", "enter:C"]
    assert manager.depth == 1


def test_pop_on_an_empty_stack_is_harmless():
    assert StateManager().pop_state() is None