from src.core.event_bus import EventBus


def test_subscriber_receives_payload():
    bus, got = EventBus(), []
    bus.on("X", got.append)
    bus.emit("X", {"a": 1})
    assert got == [{"a": 1}]


def test_off_unsubscribes():
    bus, got = EventBus(), []
    bus.on("X", got.append)
    bus.off("X", got.append)
    bus.emit("X", {"a": 1})
    assert got == []


def test_emit_without_subscribers_is_fine():
    EventBus().emit("NOBODY_LISTENS")


def test_bad_handler_does_not_block_others():
    bus, got = EventBus(), []

    def bad(_data):
        raise RuntimeError("boom")

    bus.on("X", bad)
    bus.on("X", got.append)
    bus.emit("X")
    assert got == [{}]