"""The real sound backend, built on pygame.mixer. Raises pygame.error if there is no usable audio."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pygame

from src.audio import synth
from src.core import settings

log = logging.getLogger(__name__)

MUSIC_LAYERS = 4               # one reserved mixer channel per music track
EXTENSIONS = (".ogg", ".wav", ".mp3")


class PygameBackend:
    available = True

    def __init__(self, audio_root: Path) -> None:
        self.root = audio_root
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(settings.AUDIO_SAMPLE_RATE, -16, settings.AUDIO_CHANNELS, 512)
        self.rate, self.format, self.channels = pygame.mixer.get_init()
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(MUSIC_LAYERS)           # channels 0-3 are for music only
        self._layers = [pygame.mixer.Channel(i) for i in range(MUSIC_LAYERS)]

    def load(self, name: str, kind: str) -> Any:
        """A real file from assets/audio/<sfx|music>/ if there is one, else a generated placeholder."""
        folder = self.root / ("music" if kind == "music" else "sfx")
        for extension in EXTENSIONS:
            path = folder / f"{name}{extension}"
            if path.is_file():
                try:
                    return pygame.mixer.Sound(str(path))
                except pygame.error as error:
                    log.warning("Could not load %s: %s", path, error)
        if self.format != -16:                             # the generator makes 16-bit audio only
            return None
        samples = (synth.music_samples if kind == "music" else synth.sfx_samples)(name, self.rate)
        if samples is None:
            return None
        return pygame.mixer.Sound(buffer=synth.to_pcm(samples, self.channels))

    def play(self, handle: Any, volume: float) -> None:
        handle.set_volume(volume)
        handle.play()

    def start_loop(self, layer: int, handle: Any, volume: float) -> None:
        channel = self._layers[layer]
        channel.play(handle, loops=-1, fade_ms=60)         # a short fade-in avoids a pop
        channel.set_volume(volume)

    def set_layer_volume(self, layer: int, volume: float) -> None:
        self._layers[layer].set_volume(volume)

    def stop_layer(self, layer: int) -> None:
        self._layers[layer].stop()

    def shutdown(self) -> None:
        pygame.mixer.stop()