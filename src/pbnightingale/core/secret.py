"""A wrapper that keeps a passphrase out of any incidental text.

See ``Passphrase`` for the rationale and the intended usage pattern.
"""

from __future__ import annotations

from dataclasses import dataclass

_REDACTED = "**********"


@dataclass(frozen=True, slots=True)
class Passphrase:
    """Wraps a secret passphrase so it never leaks through casual conversion.

    ``str()`` and ``repr()`` always show ``"**********"``, never the real
    value — including when some traceback tool dumps a frame's local
    variables while formatting an exception, the scenario this exists to
    close off. The actual text is reachable only through the
    ``passphrase`` property.

    Every function that receives, stores or forwards a passphrase should
    take/hold one of these instead of a bare ``str``, and reading
    ``.passphrase`` should be kept to the bare minimum — only at the
    point gpg's own protocol genuinely needs the raw text (building a
    ``--command-fd`` script, an ``input=`` payload, a python-gnupg
    keyword argument, or filling a widget that echoes it back to the
    user). Everywhere else — comparisons, emptiness checks, cache
    storage, log/debug redaction lists — works directly on the wrapper:
    ``bool(passphrase)`` and ``==`` behave exactly like the wrapped
    string would, without ever unwrapping it.
    """

    _value: str

    def __str__(self) -> str:
        """Return the fixed placeholder, never the real value."""
        return _REDACTED

    def __repr__(self) -> str:
        """Return a placeholder repr, never the real value."""
        return f"<{type(self).__name__} '{_REDACTED}'>"

    def __bool__(self) -> bool:
        """Return whether the wrapped passphrase is non-empty."""
        return bool(self._value)

    @property
    def passphrase(self) -> str:
        """The actual secret value — use sparingly, see the class docstring."""
        return self._value
