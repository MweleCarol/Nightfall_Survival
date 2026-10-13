"""Entry point. Run from the project root with:  python -m src.main"""
import logging

from src.core.game import Game
from src.states.main_menu_state import MainMenuState


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    game = Game()
    game.state_manager.change_state(MainMenuState(game))
    game.run()


if __name__ == "__main__":
    main()