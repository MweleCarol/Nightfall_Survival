import random

import pygame

from src.world.weather import WeatherSystem, rain_fraction


def make() -> WeatherSystem:
    return WeatherSystem(320, 180, random.Random(1))


def test_rain_fraction_follows_the_darkness():
    assert rain_fraction(0.0) == 0.0 and rain_fraction(0.1) == 0.0
    assert 0.0 < rain_fraction(0.4) < 1.0
    assert rain_fraction(1.0) == 1.0 and rain_fraction(5.0) == 1.0


def test_it_does_not_rain_in_daylight():
    weather = make()
    before = [list(drop) for drop in weather.rain.drops]
    weather.update(1.0, 0.0)
    assert weather.intensity == 0.0 and weather.rain.drops == before


def test_rain_falls_at_night():
    weather = make()
    before = [list(drop) for drop in weather.rain.drops]
    weather.update(0.1, 1.0)
    assert weather.intensity == 1.0 and weather.rain.drops != before


def test_lightning_only_strikes_in_heavy_rain():
    weather = make()
    weather.lightning.timer = 5.0
    weather.update(1.0, 0.3)                      # a light drizzle
    assert weather.lightning.timer == 5.0
    weather.update(1.0, 1.0)                      # a downpour
    assert weather.lightning.timer == 4.0


def test_weather_draws_without_errors():
    weather = make()
    weather.update(0.1, 1.0)
    surface = pygame.Surface((320, 180))
    weather.draw_fog(surface)
    weather.draw_rain(surface)
    weather.draw_lightning(surface)