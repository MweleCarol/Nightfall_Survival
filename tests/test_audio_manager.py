import pygame
import pytest

from src.audio import synth
from src.audio.audio_manager import (
    TRACKS, AudioManager, MusicPlayer, NullBackend, distance_volume, music_for_phase,
)
from src.core import settings
from src.core.event_bus import EventBus


class FakeBackend:
    """Records what the manager asks for, so the tests need no sound card."""
    available = True

    def __init__(self, missing: bool = False):
        self.missing = missing
        self.loads, self.played, self.loops, self.stopped, self.closed = [], [], {}, [], False

    def load(self, name, kind):
        self.loads.append((name, kind))
        return None if self.missing else (name, kind)

    def play(self, handle, volume):
        self.played.append((handle[0], volume))

    def start_loop(self, layer, handle, volume):
        self.loops[layer] = (handle[0], volume)

    def set_layer_volume(self, layer, volume):
        self.loops[layer] = (self.loops[layer][0], volume)

    def stop_layer(self, layer):
        self.stopped.append(layer)
        self.loops.pop(layer, None)

    def shutdown(self):
        self.closed = True


def make(master=1.0, sfx=1.0, music=1.0, backend=None):
    bus, backend = EventBus(), backend or FakeBackend()
    return AudioManager(bus, backend, master, sfx, music), bus, backend


def names(backend) -> list[str]:
    return [name for name, _volume in backend.played]


def test_events_play_their_sounds():
    _audio, bus, backend = make()
    bus.emit("SHOT_FIRED", {"origin": (0, 0)})
    bus.emit("LEVEL_UP", {})
    assert names(backend) == ["shot", "level_up"]


def test_critical_hits_have_their_own_sound():
    audio, bus, backend = make()
    bus.emit("ENEMY_HIT", {"critical": False})
    audio.update(0.2)
    bus.emit("ENEMY_HIT", {"critical": True})
    assert names(backend) == ["hit", "critical"]


def test_rapid_repeats_are_limited_until_time_passes():
    audio, bus, backend = make()
    bus.emit("SHOT_FIRED", {})
    bus.emit("SHOT_FIRED", {})
    assert names(backend) == ["shot"]
    audio.update(0.2)
    bus.emit("SHOT_FIRED", {})
    assert names(backend) == ["shot", "shot"]


def test_volumes_scale_sound_effects():
    _audio, bus, backend = make(master=0.5, sfx=0.5)
    bus.emit("SHOT_FIRED", {})
    assert backend.played[0][1] == pytest.approx(0.25)


def test_distant_sounds_are_quieter_and_far_ones_are_silent():
    audio, bus, backend = make()
    audio.listener = (0.0, 0.0)
    for position in ((100, 0), (700, 0), (5000, 0)):
        bus.emit("ENEMY_DIED", {"position": position})
        audio.update(0.2)
    volumes = [volume for _name, volume in backend.played]
    assert len(volumes) == 2                                  # the far one never played
    assert volumes[0] == pytest.approx(1.0) and 0 < volumes[1] < volumes[0]
    assert distance_volume(settings.AUDIO_HEARING_RANGE) == 0.0


def test_missing_sounds_and_unknown_names_do_not_crash():
    audio, bus, backend = make(backend=FakeBackend(missing=True))
    bus.emit("SHOT_FIRED", {})
    audio.play("no_such_sound")
    assert backend.played == []


def test_a_silent_backend_is_safe():
    audio, bus, _backend = make(backend=NullBackend())
    for event in ("SHOT_FIRED", "NIGHT_STARTED", "BOSS_STARTED", "PLAYER_DIED"):
        bus.emit(event, {})
    audio.set_music("day")
    audio.update(1.0)
    audio.shutdown()


def test_music_follows_the_day_night_and_boss_events():
    audio, bus, _backend = make()
    expected = [("GAME_STARTED", "day"), ("NIGHT_STARTED", "night"), ("BOSS_STARTED", "boss"),
                ("BOSS_DEFEATED", "night"), ("DAY_STARTED", "day"), ("PLAYER_DIED", None)]
    for event, track in expected:
        bus.emit(event, {})
        assert audio.music.target == track, event


def test_ducking_lowers_the_music():
    audio, _bus, backend = make(master=1.0, music=0.5)
    audio.set_music("day")
    audio.update(10.0)
    assert backend.loops[1][1] == pytest.approx(0.5)
    audio.duck(True)
    audio.update(0.1)
    assert backend.loops[1][1] == pytest.approx(0.5 * settings.AUDIO_DUCK_FACTOR)
    audio.duck(False)
    audio.update(0.1)
    assert backend.loops[1][1] == pytest.approx(0.5)


def test_shutting_down_stops_listening():
    audio, bus, backend = make()
    audio.shutdown()
    bus.emit("SHOT_FIRED", {})
    assert backend.played == [] and backend.closed is True


def test_volumes_are_clamped():
    audio, _bus, _backend = make()
    audio.set_volumes(master=2.0, sfx=-1.0, music=0.3)
    assert (audio.master, audio.sfx_volume, audio.music_volume) == (1.0, 0.0, 0.3)


def test_a_new_track_fades_in_while_the_old_one_fades_out():
    backend = FakeBackend()
    player = MusicPlayer(backend, fade=2.0)
    player.set_target("day")
    player.update(1.0, 1.0)
    assert player.levels["day"] == pytest.approx(0.5) and backend.loops[1][1] == pytest.approx(0.5)
    player.set_target("night")
    player.update(1.0, 1.0)
    assert player.levels["day"] == 0.0 and 1 in backend.stopped      # the old track was switched off
    assert player.levels["night"] == pytest.approx(0.5) and backend.loops[2][0] == "night"


def test_boss_music_fades_in_faster():
    player = MusicPlayer(FakeBackend(), fade=2.0)
    player.set_target("boss")
    player.update(0.5, 1.0)
    assert player.levels["boss"] == pytest.approx(1.0)
    player.set_target("day")
    player.update(0.5, 1.0)
    assert player.levels["day"] == pytest.approx(0.25)


def test_no_target_fades_everything_out():
    backend = FakeBackend()
    player = MusicPlayer(backend, fade=1.0)
    player.set_target("day")
    player.update(1.0, 1.0)
    player.set_target(None)
    player.update(1.0, 1.0)
    assert backend.loops == {} and all(level == 0.0 for level in player.levels.values())


def test_a_missing_music_file_is_not_searched_for_every_frame():
    backend = FakeBackend(missing=True)
    player = MusicPlayer(backend)
    player.set_target("night")
    for _ in range(5):
        player.update(0.5, 1.0)
    assert backend.loads == [("night", "music")] and backend.loops == {}


def test_the_music_fits_the_moment():
    assert music_for_phase(False, False) == "day"
    assert music_for_phase(True, False) == "night"
    assert music_for_phase(True, True) == "boss"
    assert set(TRACKS) == set(synth.MUSIC_NAMES)


def test_create_gives_a_usable_manager_with_or_without_a_sound_card(monkeypatch, tmp_path):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")            # no real sound during the test
    pygame.mixer.quit()
    audio = AudioManager.create(EventBus(), tmp_path)
    audio.play("ui_confirm")
    audio.set_music("day")
    audio.update(0.1)
    audio.shutdown()
    pygame.mixer.quit()