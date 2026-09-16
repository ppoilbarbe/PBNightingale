"""OS-specific abstractions (config/data directories, auto-update, …).

All platform-dependent code lives here so ``core/`` and ``ui/`` stay portable
across Linux, Windows and macOS.
"""

from pbnightingale.platform.dirs import AppDirs, XdgDirs
from pbnightingale.platform.locale import system_language

__all__ = [
    "AppDirs",
    "XdgDirs",
    "system_language",
]
