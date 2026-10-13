import pygame
import pytest

from src.ui.screen_effects import HurtFlash, Vignette, low_health_intensity


def test_hurt_flash_fades_out():
    flash = HurtFlash(fade_time=0.45)
    flash.trigger(1.0)
    assert flash.intensity == 1.0
    flash.update(0.225)
    assert flash.intensity == pytest.approx(0.5)
    flash.update(1.0)
    assert flash.intensity == 0.0


def test_a_weaker_hit_does_not_replace_a_stronger_flash():
    flash = HurtFlash()
    flash.trigger(0.8)
    flash.trigger(0.3)
    assert flash.intensity == 0.8


def test_no_low_health_warning_when_healthy():
    assert low_health_intensity(0.5, 1.0) == 0.0
    assert low_health_intensity(0.3, 1.0) == 0.0


def test_the_warning_is_stronger_the_lower_the_health():
    def peak(fraction: float) -> float:
        return max(low_health_intensity(fraction, t * 0.05) for t in range(200))

    assert peak(0.05) > peak(0.25) > 0.0


def test_the_warning_stays_between_zero_and_one():
    for fraction in (-1.0, 0.0, 0.01, 0.1, 0.29, 5.0):
        for step in range(50):
            assert 0.0 <= low_health_intensity(fraction, step * 0.1) <= 1.0


def test_vignette_is_darker_in_the_corners_and_draws():
    vignette = Vignette(320, 180)
    assert vignette.dark.get_at((0, 0)).a > vignette.dark.get_at((160, 90)).a
    surface = pygame.Surface((320, 180))
    vignette.draw(surface, darkness=1.0, hurt=0.5, low_health=0.2)