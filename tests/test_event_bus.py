from core.event_bus import EventBus, Events


def test_emit_calls_subscribed_handler():
    bus = EventBus()
    received: list[dict] = []
    bus.on(Events.ENEMY_DIED, received.append)
    bus.emit(Events.ENEMY_DIED, {"xp": 10})
    assert received == [{"xp": 10}]


def test_emit_without_payload_passes_empty_dict():
    bus = EventBus()
    received: list[dict] = []
    bus.on(Events.NIGHT_STARTED, received.append)
    bus.emit(Events.NIGHT_STARTED)
    assert received == [{}]


def test_multiple_handlers_all_called():
    bus = EventBus()
    calls: list[str] = []
    bus.on("X", lambda _: calls.append("a"))
    bus.on("X", lambda _: calls.append("b"))
    bus.emit("X")
    assert calls == ["a", "b"]


def test_off_removes_handler():
    bus = EventBus()
    received: list[dict] = []
    bus.on("X", received.append)
    bus.off("X", received.append)
    bus.emit("X", {"a": 1})
    assert received == []


def test_emit_with_no_subscribers_does_not_fail():
    EventBus().emit("NOBODY_LISTENING", {"a": 1})


def test_failing_handler_does_not_block_others():
    bus = EventBus()
    received: list[dict] = []

    def bad_handler(_: dict) -> None:
        raise RuntimeError("boom")

    bus.on("X", bad_handler)
    bus.on("X", received.append)
    bus.emit("X", {"ok": True})
    assert received == [{"ok": True}]