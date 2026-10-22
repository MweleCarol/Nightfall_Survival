import pygame

from src.ui.widgets import MenuModel, handle_menu_input


class Box:
    """Just enough of a button for the input helper: a rectangle that can be hit-tested."""

    def __init__(self, y: int):
        self.rect = pygame.Rect(0, y, 100, 40)

    def contains(self, position) -> bool:
        return self.rect.collidepoint(position)


def key(code: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code)


def test_keyboard_moves_and_confirms_make_sounds():
    heard, model = [], MenuModel([True, True])
    boxes = [Box(0), Box(60)]
    assert handle_menu_input(key(pygame.K_DOWN), boxes, model, heard.append) is None
    assert handle_menu_input(key(pygame.K_RETURN), boxes, model, heard.append) == 1
    assert heard == ["ui_move", "ui_confirm"]


def test_clicking_a_disabled_button_makes_the_refusal_sound():
    heard, model = [], MenuModel([True, False])
    boxes = [Box(0), Box(60)]
    refuse = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 80))
    accept = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 20))
    assert handle_menu_input(refuse, boxes, model, heard.append) is None
    assert handle_menu_input(accept, boxes, model, heard.append) == 0
    assert heard == ["ui_deny", "ui_confirm"]


def test_hovering_a_new_button_ticks_once_and_works_without_a_sound_callback():
    heard, model = [], MenuModel([True, True])
    boxes = [Box(0), Box(60)]
    over_second = pygame.event.Event(pygame.MOUSEMOTION, pos=(50, 80), rel=(0, 0), buttons=(0, 0, 0))
    handle_menu_input(over_second, boxes, model, heard.append)
    handle_menu_input(over_second, boxes, model, heard.append)          # still on the same button
    assert heard == ["ui_move"]
    assert handle_menu_input(key(pygame.K_UP), boxes, model) is None     # no callback: no crash