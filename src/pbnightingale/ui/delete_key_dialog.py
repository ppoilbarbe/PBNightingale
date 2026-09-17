"""Delete Key dialog.

Strong confirmation (a checkbox, not just a button click) before
permanently erasing a key from the keyring. Unlike ``RevokeKeyDialog``,
this needs no passphrase (see ``GPGBackend.delete_key()``) and the key no
longer exists at all afterwards, rather than merely being marked
untrustworthy.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale.core import gpg_backend
from pbnightingale.core.gpg_backend import Key
from pbnightingale.ui.delete_key_dialog_ui import Ui_DeleteKeyDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


class DeleteKeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for permanently deleting a key from the keyring."""

    def __init__(self, key: Key, parent: QDialog | None = None) -> None:
        """Build the dialog for deleting *key*.

        Parameters
        ----------
        key
            The key to delete.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = key.fingerprint
        self._has_secret = key.has_secret
        self._ui = Ui_DeleteKeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("delete_key_dialog")
        self._init_key_operation()

        self._ui.lblWarning.setText(
            _(
                "This permanently deletes {keyid} from your keyring, "
                "including any private key material. Unlike revoking, "
                "the key will no longer exist at all afterwards."
            ).format(keyid=key.keyid)
        )
        self._ok_button = self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        self._ui.chkConfirm.toggled.connect(self._ok_button.setEnabled)

        self._ui.buttonBox.accepted.connect(self._on_delete)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _passphrase_line_edit(self):
        """Return ``None`` — deleting a key never needs a passphrase."""
        return

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the confirmation checkbox and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.chkConfirm.setEnabled(enabled)
        self._ok_button.setEnabled(enabled and self._ui.chkConfirm.isChecked())

    def _on_delete(self) -> None:
        """Delete the key via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().delete_key(
                self._fingerprint, secret=self._has_secret
            ),
            busy_text=_("Deleting key…"),
            error_template=_("Could not delete key: {error}"),
        )

    def _on_operation_result(self, _result: None) -> None:
        """Close the dialog once the key has been deleted."""
        self.accept()
