"""General application preferences, beyond language (see ``i18n.py``) and
window geometry (see ``ui/window_state.py``).

Backed by the same ``QSettings`` INI file as those, rooted at ``settings.py``'s
config directory — so it gets the same test isolation automatically.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

_DOMAIN = "pbnightingale"
_ALGORITHM_KEY = "keygen/preferred_algorithm"
DEFAULT_ALGORITHM = "RSA"

_ICON_SIZE_KEY = "ui/toolbar_icon_size"
DEFAULT_TOOLBAR_ICON_SIZE = "system"
_VALID_TOOLBAR_ICON_SIZES = ("system", "16", "24", "32", "48", "64")

# A QSettings key name, not a credential — ruff's S105 can't tell the
# difference from the "passphrase" substring alone.
_PASSPHRASE_CACHE_KEY = "security/passphrase_cache_minutes"  # noqa: S105
DEFAULT_PASSPHRASE_CACHE_MINUTES = 10


def _settings() -> QSettings:
    import pbnightingale.settings as _settings_mod

    cfg = _settings_mod._dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def get_preferred_algorithm() -> str:
    """Return the preferred key algorithm ("RSA" or "ED25519"), default RSA."""
    value = _settings().value(_ALGORITHM_KEY, DEFAULT_ALGORITHM)
    return value if value in ("RSA", "ED25519") else DEFAULT_ALGORITHM


def set_preferred_algorithm(algorithm: str) -> None:
    _settings().setValue(_ALGORITHM_KEY, algorithm)


def get_toolbar_icon_size() -> str:
    """Return the preferred toolbar icon size: ``"system"`` (the current Qt
    style's own default, i.e. no explicit override) or a pixel size
    (``"16"``, ``"24"``, ``"32"``, ``"48"``, ``"64"``)."""
    value = _settings().value(_ICON_SIZE_KEY, DEFAULT_TOOLBAR_ICON_SIZE)
    return value if value in _VALID_TOOLBAR_ICON_SIZES else DEFAULT_TOOLBAR_ICON_SIZE


def set_toolbar_icon_size(size: str) -> None:
    _settings().setValue(_ICON_SIZE_KEY, size)


def get_passphrase_cache_minutes() -> int:
    """Return how long (in minutes) a successfully-entered passphrase stays
    cached in memory before being forgotten; 0 disables caching entirely.
    """
    value = _settings().value(_PASSPHRASE_CACHE_KEY, DEFAULT_PASSPHRASE_CACHE_MINUTES)
    try:
        minutes = int(value)
    except TypeError, ValueError:
        return DEFAULT_PASSPHRASE_CACHE_MINUTES
    return minutes if minutes >= 0 else DEFAULT_PASSPHRASE_CACHE_MINUTES


def set_passphrase_cache_minutes(minutes: int) -> None:
    _settings().setValue(_PASSPHRASE_CACHE_KEY, minutes)
