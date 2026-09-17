"""Application preferences — persistence root shared by all settings modules.

Only the configuration directory lives here. Feature-specific preferences
(language override in ``i18n.py``, auto-update in ``platform/auto_update.py``,
…) each keep their own keys but go through ``_dirs.config_home`` from here so
they all get test isolation for free via ``configure()``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pbnightingale.platform import AppDirs

_DOMAIN = "pbnightingale"
_dirs = AppDirs(_DOMAIN)


def configure(config_dir: Path | None = None) -> None:
    """Override the configuration directory used by all settings functions.

    Intended for testing — never run/test against the real user's
    configuration directory.

    Parameters
    ----------
    config_dir
        The directory to use, or ``None`` to restore the platform default.
    """
    global _dirs
    if config_dir is None:
        _dirs = AppDirs(_DOMAIN)
    else:
        _dirs = SimpleNamespace(
            config_home=config_dir,
            data_home=config_dir,
            cache_home=config_dir,
        )
