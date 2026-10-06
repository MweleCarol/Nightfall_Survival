from dataclasses import FrozenInstanceError

import pytest

from core.settings import Settings, resource_path


def test_default_settings_match_design_target():
    settings = Settings()
    assert (settings.width, settings.height) == (1280, 720)
    assert settings.fps == 60


def test_settings_are_immutable():
    settings = Settings()
    with pytest.raises(FrozenInstanceError):
        settings.fps = 30  # type: ignore[misc]


def test_resource_path_points_inside_project():
    assert resource_path("src").exists()