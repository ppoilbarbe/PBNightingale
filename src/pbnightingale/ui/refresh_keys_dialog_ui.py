"""UI layout for the Refresh Keys (from keyserver) confirmation dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QRadioButton, QVBoxLayout

from pbnightingale.ui.key_operation_dialog_ui import KeyOperationDialogUiMixin


class Ui_RefreshKeysDialog(KeyOperationDialogUiMixin):
    def setupUi(self, dialog: QDialog) -> None:
        dialog.setWindowTitle(_("Refresh Keys"))
        dialog.setMinimumWidth(360)

        layout = QVBoxLayout(dialog)

        self.lblExplanation = QLabel(dialog)
        self.lblExplanation.setWordWrap(True)
        layout.addWidget(self.lblExplanation)

        self.radioSelected = QRadioButton(_("Refresh the selected key only"), dialog)
        layout.addWidget(self.radioSelected)
        self.radioAll = QRadioButton(_("Refresh every key in the keyring"), dialog)
        layout.addWidget(self.radioAll)

        self._build_button_box(dialog, layout, ok_text=_("Refresh"))
