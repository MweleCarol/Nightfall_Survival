"""Placeholder sounds made from maths, so the game has audio before you add real files.

Everything is built as a list of floats between -1 and 1 at a given sample rate. Real files in
assets/audio/ replace these by name (see PygameBackend.load).
"""
from __future__ import annotations

import math
import random
from array import array
from typing import Callable

MUSIC_SECONDS = 6.0
TWO_PI = 2.0 * math.pi


class Synth:
    """Builds sounds. A fixed seed makes every sound come out the same each time."""

    def __init__(self, rate: int, seed: int = 7) -> None:
        self.rate = rate
        self.rng = random.Random(seed)

    def _count(self, seconds: float) -> int:
        return max(1, int(self.rate * seconds))

    def tone(self, freq: float, seconds: float, volume: float = 0.5, wave: str = "sine",
             attack: float = 0.004, decay: float = 6.0, slide: float | None = None) -> list[float]:
        """A pitched sound. `slide` is the pitch it glides to; `decay` is how fast it fades."""
        n = self._count(seconds)
        end = freq if slide is None else slide
        out = [0.0] * n
        phase = 0.0
        for i in range(n):
            phase += (freq + (end - freq) * (i / n)) / self.rate
            frac = phase - math.floor(phase)
            if wave == "sine":
                value = math.sin(TWO_PI * phase)
            elif wave == "square":
                value = 1.0 if frac < 0.5 else -1.0
            elif wave == "saw":
                value = 2.0 * frac - 1.0
            else:                                           # triangle
                value = 4.0 * abs(frac - 0.5) - 1.0
            time = i / self.rate
            envelope = (min(1.0, time / attack) if attack > 0 else 1.0) * math.exp(-decay * time)
            out[i] = value * envelope * volume
        return out

    def noise(self, seconds: float, volume: float = 0.5, decay: float = 20.0,
              attack: float = 0.0, smooth: float = 0.0) -> list[float]:
        """Hiss. `smooth` near 1 makes it a dull rumble instead of a sharp crack."""
        n = self._count(seconds)
        gain = 1.0 / max(0.15, 1.0 - smooth) ** 0.5
        out = [0.0] * n
        last = 0.0
        for i in range(n):
            last = last * smooth + self.rng.uniform(-1.0, 1.0) * (1.0 - smooth)
            time = i / self.rate
            envelope = (min(1.0, time / attack) if attack > 0 else 1.0) * math.exp(-decay * time)
            out[i] = last * gain * envelope * volume
        return out

    @staticmethod
    def mix(*tracks: list[float]) -> list[float]:
        length = max(len(track) for track in tracks)
        out = [0.0] * length
        for track in tracks:
            for i, value in enumerate(track):
                out[i] += value
        return out

    def after(self, track: list[float], seconds: float) -> list[float]:
        """The same sound, starting a little later."""
        return [0.0] * int(self.rate * seconds) + track

    # ---- music building blocks ----
    def pad(self, notes: list[tuple[float, float]], seconds: float, swell: int = 1) -> list[float]:
        """Sustained sine notes. Each fits a whole number of cycles in the loop, so it repeats cleanly."""
        n = self._count(seconds)
        total = n / self.rate
        states, steps, amps = [], [], []
        for freq, amp in notes:
            fitted = max(1, round(freq * total)) / total
            angle = TWO_PI * fitted / self.rate
            states.append(complex(1.0, 0.0))
            steps.append(complex(math.cos(angle), math.sin(angle)))
            amps.append(amp)
        out = [0.0] * n
        for i in range(n):
            value = 0.0
            for k in range(len(states)):
                states[k] *= steps[k]
                value += states[k].imag * amps[k]
            out[i] = value * (0.8 + 0.2 * math.sin(TWO_PI * swell * i / n))
            if i % 4096 == 4095:                            # stop tiny rounding errors building up
                states = [z / abs(z) for z in states]
        return out

    def pulses(self, hits: list[tuple[float, float]], seconds: float, volume: float,
               decay: float, length: float = 0.6) -> list[float]:
        """Short decaying notes (bells, drum hits) placed at (time, pitch). Tails wrap round the loop."""
        n = self._count(seconds)
        out = [0.0] * n
        burst = int(self.rate * length)
        for when, freq in hits:
            start = int(when * self.rate)
            for j in range(burst):
                tau = j / self.rate
                out[(start + j) % n] += math.sin(TWO_PI * freq * tau) * math.exp(-decay * tau) * volume
        return out


def to_pcm(samples: list[float], channels: int = 1) -> bytes:
    """16-bit signed PCM, the format the mixer plays. Values beyond -1..1 are clipped."""
    data = array("h")
    for sample in samples:
        value = int(max(-1.0, min(1.0, sample)) * 32767)
        for _ in range(channels):
            data.append(value)
    return data.tobytes()


def _normalise(samples: list[float], peak: float = 0.8) -> list[float]:
    top = max((abs(x) for x in samples), default=0.0)
    return samples if top == 0 else [x * peak / top for x in samples]


# ---------------------------------------------------------------- sound effects
def _click(s: Synth, freq: float = 1200.0, volume: float = 0.4) -> list[float]:
    return s.mix(s.noise(0.02, volume, 120.0), s.tone(freq, 0.02, volume * 0.6, decay=80.0))


def _hit(s: Synth) -> list[float]:
    return s.mix(s.noise(0.08, 0.5, 50.0, smooth=0.6), s.tone(180, 0.1, 0.5, slide=70, decay=25.0))


def _explosion(s: Synth) -> list[float]:
    return s.mix(s.noise(1.3, 0.9, 3.2, smooth=0.75), s.tone(70, 1.0, 0.8, slide=28, decay=3.0),
                 s.noise(0.1, 0.8, 40.0))


def _chord(s: Synth, freqs: tuple[float, ...], seconds: float, volume: float) -> list[float]:
    return s.mix(*[s.tone(f, seconds, volume, "triangle", decay=3.0) for f in freqs])


SFX: dict[str, Callable[[Synth], list[float]]] = {
    "shot": lambda s: s.mix(s.noise(0.14, 0.85, 38.0), s.tone(150, 0.12, 0.7, slide=55, decay=18.0)),
    "shot_impact": lambda s: s.mix(s.noise(0.07, 0.45, 70.0, smooth=0.5),
                                   s.tone(300, 0.05, 0.2, slide=120, decay=40.0)),
    "hit": _hit,
    "critical": lambda s: s.mix(_hit(s), s.tone(900, 0.12, 0.3, "triangle", decay=22.0)),
    "zombie_death": lambda s: s.mix(s.tone(120, 0.55, 0.5, "saw", slide=40, decay=5.0),
                                    s.noise(0.35, 0.25, 9.0, smooth=0.8)),
    "player_hurt": lambda s: s.mix(s.tone(210, 0.22, 0.4, "square", slide=110, decay=10.0),
                                   s.noise(0.12, 0.3, 30.0, smooth=0.5)),
    "player_died": lambda s: s.mix(s.tone(220, 1.3, 0.5, "saw", slide=35, decay=2.2),
                                   s.noise(0.8, 0.2, 4.0, smooth=0.9)),
    "grenade_throw": lambda s: s.noise(0.22, 0.35, 8.0, attack=0.08, smooth=0.85),
    "explosion": _explosion,
    "reload": lambda s: s.mix(_click(s, 700.0), s.after(_click(s, 1000.0), 0.3)),
    "empty_click": lambda s: _click(s, 500.0, 0.3),
    "pickup": lambda s: s.mix(s.tone(660, 0.07, 0.4, decay=18.0), s.after(s.tone(880, 0.1, 0.4, decay=14.0), 0.06)),
    "heal": lambda s: s.mix(s.tone(440, 0.3, 0.4, "triangle", slide=880, decay=3.0),
                            s.after(s.tone(880, 0.2, 0.25, "triangle", decay=8.0), 0.15)),
    "craft": lambda s: s.mix(_click(s, 800.0), s.after(s.tone(988, 0.15, 0.3, decay=9.0), 0.05)),
    "equip": lambda s: s.mix(_click(s, 500.0), s.after(_click(s, 650.0), 0.06)),
    "search": lambda s: s.mix(s.noise(0.25, 0.35, 6.0, attack=0.05, smooth=0.5), s.after(_click(s, 600.0), 0.2)),
    "level_up": lambda s: s.mix(*[s.after(s.tone(f, 0.25, 0.35, "triangle", decay=7.0), k * 0.09)
                                  for k, f in enumerate((523.25, 659.25, 783.99, 1046.5))]),
    "mission_start": lambda s: s.mix(s.tone(440, 0.15, 0.35, decay=8.0), s.after(s.tone(660, 0.25, 0.35, decay=6.0), 0.12)),
    "mission_complete": lambda s: s.mix(_chord(s, (523.25, 659.25, 783.99), 0.7, 0.28),
                                        s.after(_chord(s, (659.25, 783.99, 1046.5), 0.8, 0.25), 0.25)),
    "mission_failed": lambda s: s.mix(s.tone(330, 0.3, 0.4, "triangle", decay=5.0),
                                      s.after(s.tone(247, 0.5, 0.4, "triangle", decay=4.0), 0.25)),
    "radio": lambda s: s.mix(*[s.after(s.tone(1000, 0.06, 0.25, "square", decay=10.0), k * 0.11) for k in range(3)],
                             s.noise(0.4, 0.1, 5.0, smooth=0.2)),
    "night_start": lambda s: s.mix(s.tone(110, 1.6, 0.5, "saw", attack=0.4, decay=1.2),
                                   s.tone(165, 1.6, 0.3, "saw", attack=0.4, decay=1.2)),
    "day_start": lambda s: s.mix(*[s.after(s.tone(f, 0.4, 0.3, "triangle", decay=5.0), k * 0.12)
                                   for k, f in enumerate((392.0, 523.25, 659.25))]),
    "wave_start": lambda s: s.mix(s.tone(90, 0.25, 0.8, slide=45, decay=14.0), s.noise(0.1, 0.3, 40.0),
                                  s.after(s.tone(90, 0.25, 0.7, slide=45, decay=14.0), 0.22)),
    "wave_clear": lambda s: s.mix(*[s.after(s.tone(f, 0.25, 0.3, "triangle", decay=6.0), k * 0.14)
                                    for k, f in enumerate((392.0, 494.0, 587.0))]),
    "boss_start": lambda s: s.mix(s.tone(60, 1.8, 0.6, "saw", attack=0.3, decay=1.0),
                                  s.tone(63, 1.8, 0.4, "saw", attack=0.3, decay=1.0),
                                  s.noise(1.6, 0.5, 1.5, attack=0.3, smooth=0.9)),
    "boss_phase": lambda s: s.mix(s.noise(0.6, 0.6, 5.0, smooth=0.8), s.tone(80, 0.6, 0.6, slide=40, decay=4.0),
                                  s.tone(300, 0.1, 0.3, "square", decay=20.0)),
    "boss_stunned": lambda s: s.mix(s.tone(1200, 0.5, 0.3, decay=6.0), s.tone(1212, 0.5, 0.3, decay=6.0)),
    "boss_defeated": lambda s: s.mix(_explosion(s), s.after(_chord(s, (261.6, 329.6, 392.0), 1.2, 0.3), 0.6)),
    "chapter": lambda s: s.mix(s.tone(880, 0.6, 0.4, decay=4.0), s.tone(1320, 0.6, 0.15, decay=4.0)),
    "truce_broken": lambda s: s.mix(*[s.after(s.tone(f, 0.12, 0.3, "square", decay=8.0), k * 0.14)
                                      for k, f in enumerate((880.0, 660.0, 880.0, 660.0))]),
    "ui_move": lambda s: s.tone(900, 0.03, 0.25, decay=60.0),
    "ui_confirm": lambda s: s.mix(s.tone(700, 0.05, 0.3, decay=30.0), s.after(s.tone(1050, 0.08, 0.3, decay=25.0), 0.05)),
    "ui_deny": lambda s: s.tone(160, 0.12, 0.3, "square", decay=14.0),
    "ui_open": lambda s: s.tone(300, 0.12, 0.3, "triangle", slide=700, decay=8.0),
    "ui_close": lambda s: s.tone(700, 0.12, 0.3, "triangle", slide=300, decay=8.0),
    "ui_tab": lambda s: s.tone(800, 0.03, 0.25, decay=50.0),
}
SFX_NAMES = tuple(SFX)


# ---------------------------------------------------------------- music loops
def _menu(s: Synth) -> list[float]:
    pad = s.pad([(110.0, 0.25), (164.8, 0.2), (220.0, 0.2), (261.6, 0.12), (329.6, 0.08)], MUSIC_SECONDS, swell=1)
    bells = s.pulses([(0.0, 440.0), (1.5, 523.3), (3.0, 659.3), (4.5, 523.3)], MUSIC_SECONDS, 0.18, 2.5)
    return s.mix(pad, bells)


def _day(s: Synth) -> list[float]:
    pad = s.pad([(130.8, 0.22), (196.0, 0.18), (261.6, 0.16), (329.6, 0.1), (392.0, 0.06)], MUSIC_SECONDS, swell=2)
    bells = s.pulses([(0.0, 523.3), (3.0, 392.0)], MUSIC_SECONDS, 0.12, 2.0)
    return s.mix(pad, bells)


def _night(s: Synth) -> list[float]:
    pad = s.pad([(55.0, 0.35), (82.4, 0.25), (110.0, 0.18), (116.5, 0.1)], MUSIC_SECONDS, swell=1)
    beat = s.pulses([(0.0, 55.0), (0.35, 55.0), (2.0, 55.0), (2.35, 55.0), (4.0, 55.0), (4.35, 55.0)],
                    MUSIC_SECONDS, 0.5, 9.0, 0.5)
    return s.mix(pad, beat)


def _boss(s: Synth) -> list[float]:
    pad = s.pad([(73.4, 0.3), (110.0, 0.22), (146.8, 0.18), (155.6, 0.12)], MUSIC_SECONDS, swell=3)
    drums = s.pulses([(k * 0.5, 60.0) for k in range(12)], MUSIC_SECONDS, 0.6, 10.0, 0.4)
    return s.mix(pad, drums)


MUSIC: dict[str, Callable[[Synth], list[float]]] = {"menu": _menu, "day": _day, "night": _night, "boss": _boss}
MUSIC_NAMES = tuple(MUSIC)


def sfx_samples(name: str, rate: int) -> list[float] | None:
    recipe = SFX.get(name)
    return recipe(Synth(rate)) if recipe is not None else None


def music_samples(name: str, rate: int) -> list[float] | None:
    recipe = MUSIC.get(name)
    return _normalise(recipe(Synth(rate))) if recipe is not None else None