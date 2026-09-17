"""Bundled resource files (SVG icons)."""

from pathlib import Path

_HERE = Path(__file__).parent


def path(name: str) -> str:
    """Return the absolute path to a bundled resource file.

    Parameters
    ----------
    name
        The resource's file name, e.g. ``"quit.svg"``.

    Returns
    -------
    :
        The absolute path to that file.
    """
    return str(_HERE / name)
