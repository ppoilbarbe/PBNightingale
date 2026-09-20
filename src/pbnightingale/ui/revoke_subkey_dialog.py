"""Revoke Subkey dialog.

Strong confirmation (a checkbox, not just a button click) before an
irreversible operation.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Subkey
from pbnightingale.core.secret import Passphrase
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog
from pbnightingale.ui.revoke_subkey_dialog_ui import Ui_RevokeSubkeyDialog


class RevokeSubkeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for revoking a subkey."""

    def __init__(self, fingerprint: str, subkey: Subkey, parent=None) -> None:
        """Build the dialog for revoking *subkey*.

        Parameters
        ----------
        fingerprint
            The subkey's primary key.
        subkey
            The subkey to revoke.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._subkey = subkey
        self._ui = Ui_RevokeSubkeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("revoke_subkey_dialog")
        self._init_key_operation()

        self._ui.lblWarning.setText(
            _(
                "You are about to revoke subkey {keyid}. This cannot be "
                "undone: the subkey will stop being usable everywhere this "
                "key is trusted."
            ).format(keyid=subkey.keyid)
        )
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.chkConfirm.toggled.connect(self._ok_button.setEnabled)

        self._ui.buttonBox.accepted.connect(self._on_revoke)
        self._ui.buttonBox.rejected.connect(self.reject)

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
        """Revoke the subkey via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().revoke_subkey(
                self._fingerprint,
                self._subkey.keyid,
                Passphrase(self._ui.txtPassphrase.text()),
            ),
            busy_text=_("Revoking subkey…"),
            error_template=_("Could not revoke subkey: {error}"),
        )
