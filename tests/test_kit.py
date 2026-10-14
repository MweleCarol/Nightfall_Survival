import pygame
import pytest

from src.ui.kit import (
    cut_panel, draw_bar, draw_checkbox, draw_hud_icon, draw_item_icon, draw_keycap,
    fit_text, parse_prompt,
)


@pytest.fixture(autouse=True, scope="module")
def font_module():
    pygame.font.init()


def test_cut_panel_has_the_size_and_chamfered_corners():
    panel = cut_panel(120, 60)
    assert panel.get_size() == (120, 60)
    assert panel.get_at((0, 0)).a == 0 and panel.get_at((119, 59)).a == 0
    assert panel.get_at((60, 30)).a > 0


def test_fit_text_shortens_long_text():
    assert fit_text("short", 20) == "short"
    shortened = fit_text("a very long line of objective text", 15)
    assert len(shortened) <= 15 and shortened.endswith("...")


def test_fit_text_collapses_whitespace():
    assert fit_text("a   b\n c", 20) == "a b c"


def test_prompts_are_split_into_a_key_and_a_sentence():
    assert parse_prompt("Press E to search") == ("E", "to search")
    assert parse_prompt("Press k to open skills") == ("K", "to open skills")


def test_prompts_without_a_key_are_left_alone():
    assert parse_prompt("Inventory full") == (None, "Inventory full")


def test_keycap_returns_its_rectangle():
    surface = pygame.Surface((200, 100))
    rect = draw_keycap(surface, pygame.font.Font(None, 20), "E", (10, 10))
    assert rect.width >= 22 and rect.topleft == (10, 10)


def test_every_hud_icon_draws():
    surface = pygame.Surface((200, 100))
    for name in ("heart", "bolt", "skull", "warning", "diamond", "radio", "sun", "moon",
                 "gun", "mag", "not-an-icon"):
        draw_hud_icon(surface, name, (50, 50), (255, 255, 255), 20)


def test_item_icons_have_drawn_fallbacks():
    surface = pygame.Surface((200, 100))
    for item_id, kind in (("medkit", "consumable"), ("bandage", "consumable"), ("ammo_9mm", "ammo"),
                          ("scrap", "resource"), ("radio_unit", "quest"), ("mystery", "unheard-of")):
        draw_item_icon(surface, None, item_id, kind, pygame.Rect(10, 10, 44, 44))


def test_bars_and_checkboxes_draw():
    surface = pygame.Surface((200, 100))
    for fraction in (-1.0, 0.0, 0.5, 1.0, 9.0):
        draw_bar(surface, pygame.Rect(10, 10, 100, 12), fraction, (200, 40, 40))
    draw_checkbox(surface, pygame.Rect(10, 40, 14, 14), True)
    draw_checkbox(surface, pygame.Rect(40, 40, 14, 14), False)


def test_cut_panel_accepts_any_border_colour():
    assert cut_panel(60, 40, border=(224, 34, 27)).get_size() == (60, 40)