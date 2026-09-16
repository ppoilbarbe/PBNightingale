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
    import pbnightingale.settings as _settings_mod

    cfg = _settings_mod._dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def save_geometry(key: str, geometry: QByteArray) -> None:
    _settings().setValue(f"windowState/{key}/geometry", geometry)


def load_geometry(key: str) -> QByteArray | None:
    value = _settings().value(f"windowState/{key}/geometry")
    return value if isinstance(value, QByteArray) else None


def save_splitter_state(window_key: str, splitter_key: str, state: QByteArray) -> None:
    _settings().setValue(f"windowState/{window_key}/splitter/{splitter_key}", state)


def load_splitter_state(window_key: str, splitter_key: str) -> QByteArray | None:
    value = _settings().value(f"windowState/{window_key}/splitter/{splitter_key}")
    return value if isinstance(value, QByteArray) else None


def save_header_state(window_key: str, header_key: str, state: QByteArray) -> None:
    _settings().setValue(f"windowState/{window_key}/header/{header_key}", state)


def load_header_state(window_key: str, header_key: str) -> QByteArray | None:
    value = _settings().value(f"windowState/{window_key}/header/{header_key}")
    return value if isinstance(value, QByteArray) else None


def save_toolbar_state(key: str, state: QByteArray) -> None:
    """Persist a ``QMainWindow.saveState()`` blob — toolbar position,
    order and visibility (and dock widget layout, unused here)."""
    _settings().setValue(f"windowState/{key}/toolbars", state)


def load_toolbar_state(key: str) -> QByteArray | None:
    value = _settings().value(f"windowState/{key}/toolbars")
    return value if isinstance(value, QByteArray) else None
