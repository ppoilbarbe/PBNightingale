"""Mixin factoring out what every add/set/revoke dialog in this app does identically.

Runs one passphrase-guarded ``GPGBackend`` call off the GUI thread, shows
a busy indicator while it's in flight, reports a new ``Key`` on success
(and closes), or a translated error message on failure — plus, now,
caches a passphrase that turned out to be correct.

Usage::

    class MyDialog(GeometryMixin, KeyOperationDialog, QDialog):
        def __init__(self, fingerprint: str, parent=None) -> None:
            super().__init__(parent)
            self._fingerprint = fingerprint          # _cache_fingerprint() default
            self._ui = Ui_MyDialog()
            self._ui.setupUi(self)
            self._init_geometry("my_dialog")
            self._init_key_operation()               # after self._ui is ready
            ...
            self._ui.buttonBox.accepted.connect(self._on_accept)
            self._ui.buttonBox.rejected.connect(self.reject)

        def _set_form_enabled(self, enabled: bool) -> None:
            self._ui.someField.setEnabled(enabled)   # dialog-specific widgets
            self._ui.buttonBox.button(...).setEnabled(enabled)

        def _on_accept(self) -> None:
            self._run_operation(
                lambda: gpg_backend.default_backend().add_subkey(...),
                busy_text=_("Adding subkey…"),
                error_template=_("Could not add subkey: {error}"),
            )

A dialog whose passphrase belongs to a key other than ``self._fingerprint``
(``SignKeyDialog`` signs *as* a different key than the one being signed)
overrides ``_cache_fingerprint()``. A dialog with no passphrase field
simply doesn't set one — nothing here requires ``self._ui.txtPassphrase``
to exist unless ``_run_operation()`` (which reads it) is actually called.
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool

from pbnightingale import preferences
from pbnightingale.core import passphrase_cache
from pbnightingale.core.gpg_backend import BadPassphraseError, Key
from pbnightingale.ui.gpg_worker import run_async


class KeyOperationDialog:
    """Mixin providing the common accept/busy/error flow — see module docstring."""

    def _init_key_operation(self) -> None:
        """Initialize the worker pool and operation state — call after ``self._ui`` is ready."""
        self._pool = QThreadPool(self)
        self.updated_key: Key | None = None
        self._pending_fingerprint: str | None = None
        self._pending_passphrase: str = ""
        self._sync_cached_passphrase()

    def _passphrase_line_edit(self):
        """Return the field holding the passphrase to cache/prefill.

        Returns
        -------
        :
            Every dialog names this field the same, so this rarely needs
            overriding. ``None`` if the operation needs no passphrase at
            all (e.g. ``DeleteKeyDialog`` — deleting is a local keyring
            operation, not a cryptographic one) — nothing to prefill or
            cache then.
        """
        return self._ui.txtPassphrase

    def _cache_fingerprint(self) -> str | None:
        """Return which key's passphrase this dialog's field holds.

        Returns
        -------
        :
            Defaults to ``self._fingerprint`` (every dialog but
            ``SignKeyDialog`` sets this to the key being operated on);
            ``None`` disables both prefill and caching.
        """
        return getattr(self, "_fingerprint", None)

    def _sync_cached_passphrase(self) -> None:
        """Fill the passphrase field from the cache for the key it currently applies to.

        Clears the field if there's nothing cached. Call again after
        anything that changes ``_cache_fingerprint()``'s answer, e.g. a
        "sign as" key combo box changing selection.
        """
        field = self._passphrase_line_edit()
        if field is None:
            return
        fingerprint = self._cache_fingerprint()
        cached = passphrase_cache.get(fingerprint) if fingerprint else None
        field.setText(cached or "")

    def _bad_passphrase_message(self) -> str:
        """Return the message shown for a wrong passphrase.

        Overridable: most dialogs unlock the *primary* key, but a couple
        need different wording (see ``RevokeKeyDialog``, ``SignKeyDialog``).
        """
        return _("Incorrect primary key passphrase.")

    def _format_error(self, exc: Exception) -> str:
        """Return a message for *exc*, using this dialog's own wording for a wrong passphrase.

        Parameters
        ----------
        exc
            The exception raised by the failed operation.
        """
        if isinstance(exc, BadPassphraseError):
            return self._bad_passphrase_message()
        return str(exc)

    def _run_operation(self, call, *, busy_text: str, error_template: str) -> None:
        """Run *call* off the GUI thread and update the dialog accordingly.

        Parameters
        ----------
        call
            Zero-arg callable returning a ``Key``, run on a worker thread.
        busy_text
            Shown immediately in the status label while *call* runs.
        error_template
            Shown on failure, with an ``{error}`` placeholder for the
            formatted error message.
        """
        self._error_template = error_template
        self._pending_fingerprint = self._cache_fingerprint()
        field = self._passphrase_line_edit()
        self._pending_passphrase = field.text() if field is not None else ""
        self._set_form_enabled(False)
        self._ui.progress.setVisible(True)
        self._ui.lblStatus.setText(busy_text)
        run_async(
            self._pool,
            call,
            on_success=self._on_operation_success,
            on_error=self._on_operation_error,
        )

    def _on_operation_success(self, result) -> None:
        """Cache the passphrase just used (if any) and forward *result*.

        Parameters
        ----------
        result
            The value returned by the operation's ``call``, forwarded to
            ``_on_operation_result()``.
        """
        if self._pending_fingerprint and self._pending_passphrase:
            passphrase_cache.store(
                self._pending_fingerprint,
                self._pending_passphrase,
                preferences.get_passphrase_cache_minutes() * 60,
            )
        self._on_operation_result(result)

    def _on_operation_result(self, key: Key) -> None:
        """Handle a successful call's return value — overridable.

        Parameters
        ----------
        key
            Defaults to being treated as "it's the updated Key", which is
            stored and accepts the dialog. ``BackupPrivateKeyDialog``
            overrides this since its call returns armored key text to
            write to a file, not a ``Key``.
        """
        self.updated_key = key
        self.accept()

    def _on_operation_error(self, exc: Exception) -> None:
        """Show the formatted error and re-enable the form.

        Parameters
        ----------
        exc
            The exception raised by the failed operation.
        """
        self._ui.progress.setVisible(False)
        self._ui.lblStatus.setText(
            self._error_template.format(error=self._format_error(exc))
        )
        self._set_form_enabled(True)
