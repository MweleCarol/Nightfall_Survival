import pygame
import pytest

from src.services.asset_manager import AssetManager


@pytest.fixture(autouse=True)
def font_module():
    pygame.font.init()


def make_png(path) -> None:
    surface = pygame.Surface((8, 4))
    surface.fill((255, 0, 0))
    pygame.image.save(surface, str(path))


def test_missing_image_returns_none_and_is_remembered(tmp_path):
    assets = AssetManager(tmp_path)
    assert assets.image("ui/logo.png") is None
    assert assets.image("ui/logo.png") is None
    assert "ui/logo.png" in assets._images           # remembered, so the disk is searched only once


def test_existing_image_loads_once(tmp_path):
    (tmp_path / "images" / "ui").mkdir(parents=True)
    make_png(tmp_path / "images" / "ui" / "logo.png")
    assets = AssetManager(tmp_path)
    first = assets.image("ui/logo.png")
    assert first is not None and first.get_size() == (8, 4)
    assert assets.image("ui/logo.png") is first


def test_corrupt_image_falls_back_to_none(tmp_path):
    (tmp_path / "images" / "ui").mkdir(parents=True)
    (tmp_path / "images" / "ui" / "logo.png").write_bytes(b"this is not a png")
    assert AssetManager(tmp_path).image("ui/logo.png") is None


def test_fonts_are_cached_per_size_and_weight(tmp_path):
    assets = AssetManager(tmp_path)
    assert assets.font(20) is assets.font(20)
    assert assets.font(20) is not assets.font(30)
    assert assets.font(20) is not assets.font(20, bold=True)


def test_font_works_without_any_font_files(tmp_path):
    assert isinstance(AssetManager(tmp_path).font(18), pygame.font.Font)