"""UI layout for the Back Up Private Key dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_BackupPrivateKeyDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Back Up Private Key"))
        dialog.setMinimumWidth(420)

        layout = QVBoxLayout(dialog)

        self.lblWarning = QLabel(dialog)
        self.lblWarning.setWordWrap(True)
        layout.addWidget(self.lblWarning)

        self._build_passphrase_field(dialog, layout)
        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Back Up…"))
