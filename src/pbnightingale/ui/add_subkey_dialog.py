"""Add Subkey dialog.

Adds a sign/encrypt/authenticate subkey to a key already in the keyring
(the key must have its secret part available).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pbnightingale import preferences
from pbnightingale.core import gpg_backend
from pbnightingale.ui.add_subkey_dialog_ui import Ui_AddSubkeyDialog
from pbnightingale.ui.geometry_mixin import GeometryMixin
from pbnightingale.ui.key_operation_dialog import KeyOperationDialog


class AddSubkeyDialog(GeometryMixin, KeyOperationDialog, QDialog):
    """Dialog for adding a subkey to an existing key."""

    def __init__(self, fingerprint: str, parent=None) -> None:
        """Build the dialog for the key identified by *fingerprint*.

        Parameters
        ----------
        fingerprint
            The key to add the subkey to.
        parent
            The owning widget, if any.
        """
        super().__init__(parent)
        self._fingerprint = fingerprint
        self._ui = Ui_AddSubkeyDialog()
        self._ui.setupUi(self)
        self._init_geometry("add_subkey_dialog")
        self._init_key_operation()

        idx = self._ui.cmbAlgorithm.findData(preferences.get_preferred_algorithm())
        if idx >= 0:
            self._ui.cmbAlgorithm.setCurrentIndex(idx)
        self._ui.cmbAlgorithm.currentIndexChanged.connect(self._sync_key_size_enabled)
        self._sync_key_size_enabled()

        self._ui.buttonBox.accepted.connect(self._on_add)
        self._ui.buttonBox.rejected.connect(self.reject)

    def _sync_key_size_enabled(self) -> None:
        """Enable the key-size field only for RSA (ED25519 has a fixed curve)."""
        self._ui.cmbKeySize.setEnabled(self._ui.cmbAlgorithm.currentData() == "RSA")

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable every form field and the OK button.

        Parameters
        ----------
        enabled
            Whether the fields should be interactive.
        """
        self._ui.cmbPurpose.setEnabled(enabled)
        self._ui.cmbAlgorithm.setEnabled(enabled)
        self._ui.cmbKeySize.setEnabled(
            enabled and self._ui.cmbAlgorithm.currentData() == "RSA"
        )
        self._ui.txtPassphrase.setEnabled(enabled)
        self._ui.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def _on_add(self) -> None:
        """Add the new subkey via the backend."""
        self._run_operation(
            lambda: gpg_backend.default_backend().add_subkey(
                self._fingerprint,
                self._ui.txtPassphrase.text(),
                usage=self._ui.cmbPurpose.currentData(),
                algorithm=self._ui.cmbAlgorithm.currentData(),
                key_length=self._ui.cmbKeySize.currentData(),
            ),
            busy_text=_("Adding subkey…"),
            error_template=_("Could not add subkey: {error}"),
        )
