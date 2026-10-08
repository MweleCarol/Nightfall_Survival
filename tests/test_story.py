import pytest

from src.core.event_bus import EventBus
from src.services.data_loader import DataLoadError
from src.systems.story import Chapter, Note, RadioMessage, StoryData, StoryState, load_story_data


def make_data() -> StoryData:
    chapters = {1: Chapter(1, "One", "first"), 2: Chapter(2, "Two", "second")}
    messages = {
        "hello": RadioMessage("hello", "SRC", "hi", "game_start", ""),
        "done_a": RadioMessage("done_a", "SRC", "a done", "mission_completed", "a"),
        "night2": RadioMessage("night2", "SRC", "n2", "night_started", "2"),
        "day3": RadioMessage("day3", "SRC", "d3", "day_started", "3"),
    }
    notes = {"n1": Note("n1", "Note", "text")}
    return StoryData(chapters, messages, notes)


def make_state(bus=None) -> StoryState:
    return StoryState(make_data(), bus)


def raw_story(**overrides) -> dict:
    data = {"chapters": [{"id": 1, "title": "T", "summary": "S"}],
            "radio_messages": [{"id": "m", "sender": "X", "text": "t",
                                "trigger": {"type": "game_start"}}],
            "notes": [{"id": "n", "title": "T", "text": "x"}]}
    data.update(overrides)
    return data


def test_first_chapter_is_unlocked_and_others_unlock_once():
    bus, events = EventBus(), []
    bus.on("CHAPTER_UNLOCKED", events.append)
    story = make_state(bus)
    assert story.unlocked_chapters == {1}
    assert story.unlock_chapter(2) is True
    assert story.unlock_chapter(2) is False
    assert story.unlock_chapter(9) is False
    assert events == [{"chapter": 2, "title": "Two"}]


def test_game_start_message_arrives_only_once():
    bus, got = EventBus(), []
    bus.on("RADIO_MESSAGE", got.append)
    story = make_state(bus)
    story.notify("GAME_STARTED", {})
    story.notify("GAME_STARTED", {})
    assert story.inbox == ["hello"]
    assert got == [{"id": "hello", "sender": "SRC"}]


def test_mission_completed_trigger_matches_only_its_mission():
    story = make_state()
    story.notify("MISSION_COMPLETED", {"id": "zzz"})
    assert story.inbox == []
    story.notify("MISSION_COMPLETED", {"id": "a"})
    assert story.inbox == ["done_a"]


def test_night_and_day_triggers_mean_at_least():
    story = make_state()
    story.notify("NIGHT_STARTED", {"night": 1})
    story.notify("DAY_STARTED", {"day": 2})
    assert story.inbox == []
    story.notify("NIGHT_STARTED", {"night": 5})
    story.notify("DAY_STARTED", {"day": 3})
    assert set(story.inbox) == {"night2", "day3"}


def test_unread_count_and_mark_read():
    story = make_state()
    story.receive("hello")
    story.receive("done_a")
    assert story.unread_count == 2
    story.mark_read("hello")
    story.mark_read("ghost")                      # harmless
    assert story.unread_count == 1
    assert story.receive("ghost") is False


def test_notes_are_added_once():
    story = make_state()
    assert story.add_note("n1") is True
    assert story.add_note("n1") is False
    assert story.add_note("ghost") is False
    assert story.found_notes == ["n1"]


def test_serialize_round_trip():
    story = make_state()
    story.unlock_chapter(2)
    story.receive("hello")
    story.mark_read("hello")
    story.add_note("n1")
    clone = StoryState.deserialize(story.serialize(), make_data())
    assert clone.unlocked_chapters == {1, 2} and clone.inbox == ["hello"]
    assert clone.unread_count == 0 and clone.found_notes == ["n1"]


def test_deserialize_ignores_garbage():
    clone = StoryState.deserialize(
        {"chapters": [99, "x"], "inbox": ["ghost"], "read": [1], "notes": ["ghost"]}, make_data())
    assert clone.unlocked_chapters == {1}
    assert clone.inbox == [] and clone.found_notes == []


def test_invalid_trigger_type_is_rejected():
    data = raw_story(radio_messages=[{"id": "m", "sender": "X", "text": "t",
                                      "trigger": {"type": "dance"}}])
    with pytest.raises(DataLoadError, match="trigger"):
        StoryData.from_dict(data, "test")


def test_night_trigger_needs_a_number():
    data = raw_story(radio_messages=[{"id": "m", "sender": "X", "text": "t",
                                      "trigger": {"type": "night_started", "value": "soon"}}])
    with pytest.raises(DataLoadError, match="value"):
        StoryData.from_dict(data, "test")


def test_shipped_story_data_loads():
    data = load_story_data()
    assert len(data.chapters) >= 4 and data.messages and data.notes