"""Persistent window geometry and splitter sizes.

Backed by the same ``QSettings`` INI file as ``i18n.py``'s language override
(one settings file for the whole app), rooted at ``settings.py``'s config
directory — so it automatically gets the same test isolation
(``tests/conftest.py``'s autouse ``_isolated_config`` fixture).
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings

_DOMAIN = "pbnightingale"


def _settings() -> QSettings:
    """Return the ``QSettings`` instance backing every function below."""
    import pbnightingale.settings as _settings_mod

    cfg = _settings_mod._dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def save_geometry(key: str, geometry: QByteArray) -> None:
    """Persist a ``QWidget.saveGeometry()`` blob under *key*."""
    _settings().setValue(f"windowState/{key}/geometry", geometry)


def load_geometry(key: str) -> QByteArray | None:
    """Return the geometry blob last saved under *key*, or ``None``.

    Returns
    -------
    :
        The saved blob, or ``None`` if nothing was ever saved for *key*.
    """
    value = _settings().value(f"windowState/{key}/geometry")
    return value if isinstance(value, QByteArray) else None


def save_splitter_state(window_key: str, splitter_key: str, state: QByteArray) -> None:
    """Persist a ``QSplitter.saveState()`` blob.

    Parameters
    ----------
    window_key
        The window the splitter belongs to.
    splitter_key
        Short key identifying this splitter within *window_key*.
    state
        The blob returned by the splitter's own ``saveState()``.
    """
    _settings().setValue(f"windowState/{window_key}/splitter/{splitter_key}", state)


def load_splitter_state(window_key: str, splitter_key: str) -> QByteArray | None:
    """Return the splitter state last saved for *window_key*/*splitter_key*.

    Returns
    -------
    :
        The saved blob, or ``None`` if nothing was ever saved for it.
    """
    value = _settings().value(f"windowState/{window_key}/splitter/{splitter_key}")
    return value if isinstance(value, QByteArray) else None


def save_header_state(window_key: str, header_key: str, state: QByteArray) -> None:
    """Persist a ``QHeaderView.saveState()`` blob (a tree/table's column widths).

    Parameters
    ----------
    window_key
        The window the header belongs to.
    header_key
        Short key identifying this header within *window_key*.
    state
        The blob returned by the header's own ``saveState()``.
    """
    _settings().setValue(f"windowState/{window_key}/header/{header_key}", state)


def load_header_state(window_key: str, header_key: str) -> QByteArray | None:
    """Return the header state last saved for *window_key*/*header_key*.

    Returns
    -------
    :
        The saved blob, or ``None`` if nothing was ever saved for it.
    """
    value = _settings().value(f"windowState/{window_key}/header/{header_key}")
    return value if isinstance(value, QByteArray) else None


def save_toolbar_state(key: str, state: QByteArray) -> None:
    """Persist a ``QMainWindow.saveState()`` blob: toolbar position, order and visibility (and dock widget layout, unused here)."""
    _settings().setValue(f"windowState/{key}/toolbars", state)


def load_toolbar_state(key: str) -> QByteArray | None:
    """Return the toolbar state last saved under *key*, or ``None``.

    Returns
    -------
    :
        The saved blob, or ``None`` if nothing was ever saved for *key*.
    """
    value = _settings().value(f"windowState/{key}/toolbars")
    return value if isinstance(value, QByteArray) else None
