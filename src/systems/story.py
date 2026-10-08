"""Story state: chapters, radio transmissions and notes found (data-driven)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core import settings
from src.core.event_bus import EventBus
from src.services.data_loader import DataLoadError, load_json, require_field

TRIGGER_TYPES = ("game_start", "mission_started", "mission_completed", "night_started", "day_started")


@dataclass(frozen=True)
class Chapter:
    id: int
    title: str
    summary: str


@dataclass(frozen=True)
class RadioMessage:
    id: str
    sender: str
    text: str
    trigger_type: str
    trigger_value: str          # a mission id, or a night/day number as text ("" for game_start)


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class StoryData:
    chapters: dict[int, Chapter]
    messages: dict[str, RadioMessage]
    notes: dict[str, Note]

    @classmethod
    def from_dict(cls, data: dict, where: str) -> StoryData:
        chapters: dict[int, Chapter] = {}
        for index, raw in enumerate(require_field(data, "chapters", list, where)):
            chapter_where = f"{where}: chapters[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{chapter_where}: must be an object")
            chapter_id = require_field(raw, "id", int, chapter_where)
            if chapter_id < 1 or chapter_id in chapters:
                raise DataLoadError(f"{chapter_where}: 'id' must be a unique number >= 1")
            chapters[chapter_id] = Chapter(
                chapter_id, require_field(raw, "title", str, chapter_where),
                require_field(raw, "summary", str, chapter_where))

        messages: dict[str, RadioMessage] = {}
        for index, raw in enumerate(require_field(data, "radio_messages", list, where)):
            message_where = f"{where}: radio_messages[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{message_where}: must be an object")
            trigger = require_field(raw, "trigger", dict, message_where)
            trigger_type = require_field(trigger, "type", str, message_where + ".trigger")
            if trigger_type not in TRIGGER_TYPES:
                raise DataLoadError(
                    f"{message_where}: field 'trigger.type' must be one of {TRIGGER_TYPES}")
            value = ""
            if trigger_type in ("night_started", "day_started"):
                raw_value = trigger.get("value")
                if not isinstance(raw_value, int) or isinstance(raw_value, bool) or raw_value < 1:
                    raise DataLoadError(f"{message_where}: trigger 'value' must be a whole number >= 1")
                value = str(raw_value)
            elif trigger_type != "game_start":
                raw_value = trigger.get("value")
                if not isinstance(raw_value, str) or not raw_value:
                    raise DataLoadError(f"{message_where}: trigger 'value' must be a mission id")
                value = raw_value
            message_id = require_field(raw, "id", str, message_where)
            if message_id in messages:
                raise DataLoadError(f"{message_where}: duplicate id '{message_id}'")
            messages[message_id] = RadioMessage(
                message_id, require_field(raw, "sender", str, message_where),
                require_field(raw, "text", str, message_where), trigger_type, value)

        notes: dict[str, Note] = {}
        for index, raw in enumerate(require_field(data, "notes", list, where)):
            note_where = f"{where}: notes[{index}]"
            if not isinstance(raw, dict):
                raise DataLoadError(f"{note_where}: must be an object")
            note_id = require_field(raw, "id", str, note_where)
            if note_id in notes:
                raise DataLoadError(f"{note_where}: duplicate id '{note_id}'")
            notes[note_id] = Note(note_id, require_field(raw, "title", str, note_where),
                                  require_field(raw, "text", str, note_where))
        return cls(chapters, messages, notes)


def load_story_data(path: str = settings.STORY_FILE) -> StoryData:
    return StoryData.from_dict(load_json(path), path)


class StoryState:
    """What the player has unlocked, received and found. Reacts to game events."""

    def __init__(self, data: StoryData, event_bus: EventBus | None = None) -> None:
        self.data = data
        self.event_bus = event_bus
        first = min(data.chapters) if data.chapters else 1
        self.unlocked_chapters: set[int] = {first}
        self.inbox: list[str] = []              # received message ids, oldest first
        self.read_messages: set[str] = set()
        self.found_notes: list[str] = []

    @property
    def unread_count(self) -> int:
        return sum(1 for message_id in self.inbox if message_id not in self.read_messages)

    # ---- reactions ----
    def notify(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Receive any radio message whose trigger matches this event."""
        info = payload or {}
        for message in self.data.messages.values():
            if message.id not in self.inbox and self._is_triggered(message, event, info):
                self.receive(message.id)

    @staticmethod
    def _is_triggered(message: RadioMessage, event: str, info: dict[str, Any]) -> bool:
        kind, value = message.trigger_type, message.trigger_value
        if kind == "game_start":
            return event == "GAME_STARTED"
        if kind == "mission_started":
            return event == "MISSION_STARTED" and info.get("id") == value
        if kind == "mission_completed":
            return event == "MISSION_COMPLETED" and info.get("id") == value
        if kind == "night_started":
            return event == "NIGHT_STARTED" and info.get("night", 0) >= int(value)
        if kind == "day_started":
            return event == "DAY_STARTED" and info.get("day", 0) >= int(value)
        return False

    # ---- changes ----
    def receive(self, message_id: str) -> bool:
        if message_id not in self.data.messages or message_id in self.inbox:
            return False
        self.inbox.append(message_id)
        self._emit("RADIO_MESSAGE", {"id": message_id,
                                     "sender": self.data.messages[message_id].sender})
        return True

    def mark_read(self, message_id: str) -> None:
        if message_id in self.inbox:
            self.read_messages.add(message_id)

    def unlock_chapter(self, chapter_id: int) -> bool:
        if chapter_id not in self.data.chapters or chapter_id in self.unlocked_chapters:
            return False
        self.unlocked_chapters.add(chapter_id)
        self._emit("CHAPTER_UNLOCKED", {"chapter": chapter_id,
                                        "title": self.data.chapters[chapter_id].title})
        return True

    def add_note(self, note_id: str) -> bool:
        if note_id not in self.data.notes or note_id in self.found_notes:
            return False
        self.found_notes.append(note_id)
        return True

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self.event_bus is not None:
            self.event_bus.emit(event, payload)

    # ---- persistence (used by the save system in Milestone 10) ----
    def serialize(self) -> dict[str, Any]:
        return {"chapters": sorted(self.unlocked_chapters), "inbox": list(self.inbox),
                "read": sorted(self.read_messages), "notes": list(self.found_notes)}

    @classmethod
    def deserialize(cls, payload: dict[str, Any], data: StoryData,
                    event_bus: EventBus | None = None) -> StoryState:
        state = cls(data, event_bus)
        for chapter in payload.get("chapters", []):
            if isinstance(chapter, int) and not isinstance(chapter, bool) and chapter in data.chapters:
                state.unlocked_chapters.add(chapter)
        for message_id in payload.get("inbox", []):
            if isinstance(message_id, str) and message_id in data.messages \
                    and message_id not in state.inbox:
                state.inbox.append(message_id)
        for message_id in payload.get("read", []):
            if message_id in state.inbox:
                state.read_messages.add(message_id)
        for note_id in payload.get("notes", []):
            if isinstance(note_id, str) and note_id in data.notes and note_id not in state.found_notes:
                state.found_notes.append(note_id)
        return state