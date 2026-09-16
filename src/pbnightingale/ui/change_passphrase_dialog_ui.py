"""UI layout for the Change Passphrase dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin
from pbnightingale.ui.password_line_edit import PasswordLineEdit
from pbnightingale.ui.password_strength_meter import PasswordStrengthMeter


class Ui_ChangePassphraseDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Change Passphrase"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        self._build_passphrase_field(
            dialog, layout, label=_("Current passphrase:"), form=form
        )

        self.txtNewPassphrase = PasswordLineEdit(dialog)
        form.addRow(_("New passphrase:"), self.txtNewPassphrase)
        self.strengthMeter = PasswordStrengthMeter(dialog)
        form.addRow(self.strengthMeter)
        self.txtNewPassphraseConfirm = PasswordLineEdit(dialog)
        form.addRow(_("Confirm new passphrase:"), self.txtNewPassphraseConfirm)
        layout.addLayout(form)

        self.lblMismatch = QLabel(_("Passphrases do not match."), dialog)
        self.lblMismatch.setStyleSheet("color: red;")
        self.lblMismatch.setVisible(False)
        layout.addWidget(self.lblMismatch)

        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Change"), ok_enabled=False)
