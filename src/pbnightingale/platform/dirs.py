"""Cross-platform application directory resolver.

Dispatches to the right implementation based on ``sys.platform``:
- Windows  : %APPDATA% / %LOCALAPPDATA%
- macOS    : ~/Library/…
- Linux    : Freedesktop XDG Base Directory Specification (v0.8)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class _BaseDirs:
    """Common interface for a platform-specific application directory set."""

    def __init__(self, app_name: str) -> None:
        """Store the application name every directory is namespaced under.

        Parameters
        ----------
        app_name
            The application's directory name, e.g. ``"pbnightingale"``.
        """
        self._app = app_name

    @property
    def config_home(self) -> Path:
        """The application's configuration directory."""
        raise NotImplementedError

    @property
    def data_home(self) -> Path:
        """The application's data directory."""
        raise NotImplementedError

    @property
    def cache_home(self) -> Path:
        """The application's cache directory."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


class _WindowsDirs(_BaseDirs):
    """Application directories under ``%APPDATA%``/``%LOCALAPPDATA%``."""

    @property
    def config_home(self) -> Path:
        """The application's subdirectory under ``%APPDATA%``."""
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / self._app

    @property
    def data_home(self) -> Path:
        """Same as ``config_home`` — Windows has no separate data directory."""
        return self.config_home

    @property
    def cache_home(self) -> Path:
        """The application's subdirectory under ``%LOCALAPPDATA%``."""
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / self._app


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


class _MacDirs(_BaseDirs):
    """Application directories under ``~/Library``."""

    @property
    def config_home(self) -> Path:
        """The application's subdirectory under ``~/Library/Preferences``."""
        return Path.home() / "Library" / "Preferences" / self._app

    @property
    def data_home(self) -> Path:
        """The application's subdirectory under ``~/Library/Application Support``."""
        return Path.home() / "Library" / "Application Support" / self._app

    @property
    def cache_home(self) -> Path:
        """The application's subdirectory under ``~/Library/Caches``."""
        return Path.home() / "Library" / "Caches" / self._app


# ---------------------------------------------------------------------------
# Linux / XDG
# ---------------------------------------------------------------------------


def _xdg_dir(var: str, default: Path) -> Path:
    """Return an XDG base directory, falling back to a default.

    Per spec the value is ignored if it is not set, empty, or not absolute.

    Parameters
    ----------
    var
        The XDG environment variable to read, e.g. ``"XDG_CONFIG_HOME"``.
    default
        The value to use when ``var`` is unset, empty, or not absolute.

    Returns
    -------
    :
        The resolved base directory.
    """
    val = os.environ.get(var, "")
    p = Path(val) if val else None
    return p if (p and p.is_absolute()) else default


class XdgDirs(_BaseDirs):
    """Freedesktop XDG Base Directory Specification (version 0.8).

    Reference: https://specifications.freedesktop.org/basedir-spec/latest/
    """

    @property
    def config_home(self) -> Path:
        """The application's subdirectory under ``$XDG_CONFIG_HOME``."""
        return _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / self._app

    @property
    def data_home(self) -> Path:
        """The application's subdirectory under ``$XDG_DATA_HOME``."""
        return _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / self._app

    @property
    def cache_home(self) -> Path:
        """The application's subdirectory under ``$XDG_CACHE_HOME``."""
        return _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache") / self._app

    @property
    def state_home(self) -> Path:
        """The application's subdirectory under ``$XDG_STATE_HOME``."""
        return _xdg_dir("XDG_STATE_HOME", Path.home() / ".local" / "state") / self._app

    @property
    def runtime_dir(self) -> Path | None:
        """The application's subdirectory under ``$XDG_RUNTIME_DIR``.

        Unlike the other XDG directories, ``$XDG_RUNTIME_DIR`` has no spec-
        mandated fallback — this returns ``None`` when it's unset, empty,
        or not absolute, rather than guessing one.
        """
        val = os.environ.get("XDG_RUNTIME_DIR", "")
        p = Path(val) if val else None
        return (p / self._app) if (p and p.is_absolute()) else None

    @property
    def config_dirs(self) -> list[Path]:
        """The application's subdirectory under each ``$XDG_CONFIG_DIRS`` entry."""
        val = os.environ.get("XDG_CONFIG_DIRS", "")
        dirs = [Path(p) for p in val.split(":") if p] if val else [Path("/etc/xdg")]
        return [d / self._app for d in dirs if d.is_absolute()]

    @property
    def data_dirs(self) -> list[Path]:
        """The application's subdirectory under each ``$XDG_DATA_DIRS`` entry."""
        val = os.environ.get("XDG_DATA_DIRS", "")
        defaults = [Path("/usr/local/share"), Path("/usr/share")]
        dirs = [Path(p) for p in val.split(":") if p] if val else defaults
        return [d / self._app for d in dirs if d.is_absolute()]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def AppDirs(app_name: str) -> _BaseDirs:
    """Return the platform-appropriate application directory object.

    Parameters
    ----------
    app_name
        The application's directory name, e.g. ``"pbnightingale"``.

    Returns
    -------
    :
        A ``_WindowsDirs``, ``_MacDirs`` or ``XdgDirs`` instance, matching
        ``sys.platform``.
    """
    if sys.platform == "win32":
        return _WindowsDirs(app_name)
    if sys.platform == "darwin":
        return _MacDirs(app_name)
    return XdgDirs(app_name)
