"""In-memory passphrase cache, keyed by key fingerprint.

Never touches disk — passphrases live only in this process's memory, for a
configurable duration (``preferences.get_passphrase_cache_minutes()``)
counted from when they were entered, not renewed on later reads: a
passphrase entered more than that long ago is forgotten, exactly like
asking again. A deliberate convenience/security trade-off — see
CODING.md, "Passphrase caching".
"""

from __future__ import annotations

import time

from pbnightingale.core.secret import Passphrase

_cache: dict[str, tuple[Passphrase, float]] = {}


def get(fingerprint: str) -> Passphrase | None:
    """Return the passphrase cached for a key, if any.

    An expired entry is dropped here, the same as if it had never been
    cached.

    Parameters
    ----------
    fingerprint
        The key whose cached passphrase to look up.

    Returns
    -------
    :
        The cached passphrase, or ``None`` if there isn't one or it has
        expired.
    """
    entry = _cache.get(fingerprint)
    if entry is None:
        return None
    passphrase, expires_at = entry
    if time.monotonic() >= expires_at:
        del _cache[fingerprint]
        return None
    return passphrase


def store(fingerprint: str, passphrase: Passphrase, ttl_seconds: float) -> None:
    """Cache a passphrase for a key, expiring after a given duration.

    A non-positive ``ttl_seconds`` or an empty ``passphrase`` is a no-op:
    caching is opted out of via a 0-minute preference, not a separate
    flag, and an empty passphrase isn't worth caching.

    Parameters
    ----------
    fingerprint
        The key to cache the passphrase for.
    passphrase
        The passphrase to cache.
    ttl_seconds
        How long to keep it, counted from now.
    """
    if not passphrase or ttl_seconds <= 0:
        return
    _cache[fingerprint] = (passphrase, time.monotonic() + ttl_seconds)


def forget(fingerprint: str) -> None:
    """Forget the passphrase cached for a key, if any.

    A no-op if nothing is cached for it — e.g. double-clicking the key
    list's lock icon after the entry already expired on its own.

    Parameters
    ----------
    fingerprint
        The key whose cached passphrase to forget.
    """
    _cache.pop(fingerprint, None)


def clear() -> None:
    """Forget every cached passphrase.

    Tests must never leak a cached passphrase into another test — this
    module-level cache otherwise persists for the whole pytest session;
    see ``tests/conftest.py``'s autouse ``_isolated_passphrase_cache``.
    """
    _cache.clear()
