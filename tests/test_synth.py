import math
from array import array

from src.audio import synth

RATE = 8000


def test_every_sound_renders_valid_audible_samples():
    for name in synth.SFX_NAMES:
        samples = synth.sfx_samples(name, RATE)
        assert samples and all(math.isfinite(x) for x in samples), name
        assert max(abs(x) for x in samples) > 0.02, name


def test_sounds_are_repeatable():
    assert synth.sfx_samples("shot", RATE) == synth.sfx_samples("shot", RATE)


def test_unknown_names_make_nothing():
    assert synth.sfx_samples("nope", RATE) is None
    assert synth.music_samples("nope", RATE) is None


def test_pcm_conversion_clips_and_duplicates_channels():
    data = array("h")
    data.frombytes(synth.to_pcm([2.0, -2.0, 0.0], channels=2))
    assert list(data) == [32767, 32767, -32767, -32767, 0, 0]


def test_music_loops_have_the_right_length_and_are_audible():
    for name in synth.MUSIC_NAMES:
        samples = synth.music_samples(name, 4000)
        assert len(samples) == int(4000 * synth.MUSIC_SECONDS), name
        assert 0.1 < max(abs(x) for x in samples) <= 1.0, name


def test_music_loops_start_and_end_close_together():
    for name in synth.MUSIC_NAMES:
        samples = synth.music_samples(name, RATE)
        assert abs(samples[0] - samples[-1]) < 0.2, name        # so the loop point does not click