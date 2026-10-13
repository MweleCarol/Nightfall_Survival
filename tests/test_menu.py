import pygame
import pytest

from src.services.asset_manager import AssetManager
from src.ui.menu_art import build_logo, build_menu_background
from src.ui.widgets import MenuButton, MenuModel, handle_menu_input, render_tracked


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def make_font() -> pygame.font.Font:
    return pygame.font.Font(None, 20)


def make_button(x: int, y: int, enabled: bool = True) -> MenuButton:
    return MenuButton("TEST", "play", pygame.Rect(x, y, 200, 40), make_font(), enabled)


def test_menu_starts_on_the_first_enabled_entry():
    assert MenuModel([False, True, True]).selected == 1


def test_moving_skips_disabled_entries_and_wraps():
    model = MenuModel([True, False, True, True])
    model.move(1)
    assert model.selected == 2
    model.move(1)
    assert model.selected == 3
    model.move(1)
    assert model.selected == 0
    model.move(-1)
    assert model.selected == 3


def test_selecting_a_disabled_entry_is_refused():
    model = MenuModel([True, False, True])
    assert model.select(1) is False and model.selected == 0
    assert model.select(9) is False
    assert model.select(2) is True and model.selected == 2


def test_a_menu_with_nothing_enabled_does_not_crash():
    model = MenuModel([False, False])
    model.move(1)
    assert model.select(0) is False


def test_enabling_an_entry_makes_it_reachable():
    model = MenuModel([True, False])
    model.set_enabled(1, True)
    model.move(1)
    assert model.selected == 1


def test_tracked_text_is_wider_by_the_tracking():
    font = make_font()
    plain = sum(font.render(c, True, (255, 255, 255)).get_width() for c in "ABC")
    assert render_tracked("ABC", font, (255, 255, 255), 5).get_width() == plain + 10


def test_button_glow_animates_towards_the_highlight():
    button = make_button(0, 0)
    button.update(0.05, True)
    assert 0.0 < button.glow < 1.0
    button.update(1.0, True)
    assert button.glow == 1.0
    button.update(1.0, False)
    assert button.glow == 0.0


def test_disabled_button_never_glows():
    button = make_button(0, 0, enabled=False)
    button.update(1.0, True)
    assert button.glow == 0.0


def test_button_hit_test():
    button = make_button(10, 10)
    assert button.contains((50, 30)) and not button.contains((300, 30))


def test_keyboard_navigation_activates_the_highlighted_button():
    buttons = [make_button(0, 0), make_button(0, 60)]
    model = MenuModel([True, True])
    assert handle_menu_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN), buttons, model) is None
    assert model.selected == 1
    assert handle_menu_input(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), buttons, model) == 1


def test_clicking_a_disabled_button_does_nothing():
    buttons = [make_button(0, 0), make_button(0, 60, enabled=False)]
    model = MenuModel([True, False])
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 80))
    assert handle_menu_input(click, buttons, model) is None
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 20))
    assert handle_menu_input(click, buttons, model) == 0


def test_menu_background_is_drawn_at_the_requested_size():
    surface = build_menu_background(320, 180)
    assert surface.get_size() == (320, 180)
    colours = {tuple(surface.get_at((x, y)))[:3] for x in range(0, 320, 20) for y in range(0, 180, 10)}
    assert len(colours) > 5                       # a gradient and objects, not a flat colour


def test_logo_is_built_without_any_image_files(tmp_path):
    logo = build_logo(AssetManager(tmp_path))
    assert logo.get_width() > 100 and pygame.mask.from_surface(logo).count() > 100