"""UI layout for the Add Subkey dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_AddSubkeyDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Add Subkey"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        self.cmbPurpose = QComboBox(dialog)
        self.cmbPurpose.addItem(_("Sign"), userData="sign")
        self.cmbPurpose.addItem(_("Encrypt"), userData="encrypt")
        self.cmbPurpose.addItem(_("Authenticate"), userData="auth")
        form.addRow(_("Purpose:"), self.cmbPurpose)

        self.cmbAlgorithm = QComboBox(dialog)
        self.cmbAlgorithm.addItem(_("RSA"), userData="RSA")
        self.cmbAlgorithm.addItem(
            _("Ed25519 (modern, smaller keys)"), userData="ED25519"
        )
        form.addRow(_("Algorithm:"), self.cmbAlgorithm)

        self.cmbKeySize = QComboBox(dialog)
        for size in (2048, 3072, 4096):
            self.cmbKeySize.addItem(str(size), userData=size)
        self.cmbKeySize.setCurrentIndex(self.cmbKeySize.count() - 1)
        form.addRow(_("Key size (bits):"), self.cmbKeySize)

        self._build_passphrase_field(dialog, layout, form=form)
        layout.addLayout(form)

        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Add"))
