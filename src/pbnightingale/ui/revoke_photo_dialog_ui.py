"""UI layout for the Revoke Photo dialog (strong confirmation required)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_RevokePhotoDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Revoke Photo"))
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)

        header_row = QHBoxLayout()
        self.lblPreview = QLabel(dialog)
        self.lblPreview.setFixedSize(96, 96)
        self.lblPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblPreview.setStyleSheet("border: 1px solid palette(mid);")
        header_row.addWidget(self.lblPreview)

        self.lblWarning = QLabel(dialog)
        self.lblWarning.setWordWrap(True)
        header_row.addWidget(self.lblWarning, 1)
        layout.addLayout(header_row)

        self._build_confirm_checkbox(dialog, layout)
        self._build_passphrase_field(dialog, layout)
        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Revoke"), ok_enabled=False)
