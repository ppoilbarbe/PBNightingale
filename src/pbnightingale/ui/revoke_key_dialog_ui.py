"""UI layout for the Revoke Key dialog (strong confirmation required)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_RevokeKeyDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Revoke Key"))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        self.lblWarning = QLabel(dialog)
        self.lblWarning.setWordWrap(True)
        layout.addWidget(self.lblWarning)

        self._build_confirm_checkbox(dialog, layout)
        self._build_passphrase_field(dialog, layout, label=_("Passphrase:"))
        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Revoke"), ok_enabled=False)
