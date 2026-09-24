"""General application preferences, beyond language and window geometry.

See ``i18n.py`` for language and ``ui/window_state.py`` for geometry.
Backed by the same ``QSettings`` INI file as those, rooted at ``settings.py``'s
config directory — so it gets the same test isolation automatically.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

_DOMAIN = "pbnightingale"
_ALGORITHM_KEY = "keygen/preferred_algorithm"
#: Fallback for ``get_preferred_algorithm()`` when nothing is saved yet.
DEFAULT_ALGORITHM = "RSA"

_ICON_SIZE_KEY = "ui/toolbar_icon_size"
#: Fallback for ``get_toolbar_icon_size()`` when nothing is saved yet.
DEFAULT_TOOLBAR_ICON_SIZE = "system"
_VALID_TOOLBAR_ICON_SIZES = ("system", "16", "24", "32", "48", "64")

# A QSettings key name, not a credential — ruff's S105 can't tell the
# difference from the "passphrase" substring alone.
_PASSPHRASE_CACHE_KEY = "security/passphrase_cache_minutes"  # noqa: S105
#: Fallback for ``get_passphrase_cache_minutes()`` when nothing is saved yet.
DEFAULT_PASSPHRASE_CACHE_MINUTES = 10

_KEYSERVERS_ARRAY = "keyservers/list"
#: Fallback for ``get_keyservers()`` when nothing is saved yet: the two
#: general-purpose, actively-maintained keyservers (checked), plus a few
#: other still-reachable community HKP servers (unchecked) for the user to
#: opt into. The classic SKS pool itself has been dead since 2021 (shut
#: down after GDPR takedown requests, no HKPS certificates issued since),
#: and pgp.mit.edu — long the best-known SKS node — is decommissioned; the
#: three unchecked entries below were picked instead from the still-
#: synchronising Hockeypuck network documented at
#: https://blog.pgpkeys.eu/state-keyservers-2024.html and verified
#: reachable directly, not merely because they were once part of SKS.
DEFAULT_KEYSERVERS: tuple[tuple[str, bool], ...] = (
    ("hkps://keys.openpgp.org", True),
    ("hkps://keyserver.ubuntu.com", True),
    ("hkps://pgpkeys.eu", False),
    ("hkps://the.earth.li", False),
    ("hkps://keys.mailvelope.com", False),
)

_THIRD_PARTY_SIGNATURES_KEY = "keyservers/keep_third_party_signatures"
#: Fallback for ``get_keep_third_party_signatures()``: off, GnuPG's own
#: default — see ``core.gpg_backend.set_keep_third_party_signatures()``.
DEFAULT_KEEP_THIRD_PARTY_SIGNATURES = False

_ACTIVITY_LOG_MAX_ENTRIES_KEY = "ui/activity_log_max_entries"
#: Fallback for ``get_activity_log_max_entries()`` when nothing is saved
#: yet — also ``core/activity_log.py``'s own ring-buffer default.
DEFAULT_ACTIVITY_LOG_MAX_ENTRIES = 50


def _settings() -> QSettings:
    """Return the ``QSettings`` instance backing every preference here."""
    import pbnightingale.settings as _settings_mod

    cfg = _settings_mod._dirs.config_home
    cfg.mkdir(parents=True, exist_ok=True)
    return QSettings(str(cfg / f"{_DOMAIN}.conf"), QSettings.Format.IniFormat)


def get_preferred_algorithm() -> str:
    """Return the preferred key algorithm.

    Returns
    -------
    :
        ``"RSA"`` or ``"ED25519"``, defaulting to ``DEFAULT_ALGORITHM``.
    """
    value = _settings().value(_ALGORITHM_KEY, DEFAULT_ALGORITHM)
    return value if value in ("RSA", "ED25519") else DEFAULT_ALGORITHM


def set_preferred_algorithm(algorithm: str) -> None:
    """Persist the preferred key algorithm.

    Parameters
    ----------
    algorithm
        ``"RSA"`` or ``"ED25519"``.
    """
    _settings().setValue(_ALGORITHM_KEY, algorithm)


def get_toolbar_icon_size() -> str:
    """Return the preferred toolbar icon size.

    Returns
    -------
    :
        ``"system"`` (the current Qt style's own default, i.e. no
        explicit override) or a pixel size (``"16"``, ``"24"``, ``"32"``,
        ``"48"``, ``"64"``).
    """
    value = _settings().value(_ICON_SIZE_KEY, DEFAULT_TOOLBAR_ICON_SIZE)
    return value if value in _VALID_TOOLBAR_ICON_SIZES else DEFAULT_TOOLBAR_ICON_SIZE


def set_toolbar_icon_size(size: str) -> None:
    """Persist the preferred toolbar icon size.

    Parameters
    ----------
    size
        One of the values returned by ``get_toolbar_icon_size()``.
    """
    _settings().setValue(_ICON_SIZE_KEY, size)


def get_passphrase_cache_minutes() -> int:
    """Return how long a successfully-entered passphrase stays cached.

    Returns
    -------
    :
        The cache duration in minutes; 0 disables caching entirely.
    """
    value = _settings().value(_PASSPHRASE_CACHE_KEY, DEFAULT_PASSPHRASE_CACHE_MINUTES)
    try:
        minutes = int(value)
    # "as _exc" (unused) is deliberate, not a style slip: a bare
    # "except (TypeError, ValueError):" here reproducibly makes ruff
    # 0.16.7's formatter strip the required parens, silently turning this
    # into invalid Python 2-style syntax on the next `ruff format` —
    # verified directly (`ruff format --diff` proposes exactly that
    # change), and reportedly what happened here before. Binding the
    # exception avoids the bug; do not remove the "as _exc" as a cleanup.
    except (TypeError, ValueError) as _exc:
        return DEFAULT_PASSPHRASE_CACHE_MINUTES
    return minutes if minutes >= 0 else DEFAULT_PASSPHRASE_CACHE_MINUTES


def set_passphrase_cache_minutes(minutes: int) -> None:
    """Persist how long a successfully-entered passphrase stays cached.

    Parameters
    ----------
    minutes
        The cache duration in minutes; 0 disables caching entirely.
    """
    _settings().setValue(_PASSPHRASE_CACHE_KEY, minutes)


def get_keyservers() -> list[tuple[str, bool]]:
    """Return the configured keyserver list, each with its checked state.

    Returns
    -------
    :
        ``(url, checked)`` pairs in display order — ``DEFAULT_KEYSERVERS``
        when nothing is saved yet. ``QSettings.beginWriteArray()`` never
        clears entries left over from a longer previous array, but
        ``beginReadArray()`` only ever reads back up to the ``size`` it
        wrote, so those leftovers stay harmlessly ignored — verified
        empirically, not just assumed from the Qt docs. "Nothing saved
        yet" is checked with ``contains()`` on the array's own ``size``
        key rather than the read size being ``0`` — the latter is also
        what a deliberately emptied list (every keyserver removed) looks
        like, and that's a real, different state from "never configured",
        not a fallback-to-defaults case.
    """
    settings = _settings()
    if not settings.contains(f"{_KEYSERVERS_ARRAY}/size"):
        return list(DEFAULT_KEYSERVERS)
    size = settings.beginReadArray(_KEYSERVERS_ARRAY)
    try:
        servers = []
        for i in range(size):
            settings.setArrayIndex(i)
            url = settings.value("url", "")
            if not url:
                continue
            checked = settings.value("checked", False)
            if not isinstance(checked, bool):
                checked = str(checked).strip().lower() == "true"
            servers.append((url, checked))
        return servers
    finally:
        settings.endArray()


def set_keyservers(servers: list[tuple[str, bool]]) -> None:
    """Persist the keyserver list, each with its checked state.

    Parameters
    ----------
    servers
        ``(url, checked)`` pairs, in the order to keep.
    """
    settings = _settings()
    settings.beginWriteArray(_KEYSERVERS_ARRAY)
    try:
        for i, (url, checked) in enumerate(servers):
            settings.setArrayIndex(i)
            settings.setValue("url", url)
            settings.setValue("checked", checked)
    finally:
        settings.endArray()


def get_keep_third_party_signatures() -> bool:
    """Return whether keyserver fetches keep other people's signatures.

    Returns
    -------
    :
        ``DEFAULT_KEEP_THIRD_PARTY_SIGNATURES`` (off) if nothing is saved.
    """
    value = _settings().value(
        _THIRD_PARTY_SIGNATURES_KEY, DEFAULT_KEEP_THIRD_PARTY_SIGNATURES
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def set_keep_third_party_signatures(enabled: bool) -> None:
    """Persist whether keyserver fetches keep other people's signatures.

    Parameters
    ----------
    enabled
        ``True`` to import third-party signatures along with a key.
    """
    _settings().setValue(_THIRD_PARTY_SIGNATURES_KEY, enabled)


def get_activity_log_max_entries() -> int:
    """Return how many recent commands the Activity window keeps.

    Returns
    -------
    :
        At least 1; falls back to ``DEFAULT_ACTIVITY_LOG_MAX_ENTRIES`` if
        nothing valid is saved.
    """
    value = _settings().value(
        _ACTIVITY_LOG_MAX_ENTRIES_KEY, DEFAULT_ACTIVITY_LOG_MAX_ENTRIES
    )
    try:
        max_entries = int(value)
    except (TypeError, ValueError) as _exc:
        return DEFAULT_ACTIVITY_LOG_MAX_ENTRIES
    return max_entries if max_entries >= 1 else DEFAULT_ACTIVITY_LOG_MAX_ENTRIES


def set_activity_log_max_entries(max_entries: int) -> None:
    """Persist how many recent commands the Activity window keeps.

    Parameters
    ----------
    max_entries
        At least 1.
    """
    _settings().setValue(_ACTIVITY_LOG_MAX_ENTRIES_KEY, max_entries)


def get_checked_keyserver_urls() -> list[str]:
    """Return the URLs of every checked keyserver, in display order.

    Returns
    -------
    :
        Checked keyserver URLs; empty if none are checked.
    """
    return [url for url, checked in get_keyservers() if checked]
