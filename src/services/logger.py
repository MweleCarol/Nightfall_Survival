"""Logging helper.

Logs go to the console (INFO and above) and to logs/nightfall.log (everything).
"""

from __future__ import annotations

import logging

from core.settings import PROJECT_ROOT

_ROOT_NAME = "nightfall"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _configure_root_logger() -> logging.Logger:
    root = logging.getLogger(_ROOT_NAME)
    if root.handlers:  # already configured
        return root

    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(_FORMAT, datefmt="%H:%M:%S")

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        log_dir = PROJECT_ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "nightfall.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # A read-only folder must never stop the game from starting.
        root.warning("Could not create log file; logging to console only.")

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module. Usage: logger = get_logger(__name__)"""
    _configure_root_logger()
    return logging.getLogger(f"{_ROOT_NAME}.{name}")