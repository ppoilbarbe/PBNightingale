"""Revoke Key dialog.

Strong confirmation (a checkbox, not just a button click) before
irreversibly revoking a primary key (not a subkey — see
``revoke_subkey_dialog.py``).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.revoke_key_dialog_ui import Ui_RevokeKeyDialog


class RevokeKeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for revoking a primary key."""

    def __init__(self, key: Key, parent=None) -> None:
        """Build the dialog for revoking *key*.

        Parameters
        ----------
        key
            The key to revoke.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = key.fingerprint
        self._ui = Ui_RevokeKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("revoke_key_dialog")
        self._init_key_operation()

        self._ui.lblWarning.setText(
            _(
                "You are about to revoke key {keyid}. This cannot be "
                "undone: the key will stop being usable, and every "
                "signature it made will no longer be trusted."
            ).format(keyid=key.keyid)
        )
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.chkConfirm.toggled.connect(self._ok_button.setEnabled)

        self._ui.buttonBox.accepted.connect(self._on_revoke)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _bad_passphrase_message(self) -> str:
        """Return the message shown when the passphrase is wrong."""
        return _("Incorrect passphrase.")

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.chkConfirm.setEnabled(enabled)
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.chkConfirm.isChecked())

    def _on_revoke(self) -> None:
        """Revoke the key via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().revoke_key(
                self._fingerprint, Passphrase(self._ui.txtPassphrase.text())
            ),
            busy_text=_("Revoking key…"),
            error_template=_("Could not revoke key: {error}"),
        )
