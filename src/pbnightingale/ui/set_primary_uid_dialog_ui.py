"""UI layout for the Set Primary User ID dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_SetPrimaryUidDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Set as Primary User ID"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        self.lblExplanation = QLabel(dialog)
        self.lblExplanation.setWordWrap(True)
        layout.addWidget(self.lblExplanation)

        self._build_passphrase_field(dialog, layout)
        self._build_progress_and_status(dialog, layout)
        self._build_button_box(dialog, layout, ok_text=_("Set"))
