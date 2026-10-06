"""Loading JSON content files with clear error messages."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class DataLoadError(Exception):
    """A content file is missing or malformed. The message names the file/field."""


def resource_path(relative: str) -> Path:
    """Resolve a project-relative path in dev AND in a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative


def load_json(relative_path: str) -> dict[str, Any]:
    path = resource_path(relative_path)
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise DataLoadError(f"Missing data file: {relative_path}") from None
    except json.JSONDecodeError as exc:
        raise DataLoadError(
            f"Invalid JSON in {relative_path}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise DataLoadError(f"{relative_path}: top level must be a JSON object")
    return data


def require_field(data: dict, key: str, expected: type | tuple[type, ...], where: str) -> Any:
    """Return data[key] after checking that it exists and has the expected type."""
    if key not in data:
        raise DataLoadError(f"{where}: missing field '{key}'")
    value = data[key]
    types = expected if isinstance(expected, tuple) else (expected,)
    wrong_bool = isinstance(value, bool) and bool not in types   # True counts as an int in Python!
    if wrong_bool or not isinstance(value, types):
        names = " or ".join(t.__name__ for t in types)
        raise DataLoadError(f"{where}: field '{key}' must be {names}")
    return value