"""Loads and caches images and fonts. A missing optional asset never crashes the game."""
from __future__ import annotations

import logging
from pathlib import Path

import pygame

from src.services.data_loader import resource_path

log = logging.getLogger(__name__)

# Used when no custom font file is found. Bahnschrift ships with Windows 10/11.
FONT_FALLBACKS = "bahnschrift,segoeui,arial"


class AssetManager:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or resource_path("assets")
        self._images: dict[str, pygame.Surface | None] = {}
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}

    def image(self, relative_path: str) -> pygame.Surface | None:
        """Load assets/images/<relative_path>. Returns None if it is missing or broken."""
        if relative_path in self._images:
            return self._images[relative_path]
        path = self.root / "images" / relative_path
        surface = None
        if path.is_file():
            try:
                surface = pygame.image.load(str(path))
                if pygame.display.get_surface() is not None:
                    surface = surface.convert_alpha()
            except pygame.error as error:
                log.warning("Could not load image %s: %s", path, error)
                surface = None
        else:
            log.info("Optional image not found: %s", path)
        self._images[relative_path] = surface          # remember misses too
        return surface

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        """A font from assets/fonts/ui(.ttf|_bold.ttf), or a good system font as a fallback."""
        key = (size, bold)
        if key in self._fonts:
            return self._fonts[key]
        font = None
        names = ("ui_bold.ttf", "ui.ttf") if bold else ("ui.ttf",)
        for name in names:
            path = self.root / "fonts" / name
            if path.is_file():
                try:
                    font = pygame.font.Font(str(path), size)
                    break
                except (pygame.error, OSError) as error:
                    log.warning("Could not load font %s: %s", path, error)
        if font is None:
            font = pygame.font.SysFont(FONT_FALLBACKS, size, bold=bold)
        self._fonts[key] = font
        return font