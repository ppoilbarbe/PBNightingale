"""Change Passphrase dialog.

Changes a key's own private-key passphrase. The new passphrase is entered
twice (live-validated for a match) and
shown against the same strength meter used by ``NewKeyWizard``'s
Passphrase page — see CODING.md, "Changing a key's passphrase".
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale import preferences
from pbnightingale.core import gpg_backend, passphrase_cache
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.change_passphrase_dialog_ui import Ui_ChangePassphraseDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


class ChangePassphraseDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for changing a key's own private-key passphrase."""

    def __init__(self, fingerprint: str, parent=None) -> None:
        """Build the dialog for the key identified by *fingerprint*.

        Parameters
        ----------
        fingerprint
            The key whose passphrase is being changed.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._new_passphrase = Passphrase("")
        self._ui = Ui_ChangePassphraseDialog()
        self._ui.setupUi(self)
        self._init_geometry("change_passphrase_dialog")
        self._init_key_operation()

        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.txtNewPassphrase.textChanged.connect(self._on_new_passphrase_changed)
        self._ui.txtNewPassphraseConfirm.textChanged.connect(
            self._on_new_passphrase_changed
        )
        self._on_new_passphrase_changed()

        self._ui.buttonBox.accepted.connect(self._on_change)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _new_matches(self) -> bool:
        """Return whether the new-passphrase field matches its confirmation."""
        return (
            self._ui.txtNewPassphrase.text() == self._ui.txtNewPassphraseConfirm.text()
        )

    def _is_new_valid(self) -> bool:
        """Return whether the new passphrase is non-empty and confirmed."""
        return self._new_matches() and bool(self._ui.txtNewPassphrase.text())

    def _on_new_passphrase_changed(self) -> None:
        """Refresh the strength meter, mismatch warning and OK button."""
        self._ui.strengthMeter.set_password(self._ui.txtNewPassphrase.text())
        self._ui.lblMismatch.setVisible(not self._new_matches())
        self._ok_button.setEnabled(self._is_new_valid())

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.txtNewPassphrase.setEnabled(enabled)
        self._ui.txtNewPassphraseConfirm.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._is_new_valid())

    def _bad_passphrase_message(self) -> str:
        """Return the message shown when the current passphrase is wrong."""
        return _("Incorrect current passphrase.")

    def _on_change(self) -> None:
        """Change the passphrase via the backend."""
        self._new_passphrase = Passphrase(self._ui.txtNewPassphrase.text())
        self._run_operation(
            lambda: gpg_backend.default_backend().change_passphrase(
                self._fingerprint,
                Passphrase(self._ui.txtPassphrase.text()),
                self._new_passphrase,
            ),
            busy_text=_("Changing passphrase…"),
            error_template=_("Could not change passphrase: {error}"),
        )

    def _on_operation_success(self, result) -> None:
        """Cache the new passphrase instead of the now-stale old one.

        Overrides ``KeyOperationDialog``'s default caching, which would
        cache the *old* passphrase (the field ``_run_operation()`` reads)
        — now stale, since the whole point of this dialog is that it no
        longer unlocks the key.

        Parameters
        ----------
        result
            The updated key, forwarded to ``_on_operation_result()``.
        """
        passphrase_cache.store(
            self._fingerprint,
            self._new_passphrase,
            preferences.get_passphrase_cache_minutes() * 60,
        )
        self._on_operation_result(result)
