"""PBNightingale — A graphical GPG key management utility."""

import builtins

#: Current release version (semver).
__version__ = "0.2.2"
#: Upstream author's name.
__author__ = "Marcel Spock"
#: Upstream author's contact address.
__email__ = "mrspock@cardolan.net"
#: SPDX-ish short license identifier for the code (see LICENSE).
__license__ = "GPLv3"

# No-op fallback so _() is always defined even when i18n.setup() is not called
# (e.g. during unit tests or direct imports without launching the app).
if not hasattr(builtins, "_"):
    builtins._ = lambda s: s  # type: ignore[assignment]
