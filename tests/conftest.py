# Force offscreen rendering before Qt is imported — required when DISPLAY is absent
# (local CI, SSH without X forwarding, local test run without a compositor).
# Must come before any PySide6 import; setdefault lets the caller override it
# (e.g. QT_QPA_PLATFORM=xcb make test to debug with a visible display).
import builtins
import os
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Telltale files gpg itself creates in a directory it's used as a GNUPGHOME —
# used to skip the (harmless but not free) `gpgconf --kill` subprocess call
# for the many directories a test creates that were never a GNUPGHOME at all.
_GNUPGHOME_MARKERS = (
    "pubring.kbx",
    "private-keys-v1.d",
    "trustdb.gpg",
    "openpgp-revocs.d",
)


def _kill_gpg_agents_under(root: Path) -> None:
    """Kill any gpg-agent bound to *root* or one of its subdirectories.

    Every test that touches gpg does so through its own isolated,
    disposable GNUPGHOME (never the real user's keyring), but gpg itself
    autostarts a gpg-agent daemon the first time it needs one — and unlike
    the gpg subprocess itself, that daemon detaches and keeps running
    long after the directory (and the test) are gone, since nothing else
    ever tells it to stop. Left unchecked, a full test run leaves behind
    one stray `gpg-agent --homedir <deleted tmp dir>` process per test
    that generated or manipulated a key — hundreds of them accumulate
    over time (found via `ps -ef | grep gpg-agen[t]`, a real report from
    running this suite repeatedly). `gpgconf --kill` is the same
    graceful-shutdown mechanism `GPGBackend._restart_agent()` already
    uses in production, and is a safe no-op for a directory that never
    had an agent — but only bother calling it for directories that
    actually look like a GNUPGHOME, to avoid a subprocess spawn per test
    for the many tests that never touch gpg at all.
    """
    if not root.exists():
        return
    candidates = [root, *(p for p in root.rglob("*") if p.is_dir())]
    for directory in candidates:
        if any((directory / marker).exists() for marker in _GNUPGHOME_MARKERS):
            try:
                subprocess.run(  # noqa: S603
                    ["gpgconf", "--homedir", str(directory), "--kill", "gpg-agent"],  # noqa: S607
                    capture_output=True,
                    check=False,
                )
            except FileNotFoundError:
                pass


@pytest.fixture(autouse=True)
def _kill_gpg_agents_after_test(tmp_path):
    """Clean up any gpg-agent a test started under its own ``tmp_path`` —
    see ``_kill_gpg_agents_under()``. Most tests that exercise
    ``GPGBackend`` build it directly on a ``tmp_path`` subdirectory
    (``GPGBackend(tmp_path / "home")``, ``.../"source"``, ``.../"dest"``,
    …), which is a different root from the ``gnupg_home`` fixture below.
    """
    yield
    _kill_gpg_agents_under(tmp_path)


@pytest.fixture
def config_dir(tmp_path_factory):
    """Return a per-test config directory and redirect all settings I/O to it.

    Uses tmp_path_factory so the directory is independent from the test's own
    tmp_path, preventing directory-listing tests from seeing a spurious entry.
    Tests that need to inspect or write config files directly can request this
    fixture to obtain the path.
    """
    import pbnightingale.settings as _settings

    cfg = tmp_path_factory.mktemp("pbncfg", numbered=True)
    _settings.configure(cfg)
    yield cfg
    _settings.configure()


@pytest.fixture(autouse=True)
def _isolated_config(config_dir):
    """Ensure every test runs with an isolated config directory."""


@pytest.fixture
def gnupg_home(tmp_path_factory):
    """Return a per-test GNUPGHOME and redirect gpg_backend.default_backend()
    to it. Never the real user's keyring.
    """
    from pbnightingale.core import gpg_backend

    home = tmp_path_factory.mktemp("pbngnupg", numbered=True)
    gpg_backend.configure(home)
    yield home
    gpg_backend.configure()
    _kill_gpg_agents_under(home)


@pytest.fixture(autouse=True)
def _isolated_gnupghome(gnupg_home):
    """Ensure every test runs with an isolated GNUPGHOME."""


@pytest.fixture(autouse=True)
def _isolated_passphrase_cache():
    """Ensure no cached passphrase leaks between tests — this module-level
    cache otherwise persists across the whole test session.
    """
    from pbnightingale.core import passphrase_cache

    passphrase_cache.clear()
    yield
    passphrase_cache.clear()


@pytest.fixture(autouse=True)
def _restore_builtin_gettext():
    """Restore the global ``_()`` builtin after tests that call i18n.setup().

    gettext's ``install()`` mutates ``builtins._`` process-wide; without this,
    a test that installs a non-English catalogue would leak translated
    strings into unrelated tests that run afterwards.
    """
    original = getattr(builtins, "_", None)
    yield
    if original is not None:
        builtins._ = original
