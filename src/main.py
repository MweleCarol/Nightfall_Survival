"""Entry point. Run with:  python -m src.main"""
import logging

from src.core.game import Game
from src.states.boot_state import BootState


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    game = Game()
    game.state_manager.change_state(BootState(game))
    game.run()


if __name__ == "__main__":
    main()